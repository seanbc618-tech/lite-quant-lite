#!/usr/bin/env python3
"""Evaluate an independent monthly SEC quality satellite research candidate."""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


QUALITY_METRICS = ("roe_ttm", "cash_conversion_ttm", "debt_to_assets")
VALID_VARIANTS = frozenset({"base", "reported_only"})
BENCHMARKS = ("SPY", "QQQ")
WINDOWS = ("full", "63d", "126d", "252d")
DEFAULT_QUALITY = Path(".cache/fundamentals/quality_daily.parquet")
DEFAULT_PROVIDER = Path.home() / ".qlib" / "qlib_data" / "us_modern_liquid100"
DEFAULT_REPORT = Path(".cache/reports/quality_satellite_candidate_latest.md")
DEFAULT_HOLDINGS = Path(".cache/quality_satellite/latest_holdings.parquet")
DEFAULT_LIGHTGBM_REPORT = Path(".cache/reports/modern_low_monitor_latest.md")
DEFAULT_FULL_START = "2025-01-02"


@dataclass(frozen=True)
class StressRow:
    variant: str
    benchmark: str
    window: str
    ann_excess_cost: float
    max_drawdown_cost: float
    ir_cost: float
    turnover: float
    transaction_cost: float


@dataclass(frozen=True)
class PromotionCheck:
    rule: str
    passed: bool
    detail: str


def score_snapshot(snapshot: pd.DataFrame, variant: str, topk: int = 9) -> pd.DataFrame:
    """Return scored top-k eligible rows for one information session."""
    if variant not in VALID_VARIANTS:
        raise ValueError(f"unknown quality variant: {variant}")
    if topk < 1:
        raise ValueError("topk must be positive")

    eligible = snapshot.copy()
    required = [*QUALITY_METRICS, "net_income_ttm"]
    eligible = eligible.dropna(subset=required)
    eligible = eligible.loc[eligible["net_income_ttm"] > 0]
    if variant == "reported_only":
        eligible = eligible.loc[eligible["debt_to_assets_source"] == "reported"]
    if eligible.empty:
        return eligible.assign(
            roe_rank=pd.Series(dtype=float),
            cash_conversion_rank=pd.Series(dtype=float),
            debt_to_assets_rank=pd.Series(dtype=float),
            quality_score=pd.Series(dtype=float),
            target_weight=pd.Series(dtype=float),
        )

    rank_settings = {
        "roe_ttm": ("roe_rank", True),
        "cash_conversion_ttm": ("cash_conversion_rank", True),
        "debt_to_assets": ("debt_to_assets_rank", False),
    }
    for field, (rank_field, higher_is_better) in rank_settings.items():
        lower = eligible[field].quantile(0.05)
        upper = eligible[field].quantile(0.95)
        winsorized = eligible[field].clip(lower=lower, upper=upper)
        eligible[rank_field] = winsorized.rank(
            pct=True,
            ascending=higher_is_better,
            method="average",
        )
    eligible["quality_score"] = eligible[
        ["roe_rank", "cash_conversion_rank", "debt_to_assets_rank"]
    ].mean(axis=1)
    selected = eligible.sort_values(
        ["quality_score", "ticker"], ascending=[False, True], kind="mergesort"
    ).head(topk).copy()
    selected["target_weight"] = 1.0 / len(selected)
    return selected.reset_index(drop=True)


def build_monthly_targets(
    quality: pd.DataFrame,
    calendar: Iterable[pd.Timestamp | str],
    variant: str,
    topk: int = 9,
) -> pd.DataFrame:
    """Use the preceding session snapshot to form first-session monthly targets."""
    sessions = sorted(pd.to_datetime(list(calendar)))
    quality = quality.copy()
    quality["session"] = pd.to_datetime(quality["session"])
    targets: list[pd.DataFrame] = []
    for index, session in enumerate(sessions):
        if index == 0 or session.to_period("M") == sessions[index - 1].to_period("M"):
            continue
        information_session = sessions[index - 1]
        snapshot = quality.loc[quality["session"] == information_session]
        selected = score_snapshot(snapshot, variant=variant, topk=topk)
        if selected.empty:
            continue
        selected["variant"] = variant
        selected["information_session"] = information_session
        selected["rebalance_session"] = session
        targets.append(selected)
    if not targets:
        return pd.DataFrame(
            columns=[
                *quality.columns,
                "roe_rank",
                "cash_conversion_rank",
                "debt_to_assets_rank",
                "quality_score",
                "target_weight",
                "variant",
                "information_session",
                "rebalance_session",
            ]
        )
    return pd.concat(targets, ignore_index=True)


def simulate_portfolio(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    open_cost: float = 0.0005,
    close_cost: float = 0.0015,
) -> pd.DataFrame:
    """Apply monthly targets at formation close and retain drifted holdings."""
    if open_cost < 0 or close_cost < 0:
        raise ValueError("transaction costs cannot be negative")
    if prices.empty:
        raise ValueError("prices cannot be empty")

    price_frame = prices.copy().sort_index()
    price_frame.index = pd.to_datetime(price_frame.index)
    target_frame = targets.copy()
    target_frame["rebalance_session"] = pd.to_datetime(target_frame["rebalance_session"])
    targets_by_session = {
        session: group.set_index("ticker")["target_weight"].astype(float)
        for session, group in target_frame.groupby("rebalance_session", sort=True)
    }

    holdings = pd.Series(dtype=float)
    cash_weight = 1.0
    started = False
    rows: list[dict[str, object]] = []
    sessions = price_frame.index.tolist()
    for start_session, end_session in zip(sessions[:-1], sessions[1:]):
        turnover = 0.0
        cost = 0.0
        if start_session in targets_by_session:
            target = targets_by_session[start_session]
            if target.sum() > 1.0 + 1e-12 or (target < 0).any():
                raise ValueError("target weights must be non-negative and sum to at most one")
            symbols = holdings.index.union(target.index)
            existing = holdings.reindex(symbols, fill_value=0.0)
            desired = target.reindex(symbols, fill_value=0.0)
            buys = (desired - existing).clip(lower=0.0).sum()
            sells = (existing - desired).clip(lower=0.0).sum()
            turnover = float(buys + sells)
            cost = float(buys * open_cost + sells * close_cost)
            holdings = target.copy()
            cash_weight = float(1.0 - target.sum() - cost)
            started = True
        if not started:
            continue

        active = holdings.loc[holdings > 0].index.tolist()
        if active:
            needed = price_frame.loc[[start_session, end_session], active]
            if needed.isna().any().any():
                raise ValueError(f"prices missing for active holdings at {end_session.date()}")
            asset_returns = price_frame.loc[end_session, active] / price_frame.loc[start_session, active] - 1.0
            gross_return = float((holdings.reindex(active) * asset_returns).sum())
        else:
            asset_returns = pd.Series(dtype=float)
            gross_return = 0.0
        end_value = cash_weight + float(
            (holdings.reindex(active) * (1.0 + asset_returns)).sum()
        )
        net_return = end_value - 1.0
        if end_value <= 0:
            raise ValueError("portfolio value became non-positive")
        if active:
            holdings.loc[active] = holdings.reindex(active) * (1.0 + asset_returns) / end_value
        cash_weight = cash_weight / end_value
        rows.append(
            {
                "session": end_session,
                "net_return": net_return,
                "gross_return": gross_return,
                "turnover": turnover,
                "cost": cost,
                "holding_count": int((holdings > 0).sum()),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["net_return", "gross_return", "turnover", "cost", "holding_count"]
        ).rename_axis("session")
    return pd.DataFrame(rows).set_index("session")


def build_stress_rows(
    daily: pd.DataFrame,
    benchmark_returns: dict[str, pd.Series],
    variant: str,
    windows: tuple[str, ...] = WINDOWS,
    full_start: str | pd.Timestamp | None = None,
) -> list[StressRow]:
    """Measure each benchmark/window from after-cost strategy returns."""
    from qlib.contrib.evaluate import risk_analysis

    rows: list[StressRow] = []
    for benchmark in BENCHMARKS:
        aligned_benchmark = benchmark_returns[benchmark].reindex(daily.index)
        if aligned_benchmark.isna().any():
            raise ValueError(f"benchmark returns do not cover strategy dates: {benchmark}")
        for window in windows:
            if window == "full":
                selected = daily if full_start is None else daily.loc[daily.index >= pd.Timestamp(full_start)]
                if selected.empty:
                    raise ValueError(f"full window starts outside strategy coverage: {full_start}")
                selected_benchmark = aligned_benchmark.reindex(selected.index)
            elif window.endswith("d") and window[:-1].isdigit():
                periods = int(window[:-1])
                if len(daily) < periods:
                    raise ValueError(f"window is outside strategy coverage: {window}")
                selected = daily.tail(periods)
                selected_benchmark = aligned_benchmark.tail(periods)
            else:
                raise ValueError(f"unknown stress window: {window}")
            excess = selected["net_return"] - selected_benchmark
            metrics = risk_analysis(excess, freq="day")["risk"]
            rows.append(
                StressRow(
                    variant=variant,
                    benchmark=benchmark,
                    window=window,
                    ann_excess_cost=float(metrics["annualized_return"]),
                    max_drawdown_cost=float(metrics["max_drawdown"]),
                    ir_cost=float(metrics["information_ratio"]),
                    turnover=float(selected["turnover"].sum()),
                    transaction_cost=float(selected["cost"].sum()),
                )
            )
    return rows


def build_benchmark_returns(prices: pd.DataFrame) -> dict[str, pd.Series]:
    """Compute benchmark returns using the explicit missing-data policy used by Qlib reports."""
    return {
        benchmark: prices[benchmark].pct_change(fill_method=None).fillna(0.0)
        for benchmark in BENCHMARKS
    }


def benchmark_missing_sessions(prices: pd.DataFrame) -> list[pd.Timestamp]:
    """Return benchmark price gaps that are treated as zero-return Qlib benchmark periods."""
    return pd.to_datetime(prices.index[prices[list(BENCHMARKS)].isna().any(axis=1)]).tolist()


def read_monitor_evaluation_session(path: Path) -> str | None:
    """Read the latest safely evaluable session emitted by the LightGBM monitor."""
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("latest_evaluable_session:"):
            return line.split(":", 1)[1].strip()
    return None


def read_lightgbm_reference(path: Path) -> dict[tuple[str, str], tuple[float, float]]:
    """Read after-cost return and drawdown references from a monitor report."""
    if not path.is_file():
        return {}
    references: dict[tuple[str, str], tuple[float, float]] = {}
    pattern = re.compile(r"_monitor_(full|63d|126d|252d)_bench(spy|qqq)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| lightgbm_"):
            continue
        fields = [field.strip() for field in line.strip("|").split("|")]
        match = pattern.search(fields[0])
        if not match:
            continue
        window, benchmark = match.groups()
        references[(benchmark.upper(), window)] = (
            float(fields[5].rstrip("%")) / 100,
            float(fields[6].rstrip("%")) / 100,
        )
    return references


def assess_promotion(
    rows: list[StressRow],
    references: dict[tuple[str, str], tuple[float, float]],
    maximum_holding_count: int,
) -> list[PromotionCheck]:
    """Apply the frozen research promotion gate to both quality variants."""
    checks = [
        PromotionCheck(
            "nine-equity holding cap",
            maximum_holding_count <= 9,
            f"maximum holdings: {maximum_holding_count}",
        )
    ]
    lookup = {(row.variant, row.benchmark, row.window): row for row in rows}
    for variant in ("base", "reported_only"):
        if any((benchmark, window) not in references for benchmark, window in (("QQQ", "63d"), ("QQQ", "126d"), ("SPY", "full"), ("QQQ", "full"))):
            checks.append(PromotionCheck(f"{variant} reference availability", False, "LightGBM reference missing"))
            continue
        qqq_63 = lookup[(variant, "QQQ", "63d")]
        qqq_126 = lookup[(variant, "QQQ", "126d")]
        spy_full = lookup[(variant, "SPY", "full")]
        qqq_full = lookup[(variant, "QQQ", "full")]
        checks.extend(
            [
                PromotionCheck(
                    f"{variant} QQQ/63d improvement",
                    qqq_63.ann_excess_cost >= references[("QQQ", "63d")][0] + 0.10,
                    f"quality {qqq_63.ann_excess_cost:.2%}; required {references[('QQQ', '63d')][0] + 0.10:.2%}",
                ),
                PromotionCheck(
                    f"{variant} QQQ/126d retention",
                    qqq_126.ann_excess_cost >= references[("QQQ", "126d")][0] - 0.05,
                    f"quality {qqq_126.ann_excess_cost:.2%}; required {references[('QQQ', '126d')][0] - 0.05:.2%}",
                ),
                PromotionCheck(
                    f"{variant} positive full-period excess",
                    spy_full.ann_excess_cost > 0 and qqq_full.ann_excess_cost > 0,
                    f"SPY {spy_full.ann_excess_cost:.2%}; QQQ {qqq_full.ann_excess_cost:.2%}",
                ),
                PromotionCheck(
                    f"{variant} full-period drawdown tolerance",
                    spy_full.max_drawdown_cost >= references[("SPY", "full")][1] - 0.05
                    and qqq_full.max_drawdown_cost >= references[("QQQ", "full")][1] - 0.05,
                    f"SPY {spy_full.max_drawdown_cost:.2%}; QQQ {qqq_full.max_drawdown_cost:.2%}",
                ),
            ]
        )
    return checks


def render_report(
    rows: list[StressRow],
    latest_holdings: pd.DataFrame,
    latest_session: str,
    maximum_holding_count: int,
    checks: list[PromotionCheck],
    full_start: str = DEFAULT_FULL_START,
    evaluation_session: str | None = None,
    missing_benchmark_sessions: list[pd.Timestamp] | None = None,
) -> str:
    """Render a research-only quality candidate stress report."""
    derived_share = 0.0
    base = latest_holdings.loc[latest_holdings["variant"] == "base"] if not latest_holdings.empty else latest_holdings
    if not base.empty:
        derived_share = base["debt_to_assets_source"].eq("derived_assets_minus_equity").mean() * 100
    missing_benchmark_sessions = missing_benchmark_sessions or []
    missing_label = ", ".join(session.date().isoformat() for session in missing_benchmark_sessions) or "none"
    lines = [
        "# Independent Quality Satellite Candidate Report",
        "",
        f"latest_provider_session: {latest_session}",
        f"latest_evaluable_session: {evaluation_session or latest_session}",
        f"comparison_full_start: {full_start}",
        f"benchmark_missing_sessions: {missing_label}",
        "benchmark_missing_policy: explicit Qlib-compatible zero benchmark return",
        f"maximum_holding_count: {maximum_holding_count}",
        f"latest_base_derived_leverage_share: {derived_share:.1f}%",
        "",
        "This candidate is research-only; it is not approved for paper execution.",
        "",
        "## Stress Windows",
        "",
        "| variant | benchmark | window | ann_excess_cost | max_dd_cost | IR_cost | turnover | transaction_cost |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.variant} | {row.benchmark} | {row.window} | "
            f"{row.ann_excess_cost:.2%} | {row.max_drawdown_cost:.2%} | {row.ir_cost:.4f} | "
            f"{row.turnover:.4f} | {row.transaction_cost:.4%} |"
        )
    lines.extend(["", "## Latest Holdings", ""])
    for variant in ("base", "reported_only"):
        lines.extend(
            [
                f"### {variant}",
                "",
                "| ticker | weight | quality_score | roe_ttm | cash_conversion_ttm | debt_to_assets | leverage_source |",
                "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        variant_holdings = latest_holdings.loc[latest_holdings["variant"] == variant]
        for holding in variant_holdings.sort_values(["quality_score", "ticker"], ascending=[False, True]).itertuples():
            lines.append(
                f"| {holding.ticker} | {holding.target_weight:.2%} | {holding.quality_score:.4f} | "
                f"{holding.roe_ttm:.4f} | {holding.cash_conversion_ttm:.4f} | "
                f"{holding.debt_to_assets:.4f} | {holding.debt_to_assets_source} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Promotion Gate",
            "",
            "| rule | status | evidence |",
            "| --- | --- | --- |",
        ]
    )
    for check in checks:
        lines.append(f"| {check.rule} | {'PASS' if check.passed else 'FAIL'} | {check.detail} |")
    lines.extend(
        [
            "",
            "Promotion requires every gate above to pass for both variants; a failure leaves this as research only.",
            "",
        ]
    )
    return "\n".join(lines)


def load_close_prices(provider_uri: Path, symbols: list[str], start_time: str, end_time: str) -> pd.DataFrame:
    """Load close prices for the quality universe and benchmark instruments."""
    import qlib
    from qlib.data import D

    qlib.init(provider_uri=str(provider_uri.expanduser()), region="us")
    raw = D.features(symbols, ["$close"], start_time=start_time, end_time=end_time, freq="day")
    return raw["$close"].unstack("instrument").sort_index()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行独立 SEC TTM 质量卫星研究回测")
    parser.add_argument("--quality", type=Path, default=DEFAULT_QUALITY)
    parser.add_argument("--provider-uri", type=Path, default=DEFAULT_PROVIDER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--holdings", type=Path, default=DEFAULT_HOLDINGS)
    parser.add_argument("--lightgbm-report", type=Path, default=DEFAULT_LIGHTGBM_REPORT)
    parser.add_argument("--full-start", default=DEFAULT_FULL_START, help="与 LightGBM 对比的 full 窗口起点")
    parser.add_argument("--end-time", help="评估截止日；默认读取 LightGBM monitor 的安全截止日")
    parser.add_argument("--topk", type=int, default=9)
    parser.add_argument("--open-cost", type=float, default=0.0005)
    parser.add_argument("--close-cost", type=float, default=0.0015)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    quality = pd.read_parquet(args.quality)
    quality["session"] = pd.to_datetime(quality["session"])
    symbols = sorted(set(quality["ticker"]).union(BENCHMARKS))
    prices = load_close_prices(
        args.provider_uri,
        symbols,
        quality["session"].min().date().isoformat(),
        quality["session"].max().date().isoformat(),
    )
    latest_provider_session = prices.index[-1].date().isoformat()
    evaluation_session = args.end_time or read_monitor_evaluation_session(args.lightgbm_report) or latest_provider_session
    evaluation_prices = prices.loc[prices.index <= pd.Timestamp(evaluation_session)]
    calendar = evaluation_prices.index.tolist()
    rows: list[StressRow] = []
    holdings: list[pd.DataFrame] = []
    maximum_holding_count = 0
    benchmark_returns = build_benchmark_returns(evaluation_prices)
    for variant in ("base", "reported_only"):
        targets = build_monthly_targets(quality, calendar, variant=variant, topk=args.topk)
        if targets.empty:
            raise ValueError(f"no targets generated for quality variant: {variant}")
        maximum_holding_count = max(
            maximum_holding_count,
            int(targets.groupby("rebalance_session")["ticker"].nunique().max()),
        )
        daily = simulate_portfolio(evaluation_prices, targets, args.open_cost, args.close_cost)
        rows.extend(build_stress_rows(daily, benchmark_returns, variant, full_start=args.full_start))
        latest_rebalance = targets["rebalance_session"].max()
        holdings.append(targets.loc[targets["rebalance_session"] == latest_rebalance].copy())
    latest_holdings = pd.concat(holdings, ignore_index=True)
    checks = assess_promotion(
        rows,
        read_lightgbm_reference(args.lightgbm_report),
        maximum_holding_count,
    )
    args.holdings.parent.mkdir(parents=True, exist_ok=True)
    latest_holdings.to_parquet(args.holdings, index=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_report(
            rows,
            latest_holdings,
            latest_provider_session,
            maximum_holding_count,
            checks,
            full_start=args.full_start,
            evaluation_session=evaluation_session,
            missing_benchmark_sessions=benchmark_missing_sessions(evaluation_prices),
        ),
        encoding="utf-8",
    )
    print(f"Quality satellite report: {args.report}")
    print(f"Latest holdings: {args.holdings}")
    print(f"Promotion gate: {'PASS' if all(check.passed for check in checks) else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

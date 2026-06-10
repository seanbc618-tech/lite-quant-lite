#!/usr/bin/env python3
"""Evaluate a lagged ETF trend-defense overlay for the reported-only quality candidate."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_quality_paper_signals import read_promotion_status
from scripts.run_quality_satellite_candidate import (
    BENCHMARKS,
    DEFAULT_FULL_START,
    DEFAULT_PROVIDER,
    DEFAULT_QUALITY,
    StressRow,
    benchmark_missing_sessions,
    build_benchmark_returns,
    build_monthly_targets,
    build_stress_rows,
    load_close_prices,
    read_monitor_evaluation_session,
    simulate_portfolio,
)


TREND_SYMBOLS = ("SPY", "QQQ")
DEFAULT_LOOKBACK = 200
EXPOSURE_PROFILES = {
    "hard": {"risk_on": 1.0, "defensive": 0.5, "cash": 0.0},
    "gentle": {"risk_on": 1.0, "defensive": 0.75, "cash": 0.5},
}
DEFAULT_QUALITY_REPORT = Path(".cache/reports/quality_satellite_monitor_latest.md")
DEFAULT_LIGHTGBM_REPORT = Path(".cache/reports/modern_low_monitor_latest.md")
DEFAULT_OUTPUT = Path(".cache/reports/quality_trend_defense_latest.md")
DEFAULT_STATES = Path(".cache/quality_trend_defense/daily_states.parquet")
DEFAULT_MLRUNS = Path("mlruns")
DEFAULT_SIGNAL_START = "2020-11-02"
DEFAULT_EXPERIMENT_BASE = "lightgbm_alpha158_liquid100_modern_low_turnover_candidate_deterministic_monitor_"


@dataclass(frozen=True)
class OverlayCheck:
    rule: str
    passed: bool
    detail: str


def build_trend_states(
    prices: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK, profile: str = "hard"
) -> pd.DataFrame:
    """Return exposures effective on session t using closes visible through t-1."""
    if lookback < 1:
        raise ValueError("lookback must be positive")
    if profile not in EXPOSURE_PROFILES:
        raise ValueError(f"unknown trend exposure profile: {profile}")
    missing = set(TREND_SYMBOLS).difference(prices.columns)
    if missing:
        raise ValueError(f"trend prices missing symbols: {', '.join(sorted(missing))}")
    prices = prices.sort_index()
    rows: list[dict[str, object]] = []
    for index, effective_session in enumerate(prices.index):
        prior = prices.index[index - 1] if index else None
        failure_reason: str | None = None
        passed = 0
        if prior is None:
            failure_reason = "no_prior_session"
        else:
            for symbol in TREND_SYMBOLS:
                prior_close = prices.at[prior, symbol]
                history = prices.loc[:prior, symbol].dropna().tail(lookback)
                if pd.isna(prior_close):
                    failure_reason = f"missing_prior_close:{symbol}"
                    break
                if len(history) < lookback:
                    failure_reason = f"insufficient_history:{symbol}"
                    break
                passed += int(float(prior_close) >= float(history.mean()))
        state = {2: "risk_on", 1: "defensive", 0: "cash"}[passed if not failure_reason else 0]
        exposure = 0.0 if failure_reason else EXPOSURE_PROFILES[profile][state]
        rows.append(
            {
                "session": effective_session,
                "state": state,
                "exposure": exposure,
                "failure_reason": failure_reason,
            }
        )
    return pd.DataFrame(rows).set_index("session")


def simulate_quality_overlay(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    states: pd.DataFrame,
    open_cost: float = 0.0005,
    close_cost: float = 0.0015,
) -> pd.DataFrame:
    """Trade actual holdings to monthly targets scaled by lagged market exposure."""
    if open_cost < 0 or close_cost < 0:
        raise ValueError("transaction costs cannot be negative")
    if prices.empty:
        raise ValueError("prices cannot be empty")
    price_frame = prices.copy().sort_index()
    price_frame.index = pd.to_datetime(price_frame.index)
    state_frame = states.copy()
    state_frame.index = pd.to_datetime(state_frame.index)
    if not price_frame.index.isin(state_frame.index).all():
        raise ValueError("trend states do not cover prices")

    target_frame = targets.copy()
    target_frame["rebalance_session"] = pd.to_datetime(target_frame["rebalance_session"])
    targets_by_session = {
        session: group.set_index("ticker")["target_weight"].astype(float)
        for session, group in target_frame.groupby("rebalance_session", sort=True)
    }
    base_target = pd.Series(dtype=float)
    holdings = pd.Series(dtype=float)
    cash_weight = 1.0
    applied_exposure: float | None = None
    started = False
    rows: list[dict[str, object]] = []
    sessions = price_frame.index.tolist()
    for start_session, end_session in zip(sessions[:-1], sessions[1:]):
        state = state_frame.loc[start_session]
        exposure = float(state["exposure"])
        target_changed = start_session in targets_by_session
        if target_changed:
            base_target = targets_by_session[start_session]
            if base_target.sum() > 1.0 + 1e-12 or (base_target < 0).any():
                raise ValueError("target weights must be non-negative and sum to at most one")

        turnover = 0.0
        cost = 0.0
        must_trade = not base_target.empty and (
            target_changed or applied_exposure is None or exposure != applied_exposure
        )
        if must_trade:
            if target_changed or holdings.sum() <= 0:
                desired = base_target * exposure
            else:
                desired = holdings / holdings.sum() * exposure
            symbols = holdings.index.union(desired.index)
            existing = holdings.reindex(symbols, fill_value=0.0)
            desired = desired.reindex(symbols, fill_value=0.0)
            buys = float((desired - existing).clip(lower=0.0).sum())
            sells = float((existing - desired).clip(lower=0.0).sum())
            turnover = buys + sells
            cost = buys * open_cost + sells * close_cost
            holdings = desired.loc[desired > 0]
            cash_weight = float(1.0 - holdings.sum() - cost)
            started = True
        if not base_target.empty:
            applied_exposure = exposure
        if not started:
            continue

        active = holdings.index.tolist()
        if active:
            needed = price_frame.loc[[start_session, end_session], active]
            if needed.isna().any().any():
                raise ValueError(f"prices missing for active holdings at {end_session.date()}")
            asset_returns = (
                price_frame.loc[end_session, active] / price_frame.loc[start_session, active] - 1.0
            )
            gross_return = float((holdings * asset_returns).sum())
        else:
            asset_returns = pd.Series(dtype=float)
            gross_return = 0.0
        end_value = cash_weight + float((holdings * (1.0 + asset_returns)).sum())
        if end_value <= 0:
            raise ValueError("portfolio value became non-positive")
        if active:
            holdings = holdings * (1.0 + asset_returns) / end_value
        cash_weight = cash_weight / end_value
        rows.append(
            {
                "session": end_session,
                "net_return": end_value - 1.0,
                "gross_return": gross_return,
                "turnover": turnover,
                "cost": cost,
                "holding_count": int(len(active)),
                "state": state["state"],
                "exposure": exposure,
                "failure_reason": state.get("failure_reason"),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "net_return",
                "gross_return",
                "turnover",
                "cost",
                "holding_count",
                "state",
                "exposure",
                "failure_reason",
            ]
        ).rename_axis("session")
    return pd.DataFrame(rows).set_index("session")


def summarize_absolute_returns(daily: pd.DataFrame, full_start: str) -> tuple[float, float]:
    """Return after-cost annualized strategy return and its own maximum drawdown."""
    from qlib.contrib.evaluate import risk_analysis

    selected = daily.loc[daily.index >= pd.Timestamp(full_start)]
    if selected.empty:
        raise ValueError(f"full window starts outside strategy coverage: {full_start}")
    metrics = risk_analysis(selected["net_return"], freq="day")["risk"]
    return float(metrics["annualized_return"]), float(metrics["max_drawdown"])


def _stress_lookup(rows: list[StressRow]) -> dict[tuple[str, str], StressRow]:
    return {(row.benchmark, row.window): row for row in rows}


def assess_overlay_gate(
    underlying_gate: str,
    original_rows: list[StressRow],
    defended_rows: list[StressRow],
    original_absolute_max_drawdown: float,
    defended_absolute_max_drawdown: float,
    maximum_holding_count: int,
    hidden_failure_count: int,
) -> list[OverlayCheck]:
    """Apply approved promotion rules to the protected reported-only candidate."""
    original = _stress_lookup(original_rows)
    defended = _stress_lookup(defended_rows)
    required = (("SPY", "full"), ("QQQ", "full"), ("QQQ", "126d"))
    if any(key not in original or key not in defended for key in required):
        return [OverlayCheck("required stress rows", False, "required comparison rows missing")]
    return [
        OverlayCheck(
            "underlying quality promotion gate",
            underlying_gate == "PASS",
            f"underlying quality gate: {underlying_gate}",
        ),
        OverlayCheck(
            "nine-equity holding cap",
            maximum_holding_count <= 9,
            f"maximum holdings: {maximum_holding_count}",
        ),
        OverlayCheck(
            "absolute full-period drawdown improvement",
            defended_absolute_max_drawdown - original_absolute_max_drawdown >= 0.02,
            f"original {original_absolute_max_drawdown:.2%}; defended {defended_absolute_max_drawdown:.2%}",
        ),
        OverlayCheck(
            "positive full-period excess",
            defended[("SPY", "full")].ann_excess_cost > 0
            and defended[("QQQ", "full")].ann_excess_cost > 0,
            f"SPY {defended[('SPY', 'full')].ann_excess_cost:.2%}; "
            f"QQQ {defended[('QQQ', 'full')].ann_excess_cost:.2%}",
        ),
        OverlayCheck(
            "QQQ/full excess retention",
            defended[("QQQ", "full")].ann_excess_cost
            >= original[("QQQ", "full")].ann_excess_cost - 0.05,
            f"original {original[('QQQ', 'full')].ann_excess_cost:.2%}; "
            f"defended {defended[('QQQ', 'full')].ann_excess_cost:.2%}",
        ),
        OverlayCheck(
            "QQQ/126d excess retention",
            defended[("QQQ", "126d")].ann_excess_cost > 0
            and defended[("QQQ", "126d")].ann_excess_cost
            >= original[("QQQ", "126d")].ann_excess_cost - 0.05,
            f"original {original[('QQQ', '126d')].ann_excess_cost:.2%}; "
            f"defended {defended[('QQQ', '126d')].ann_excess_cost:.2%}",
        ),
        OverlayCheck(
            "full-period excess drawdown tolerance",
            defended[("SPY", "full")].max_drawdown_cost
            >= original[("SPY", "full")].max_drawdown_cost - 0.02
            and defended[("QQQ", "full")].max_drawdown_cost
            >= original[("QQQ", "full")].max_drawdown_cost - 0.02,
            f"SPY {defended[('SPY', 'full')].max_drawdown_cost:.2%}; "
            f"QQQ {defended[('QQQ', 'full')].max_drawdown_cost:.2%}",
        ),
        OverlayCheck(
            "fail-closed audit completeness",
            hidden_failure_count == 0,
            f"unrecorded signal failures: {hidden_failure_count}",
        ),
    ]


def apply_return_overlay(
    original_net_returns: pd.Series,
    exposures: pd.Series,
    open_cost: float = 0.0005,
    close_cost: float = 0.0015,
) -> pd.Series:
    """Apply return-level exposure transitions for the research-only ML comparison."""
    exposure = exposures.reindex(original_net_returns.index)
    if exposure.isna().any():
        raise ValueError("exposures do not cover return series")
    previous = exposure.shift(1)
    if not exposure.empty:
        previous.iloc[0] = exposure.iloc[0]
    buys = (exposure - previous).clip(lower=0.0)
    sells = (previous - exposure).clip(lower=0.0)
    transition_cost = buys * open_cost + sells * close_cost
    return original_net_returns * exposure - transition_cost


def evaluate_lightgbm_comparison(
    scenarios: dict[tuple[str, str], pd.DataFrame],
    states: pd.DataFrame,
    open_cost: float = 0.0005,
    close_cost: float = 0.0015,
) -> tuple[list[StressRow], list[StressRow]]:
    """Apply the overlay independently to each existing ML monitor scenario."""
    from qlib.contrib.evaluate import risk_analysis

    original_rows: list[StressRow] = []
    defended_rows: list[StressRow] = []
    interval_exposures = states["exposure"].shift(1)
    for benchmark in BENCHMARKS:
        for window in ("full", "63d", "126d", "252d"):
            report = scenarios.get((benchmark, window))
            if report is None:
                continue
            original_net = report["return"] - report["cost"]
            exposures = interval_exposures.reindex(report.index)
            defended_net = apply_return_overlay(original_net, exposures, open_cost, close_cost)
            previous_exposure = exposures.shift(1)
            if not exposures.empty:
                previous_exposure.iloc[0] = exposures.iloc[0]
            overlay_cost = (
                (exposures - previous_exposure).clip(lower=0.0) * open_cost
                + (previous_exposure - exposures).clip(lower=0.0) * close_cost
            )
            for variant, net_return, turnover, cost in (
                ("lightgbm_original", original_net, report["turnover"], report["cost"]),
                (
                    "lightgbm_defended",
                    defended_net,
                    report["turnover"] * exposures + (exposures - previous_exposure).abs(),
                    report["cost"] * exposures + overlay_cost,
                ),
            ):
                metrics = risk_analysis(net_return - report["bench"], freq="day")["risk"]
                row = StressRow(
                    variant,
                    benchmark,
                    window,
                    float(metrics["annualized_return"]),
                    float(metrics["max_drawdown"]),
                    float(metrics["information_ratio"]),
                    float(turnover.sum()),
                    float(cost.sum()),
                )
                (original_rows if variant == "lightgbm_original" else defended_rows).append(row)
    return original_rows, defended_rows


def load_lightgbm_daily(
    mlruns_dir: Path, experiment_base: str, benchmark: str, window: str
) -> pd.DataFrame:
    """Load one latest LightGBM monitor scenario used only as comparison."""
    from scripts.evaluate_core_satellite_candidate import find_latest_report_artifact

    experiment = f"{experiment_base}{window}_bench{benchmark.lower()}"
    artifact = find_latest_report_artifact(mlruns_dir, experiment)
    report = pd.read_pickle(artifact).copy()
    if "turnover" not in report:
        report["turnover"] = 0.0
    return report


def _format_stress_rows(rows: list[StressRow]) -> list[str]:
    return [
        "| strategy | benchmark | window | ann_excess_cost | max_dd_cost | IR_cost | turnover | transaction_cost |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        *[
            f"| {row.variant} | {row.benchmark} | {row.window} | {row.ann_excess_cost:.2%} | "
            f"{row.max_drawdown_cost:.2%} | {row.ir_cost:.4f} | {row.turnover:.4f} | "
            f"{row.transaction_cost:.4%} |"
            for row in rows
        ],
    ]


def render_overlay_report(
    original_rows: list[StressRow],
    defended_rows: list[StressRow],
    lightgbm_original_rows: list[StressRow],
    lightgbm_defended_rows: list[StressRow],
    states: pd.DataFrame,
    checks: list[OverlayCheck],
    underlying_gate: str,
    latest_provider_session: str,
    evaluation_session: str,
    quality_absolute: tuple[float, float, float, float],
    missing_sessions: list[pd.Timestamp] | None = None,
    profile: str = "hard",
) -> str:
    """Render research evidence for quality defense and its ML comparison."""
    if profile not in EXPOSURE_PROFILES:
        raise ValueError(f"unknown trend exposure profile: {profile}")
    overlay_status = "PASS" if all(check.passed for check in checks) else "FAIL"
    original_ann, original_dd, defended_ann, defended_dd = quality_absolute
    normal_exposure = EXPOSURE_PROFILES[profile]
    exposure_rule = "/".join(
        f"{normal_exposure[state]:.0%}" for state in ("risk_on", "defensive", "cash")
    )
    state_counts = states["state"].value_counts()
    transitions = int(states["state"].ne(states["state"].shift()).sum() - (0 if states.empty else 1))
    failures = states.loc[states["failure_reason"].notna()] if "failure_reason" in states else states.iloc[0:0]
    missing_sessions = missing_sessions or []
    lines = [
        "# Quality Trend Defense Overlay Report",
        "",
        f"overlay_gate: {overlay_status}",
        f"underlying_quality_gate: {underlying_gate}",
        f"latest_provider_session: {latest_provider_session}",
        f"latest_evaluable_session: {evaluation_session}",
        f"exposure_profile: {profile}",
        f"trend_rule: SPY,QQQ SMA(200) -> {exposure_rule}",
        "signal_timing: session t exposure uses closes available through t-1",
        "cash_return_assumption: 0%",
        "",
        "This is a research-only defensive overlay; it creates no paper target.",
        "",
        "## Market States",
        "",
        "| state | sessions |",
        "| --- | ---: |",
    ]
    for state in ("risk_on", "defensive", "cash"):
        lines.append(f"| {state} | {int(state_counts.get(state, 0))} |")
    lines.extend(
        [
            "",
            f"state_transitions: {transitions}",
            f"average_cash_share: {(1.0 - states['exposure'].mean()):.2%}",
            f"recorded_fail_closed_sessions: {len(failures)}",
            "benchmark_missing_sessions: "
            + (", ".join(item.date().isoformat() for item in missing_sessions) or "none"),
            "",
            "## Reported Only Comparison",
            "",
            f"original_absolute_ann_return: {original_ann:.2%}",
            f"original_absolute_max_drawdown: {original_dd:.2%}",
            f"defended_absolute_ann_return: {defended_ann:.2%}",
            f"defended_absolute_max_drawdown: {defended_dd:.2%}",
            "",
            *_format_stress_rows([*original_rows, *defended_rows]),
            "",
            "## LightGBM Comparison",
            "",
            "scope: research_comparison_only",
            "cost_model: scaled reported net return plus aggregate exposure-transition cost; not a trade preview",
            "",
            *_format_stress_rows([*lightgbm_original_rows, *lightgbm_defended_rows]),
            "",
            "## Overlay Gate",
            "",
            "| rule | status | evidence |",
            "| --- | --- | --- |",
        ]
    )
    for check in checks:
        lines.append(f"| {check.rule} | {'PASS' if check.passed else 'FAIL'} | {check.detail} |")
    if not failures.empty:
        lines.extend(["", "## Recorded Fail-Closed Sessions", "", "| session | reason |", "| --- | --- |"])
        for session, row in failures.iterrows():
            lines.append(f"| {session.date().isoformat()} | {row['failure_reason']} |")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 reported_only 质量候选的 ETF trend defense 研究报告")
    parser.add_argument("--quality", type=Path, default=DEFAULT_QUALITY)
    parser.add_argument("--provider-uri", type=Path, default=DEFAULT_PROVIDER)
    parser.add_argument("--quality-report", type=Path, default=DEFAULT_QUALITY_REPORT)
    parser.add_argument("--lightgbm-report", type=Path, default=DEFAULT_LIGHTGBM_REPORT)
    parser.add_argument("--mlruns", type=Path, default=DEFAULT_MLRUNS)
    parser.add_argument("--experiment-base", default=DEFAULT_EXPERIMENT_BASE)
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--states-output", type=Path, default=DEFAULT_STATES)
    parser.add_argument("--full-start", default=DEFAULT_FULL_START)
    parser.add_argument("--signal-start", default=DEFAULT_SIGNAL_START)
    parser.add_argument("--end-time")
    parser.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK)
    parser.add_argument("--profile", choices=sorted(EXPOSURE_PROFILES), default="hard")
    parser.add_argument("--topk", type=int, default=9)
    parser.add_argument("--open-cost", type=float, default=0.0005)
    parser.add_argument("--close-cost", type=float, default=0.0015)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    underlying_gate = read_promotion_status(args.quality_report)
    quality = pd.read_parquet(args.quality)
    quality["session"] = pd.to_datetime(quality["session"])
    symbols = sorted(set(quality["ticker"]).union(BENCHMARKS))
    prices = load_close_prices(
        args.provider_uri,
        symbols,
        args.signal_start,
        quality["session"].max().date().isoformat(),
    )
    latest_provider_session = prices.index[-1].date().isoformat()
    evaluation_session = (
        args.end_time
        or read_monitor_evaluation_session(args.quality_report)
        or read_monitor_evaluation_session(args.lightgbm_report)
        or latest_provider_session
    )
    prices = prices.loc[prices.index <= pd.Timestamp(evaluation_session)]
    states = build_trend_states(prices[list(TREND_SYMBOLS)], lookback=args.lookback, profile=args.profile)
    targets = build_monthly_targets(quality, prices.index.tolist(), variant="reported_only", topk=args.topk)
    if targets.empty:
        raise ValueError("no targets generated for reported_only")
    maximum_holding_count = int(targets.groupby("rebalance_session")["ticker"].nunique().max())
    benchmarks = build_benchmark_returns(prices)
    original_daily = simulate_portfolio(prices, targets, args.open_cost, args.close_cost)
    defended_daily = simulate_quality_overlay(prices, targets, states, args.open_cost, args.close_cost)
    original_rows = build_stress_rows(
        original_daily, benchmarks, "reported_only", full_start=args.full_start
    )
    defended_rows = build_stress_rows(
        defended_daily, benchmarks, "reported_only_defended", full_start=args.full_start
    )
    original_ann, original_dd = summarize_absolute_returns(original_daily, args.full_start)
    defended_ann, defended_dd = summarize_absolute_returns(defended_daily, args.full_start)

    lightgbm_scenarios = {
        (benchmark, window): load_lightgbm_daily(
            args.mlruns, args.experiment_base, benchmark, window
        ).loc[lambda frame: frame.index <= pd.Timestamp(evaluation_session)]
        for benchmark in BENCHMARKS
        for window in ("full", "63d", "126d", "252d")
    }
    lightgbm_original_rows, lightgbm_defended_rows = evaluate_lightgbm_comparison(
        lightgbm_scenarios, states, args.open_cost, args.close_cost
    )
    comparison_returns = defended_daily.loc[
        defended_daily.index >= pd.Timestamp(args.full_start)
    ].index
    start_locations = prices.index.get_indexer(comparison_returns) - 1
    evaluation_states = states.reindex(prices.index[start_locations])
    checks = assess_overlay_gate(
        underlying_gate,
        original_rows,
        defended_rows,
        original_dd,
        defended_dd,
        maximum_holding_count,
        hidden_failure_count=0,
    )
    args.states_output.parent.mkdir(parents=True, exist_ok=True)
    evaluation_states.to_parquet(args.states_output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_overlay_report(
            original_rows,
            defended_rows,
            lightgbm_original_rows,
            lightgbm_defended_rows,
            evaluation_states,
            checks,
            underlying_gate,
            latest_provider_session,
            evaluation_session,
            (original_ann, original_dd, defended_ann, defended_dd),
            missing_sessions=benchmark_missing_sessions(prices),
            profile=args.profile,
        ),
        encoding="utf-8",
    )
    status = "PASS" if all(check.passed for check in checks) else "FAIL"
    print(f"Quality trend-defense report: {args.report}")
    print(f"Daily market states: {args.states_output}")
    print(f"Overlay gate: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

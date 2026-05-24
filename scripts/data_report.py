#!/usr/bin/env python3
"""Read-only Qlib data availability report.

The report is intentionally diagnostic: it reads local provider files, optionally
samples local Qlib feature coverage, and inspects workflow YAML date windows.
It does not download data or write MLflow artifacts.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_PROVIDER = Path.home() / ".qlib" / "qlib_data" / "us_data"
DEFAULT_MARKETS = ("all", "sp500", "nasdaq100")
DEFAULT_SYMBOLS = ("AAPL", "MSFT", "NVDA", "SPY")


DateRange = tuple[str | None, str | None]


@dataclass(frozen=True)
class CalendarSummary:
    start: str
    end: str
    sessions: int


@dataclass(frozen=True)
class InstrumentSummary:
    market: str
    count: int
    path: Path


@dataclass(frozen=True)
class SymbolCoverage:
    symbol: str
    start: str | None
    end: str | None
    bars: int
    note: str = ""


@dataclass(frozen=True)
class WorkflowSummary:
    path: Path
    experiment_name: str
    market: str | None
    handler_start: str | None
    handler_end: str | None
    train: DateRange
    valid: DateRange
    test: DateRange
    backtest: DateRange
    benchmark: str | None = None
    topk: int | None = None
    n_drop: int | None = None
    open_cost: float | None = None
    close_cost: float | None = None
    min_cost: float | None = None


def normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def parse_calendar(provider_uri: Path, frequency: str = "day") -> CalendarSummary:
    calendar_file = provider_uri.expanduser() / "calendars" / f"{frequency}.txt"
    lines = [line.strip() for line in calendar_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"calendar file is empty: {calendar_file}")
    return CalendarSummary(start=lines[0], end=lines[-1], sessions=len(lines))


def count_instruments(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def read_instrument_symbols(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    symbols: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        symbols.add(line.split()[0].upper())
    return symbols


def collect_instrument_summaries(provider_uri: Path, markets: Iterable[str]) -> list[InstrumentSummary]:
    instruments_dir = provider_uri.expanduser() / "instruments"
    return [
        InstrumentSummary(market=market, count=count_instruments(instruments_dir / f"{market}.txt"), path=instruments_dir / f"{market}.txt")
        for market in markets
    ]


def parse_range(value: Any) -> DateRange:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return normalize_date(value[0]), normalize_date(value[1])
    return None, None


def dig(payload: dict[str, Any], keys: Iterable[str]) -> Any:
    cursor: Any = payload
    for key in keys:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def parse_workflow(path: Path) -> WorkflowSummary:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"workflow yaml must be a mapping: {path}")

    handler = payload.get("data_handler_config") or dig(
        payload,
        ("task", "dataset", "kwargs", "handler", "kwargs"),
    )
    handler = handler if isinstance(handler, dict) else {}
    segments = dig(payload, ("task", "dataset", "kwargs", "segments"))
    segments = segments if isinstance(segments, dict) else {}
    backtest = dig(payload, ("port_analysis_config", "backtest"))
    backtest = backtest if isinstance(backtest, dict) else {}
    strategy_kwargs = dig(payload, ("port_analysis_config", "strategy", "kwargs"))
    strategy_kwargs = strategy_kwargs if isinstance(strategy_kwargs, dict) else {}
    exchange_kwargs = backtest.get("exchange_kwargs")
    exchange_kwargs = exchange_kwargs if isinstance(exchange_kwargs, dict) else {}

    market = payload.get("market") or handler.get("instruments")

    return WorkflowSummary(
        path=path,
        experiment_name=str(payload.get("experiment_name") or path.stem),
        market=str(market) if market is not None else None,
        handler_start=normalize_date(handler.get("start_time")),
        handler_end=normalize_date(handler.get("end_time")),
        train=parse_range(segments.get("train")),
        valid=parse_range(segments.get("valid")),
        test=parse_range(segments.get("test")),
        backtest=(normalize_date(backtest.get("start_time")), normalize_date(backtest.get("end_time"))),
        benchmark=str(payload.get("benchmark") or backtest.get("benchmark") or "") or None,
        topk=as_int(strategy_kwargs.get("topk")),
        n_drop=as_int(strategy_kwargs.get("n_drop")),
        open_cost=as_float(exchange_kwargs.get("open_cost")),
        close_cost=as_float(exchange_kwargs.get("close_cost")),
        min_cost=as_float(exchange_kwargs.get("min_cost")),
    )


def collect_workflows(workflows_dir: Path) -> list[WorkflowSummary]:
    return [parse_workflow(path) for path in sorted(workflows_dir.glob("*.yaml"))]


def workflow_status(workflow: WorkflowSummary, calendar_end: str | None) -> str:
    ends = [
        workflow.handler_end,
        workflow.train[1],
        workflow.valid[1],
        workflow.test[1],
        workflow.backtest[1],
    ]
    known_ends = [end for end in ends if end]
    if not calendar_end or not known_ends:
        return "UNKNOWN"
    return "EXCEEDS_CALENDAR" if max(known_ends) > calendar_end else "OK"


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def workflow_parameter_status(workflow: WorkflowSummary, provider_symbols: set[str], market_count: int | None) -> str:
    warnings: list[str] = []
    if workflow.benchmark and provider_symbols and workflow.benchmark.upper() not in provider_symbols:
        warnings.append("MISSING_BENCHMARK")
    if workflow.topk is not None and market_count:
        if workflow.topk > market_count:
            warnings.append("TOPK_GT_MARKET")
        elif workflow.topk / market_count > 0.30:
            warnings.append("HIGH_TOPK_SHARE")
    if workflow.open_cost is None or workflow.close_cost is None or workflow.min_cost is None:
        warnings.append("COST_UNKNOWN")
    return ",".join(warnings) if warnings else "OK"


def data_age_note(calendar_end: str, today: str | date | None = None) -> str:
    today_date = date.today() if today is None else date.fromisoformat(str(today))
    end_date = date.fromisoformat(calendar_end)
    days = (today_date - end_date).days
    if days < 0:
        return f"FUTURE (latest session is {-days} days after {today_date.isoformat()})"
    status = "STALE" if days > 370 else "OK"
    return f"{status} (latest session is {days} days behind {today_date.isoformat()})"


def collect_symbol_coverages(provider_uri: Path, symbols: Iterable[str]) -> list[SymbolCoverage]:
    try:
        import qlib
        from qlib.data import D
    except Exception as exc:
        return [SymbolCoverage(symbol=symbol, start=None, end=None, bars=0, note=f"qlib unavailable: {exc}") for symbol in symbols]

    provider = provider_uri.expanduser()
    try:
        qlib.init(provider_uri=str(provider), region="us")
    except Exception as exc:
        return [SymbolCoverage(symbol=symbol, start=None, end=None, bars=0, note=f"qlib init failed: {exc}") for symbol in symbols]

    coverages: list[SymbolCoverage] = []
    for symbol in symbols:
        try:
            frame = D.features([symbol], ["$close"], start_time="1900-01-01", end_time="2099-12-31")
        except Exception as exc:
            coverages.append(SymbolCoverage(symbol=symbol, start=None, end=None, bars=0, note=f"read failed: {exc}"))
            continue

        series = frame["$close"].dropna() if "$close" in frame else frame.dropna()
        if series.empty:
            coverages.append(SymbolCoverage(symbol=symbol, start=None, end=None, bars=0, note="no non-null close"))
            continue

        dates = series.index.get_level_values("datetime") if hasattr(series.index, "names") and "datetime" in series.index.names else series.index
        coverages.append(
            SymbolCoverage(
                symbol=symbol,
                start=normalize_date(dates.min()),
                end=normalize_date(dates.max()),
                bars=int(series.shape[0]),
            )
        )
    return coverages


def format_range(value: DateRange) -> str:
    start, end = value
    if not start and not end:
        return "-"
    return f"{start or '?'}..{end or '?'}"


def format_report(
    provider_uri: Path,
    calendar: CalendarSummary,
    instruments: list[InstrumentSummary],
    workflows: list[WorkflowSummary],
    symbol_coverages: list[SymbolCoverage],
    today: str | date | None = None,
) -> str:
    provider = provider_uri.expanduser()
    lines = [
        "# Qlib Data Report",
        "",
        f"provider_uri: {provider}",
        f"calendar: {calendar.start} -> {calendar.end} ({calendar.sessions} sessions)",
        f"data_age: {data_age_note(calendar.end, today=today)}",
        "",
        "## Instruments",
        "",
        "| market | count |",
        "|---|---:|",
    ]

    for item in instruments:
        lines.append(f"| {item.market} | {item.count} |")

    lines.extend(["", "## Sample Symbol Coverage", "", "| symbol | start | end | bars | note |", "|---|---|---|---:|---|"])
    if symbol_coverages:
        for item in symbol_coverages:
            lines.append(f"| {item.symbol} | {item.start or '-'} | {item.end or '-'} | {item.bars} | {item.note or '-'} |")
    else:
        lines.append("| - | - | - | 0 | skipped |")

    lines.extend(
        [
            "",
            "## Workflow Windows",
            "",
            "| workflow | experiment | market | handler_end | train | valid | test | backtest | status |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in workflows:
        lines.append(
            "| "
            + " | ".join(
                [
                    item.path.name,
                    item.experiment_name,
                    item.market or "-",
                    item.handler_end or "-",
                    format_range(item.train),
                    format_range(item.valid),
                    format_range(item.test),
                    format_range(item.backtest),
                    workflow_status(item, calendar.end),
                ]
            )
            + " |"
        )
    all_symbols = read_instrument_symbols(provider / "instruments" / "all.txt")
    market_counts = {item.market: item.count for item in instruments}
    lines.extend(
        [
            "",
            "## Workflow Parameters",
            "",
            "| workflow | benchmark | topk | n_drop | open_cost | close_cost | min_cost | status |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in workflows:
        market_count = market_counts.get(item.market or "")
        lines.append(
            "| "
            + " | ".join(
                [
                    item.path.name,
                    item.benchmark or "-",
                    str(item.topk) if item.topk is not None else "-",
                    str(item.n_drop) if item.n_drop is not None else "-",
                    str(item.open_cost) if item.open_cost is not None else "-",
                    str(item.close_cost) if item.close_cost is not None else "-",
                    str(item.min_cost) if item.min_cost is not None else "-",
                    workflow_parameter_status(item, all_symbols, market_count),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地 Qlib 数据可用性报告")
    parser.add_argument("--provider-uri", type=Path, default=DEFAULT_PROVIDER, help="Qlib provider 目录")
    parser.add_argument("--workflows-dir", type=Path, default=Path("config/qlib"), help="Qlib workflow YAML 目录")
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS), help="逗号分隔的 instrument 文件名")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="逗号分隔的覆盖率抽样标的")
    parser.add_argument("--skip-symbol-coverage", action="store_true", help="不调用 Qlib D.features，只输出文件/YAML 报告")
    return parser.parse_args()


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    args = parse_args()
    provider_uri = args.provider_uri.expanduser()
    calendar = parse_calendar(provider_uri)
    instruments = collect_instrument_summaries(provider_uri, split_csv(args.markets))
    workflows = collect_workflows(args.workflows_dir)
    symbol_coverages = [] if args.skip_symbol_coverage else collect_symbol_coverages(provider_uri, split_csv(args.symbols))
    print(format_report(provider_uri, calendar, instruments, workflows, symbol_coverages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

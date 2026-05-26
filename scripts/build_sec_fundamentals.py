#!/usr/bin/env python3
"""Build a local point-in-time SEC fundamentals warehouse for quality research."""
from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx
import pandas as pd

from us_quant.fundamentals import (
    FACT_COLUMNS,
    build_cik_mapping,
    build_daily_quality_snapshot,
    extract_canonical_facts,
    read_investable_symbols,
)


DEFAULT_PROVIDER = Path.home() / ".qlib" / "qlib_data" / "us_modern_liquid100"
DEFAULT_RAW_DIR = Path(".cache/sec/raw")
DEFAULT_OUTPUT_DIR = Path(".cache/fundamentals")
DEFAULT_REPORT = Path(".cache/reports/fundamentals_quality_latest.md")
TICKER_MAPPING_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
RETRIABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class FundamentalsBuildSummary:
    requested_symbols: list[str]
    covered_symbols: list[str]
    facts_rows: int
    snapshot_rows: int
    errors: list[str]
    facts_source: str
    facts_path: Path
    snapshot_path: Path
    report_path: Path


def validate_user_agent(user_agent: str | None) -> str:
    """Validate the SEC contact identity required before a live request."""
    value = (user_agent or "").strip()
    if not value:
        raise ValueError("SEC_USER_AGENT is required for live SEC requests")
    if "@" not in value:
        raise ValueError("SEC_USER_AGENT must include a contact email address")
    return value


def load_or_fetch_json(
    url: str,
    cache_path: Path,
    user_agent: str | None = None,
    refresh: bool = False,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    request_interval: float = 0.12,
    retries: int = 2,
) -> dict[str, Any]:
    """Read cached JSON or fetch it from SEC with a compliant request identity."""
    cache_path = Path(cache_path)
    if cache_path.is_file() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    headers = {
        "User-Agent": validate_user_agent(user_agent),
        "Accept-Encoding": "gzip, deflate",
    }

    def fetch(active_client: httpx.Client) -> dict[str, Any]:
        for attempt in range(retries + 1):
            sleep(request_interval if attempt == 0 else 0.5 * (2 ** (attempt - 1)))
            response = active_client.get(url, headers=headers)
            if response.status_code in RETRIABLE_STATUS_CODES and attempt < retries:
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError("unreachable SEC retry state")

    if client is None:
        with httpx.Client(timeout=30.0, follow_redirects=True) as owned_client:
            payload = fetch(owned_client)
    else:
        payload = fetch(client)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def read_sessions(provider_uri: Path) -> list[str]:
    path = Path(provider_uri).expanduser() / "calendars" / "day.txt"
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_symbols(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return sorted({symbol.strip().upper().replace(".", "-") for symbol in value.split(",") if symbol.strip()})


def render_quality_report(summary: FundamentalsBuildSummary, facts: pd.DataFrame, daily: pd.DataFrame) -> str:
    coverage_rows: list[str] = []
    metric_rows: list[str] = []
    for symbol in summary.requested_symbols:
        selected = facts.loc[facts["ticker"] == symbol] if not facts.empty else facts
        fields = ", ".join(sorted(selected["field"].unique())) if not selected.empty else "missing"
        latest = selected["filed_date"].max().date().isoformat() if not selected.empty else "-"
        coverage_rows.append(f"| {symbol} | {len(selected)} | {latest} | {fields} |")
        snapshots = daily.loc[daily["ticker"] == symbol] if not daily.empty else daily
        if snapshots.empty:
            metric_rows.append(f"| {symbol} | 0 | - | - | - | - |")
            continue
        metric_coverage = snapshots[["roe", "cash_conversion", "debt_to_assets"]].notna().mean().mul(100)
        latest_snapshot = snapshots.sort_values("session").iloc[-1]
        metric_rows.append(
            f"| {symbol} | {len(snapshots)} | {metric_coverage['roe']:.1f}% | "
            f"{metric_coverage['cash_conversion']:.1f}% | {metric_coverage['debt_to_assets']:.1f}% | "
            f"{latest_snapshot['fiscal_period']} |"
        )
    errors = "\n".join(f"- {item}" for item in summary.errors) or "- none"
    return "\n".join(
        [
            "# SEC Fundamentals Quality Report",
            "",
            f"requested_symbols: {len(summary.requested_symbols)}",
            f"covered_symbols: {len(summary.covered_symbols)}",
            f"normalized_fact_rows: {summary.facts_rows}",
            f"daily_snapshot_rows: {summary.snapshot_rows}",
            f"facts_source: {summary.facts_source}",
            "",
            "This report uses a current-universe survivorship bias sample; historical",
            "membership reconstruction is not yet included.",
            "",
            "## Coverage",
            "",
            "| Symbol | Fact rows | Latest filed | Canonical fields |",
            "| --- | ---: | --- | --- |",
            *coverage_rows,
            "",
            "## Daily Metric Coverage",
            "",
            "| Symbol | Sessions | ROE | Cash conversion | Debt to assets | Latest fiscal period |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
            *metric_rows,
            "",
            "Income and operating-cash-flow ratios retain each filing's reported",
            "fiscal-period span. A cross-symbol quality ranking requires",
            "period-normalized metrics, such as trailing-twelve-month values.",
            "",
            "## Retrieval Errors",
            "",
            errors,
            "",
        ]
    )


def build_fundamentals_dataset(
    provider_uri: Path = DEFAULT_PROVIDER,
    raw_dir: Path = DEFAULT_RAW_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    symbols: Iterable[str] | None = None,
    market: str = "liquid100",
    user_agent: str | None = None,
    refresh: bool = False,
    rebuild_facts: bool = False,
    client: httpx.Client | None = None,
) -> FundamentalsBuildSummary:
    """Build cached normalized facts and daily snapshots for requested equities."""
    investable = read_investable_symbols(provider_uri, market=market)
    if symbols is None:
        selected_symbols = investable
    else:
        requested = sorted({symbol.strip().upper().replace(".", "-") for symbol in symbols})
        unknown = sorted(set(requested) - set(investable))
        if unknown:
            raise ValueError(f"symbols not found in investable provider universe: {', '.join(unknown)}")
        selected_symbols = requested

    output_dir = Path(output_dir)
    facts_path = output_dir / "sec_facts.parquet"
    errors: list[str] = []
    facts_source = "raw SEC JSON cache"
    cached_facts = pd.read_parquet(facts_path) if facts_path.is_file() and not refresh and not rebuild_facts else None
    if cached_facts is not None and sorted(cached_facts["ticker"].unique().tolist()) == selected_symbols:
        facts = cached_facts
        facts_source = "normalized parquet cache"
    else:
        raw_dir = Path(raw_dir)
        mapping_payload = load_or_fetch_json(
            TICKER_MAPPING_URL,
            raw_dir / "ticker_mapping.json",
            user_agent=user_agent,
            refresh=refresh,
            client=client,
        )
        ticker_to_cik = build_cik_mapping(mapping_payload)
        frames: list[pd.DataFrame] = []
        for symbol in selected_symbols:
            cik = ticker_to_cik.get(symbol)
            if cik is None:
                errors.append(f"{symbol}: missing SEC ticker-to-CIK mapping")
                continue
            issuer_dir = raw_dir / cik
            try:
                payload = load_or_fetch_json(
                    COMPANYFACTS_URL.format(cik=cik),
                    issuer_dir / "companyfacts.json",
                    user_agent=user_agent,
                    refresh=refresh,
                    client=client,
                )
                load_or_fetch_json(
                    SUBMISSIONS_URL.format(cik=cik),
                    issuer_dir / "submissions.json",
                    user_agent=user_agent,
                    refresh=refresh,
                    client=client,
                )
                normalized = extract_canonical_facts(symbol, cik, payload)
                if normalized.empty:
                    errors.append(f"{symbol}: no canonical SEC facts found")
                else:
                    frames.append(normalized)
            except (OSError, httpx.HTTPError, json.JSONDecodeError) as exc:
                errors.append(f"{symbol}: {exc}")
        facts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FACT_COLUMNS)

    daily = build_daily_quality_snapshot(facts, read_sessions(provider_uri))
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / "quality_daily.parquet"
    facts.to_parquet(facts_path, index=False)
    daily.to_parquet(snapshot_path, index=False)
    summary = FundamentalsBuildSummary(
        requested_symbols=selected_symbols,
        covered_symbols=sorted(facts["ticker"].unique().tolist()) if not facts.empty else [],
        facts_rows=len(facts),
        snapshot_rows=len(daily),
        errors=errors,
        facts_source=facts_source,
        facts_path=facts_path,
        snapshot_path=snapshot_path,
        report_path=Path(report_path),
    )
    summary.report_path.parent.mkdir(parents=True, exist_ok=True)
    summary.report_path.write_text(render_quality_report(summary, facts, daily), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 SEC point-in-time 基本面研究数据仓")
    parser.add_argument("--provider-uri", type=Path, default=DEFAULT_PROVIDER, help="现代 Qlib provider 路径")
    parser.add_argument("--market", default="liquid100", help="provider instrument 文件名")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="SEC JSON 本地缓存目录")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Parquet 输出目录")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="覆盖率报告路径")
    parser.add_argument("--symbols", help="逗号分隔的小范围标的，例如 AAPL,MSFT,NVDA")
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT"), help="包含联系邮箱的 SEC User-Agent")
    parser.add_argument("--refresh", action="store_true", help="忽略已有缓存并重新请求 SEC")
    parser.add_argument("--rebuild-facts", action="store_true", help="从已有原始 SEC JSON 重新标准化事实，不重新联网")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = build_fundamentals_dataset(
            provider_uri=args.provider_uri,
            raw_dir=args.raw_dir,
            output_dir=args.output_dir,
            report_path=args.report,
            symbols=parse_symbols(args.symbols),
            market=args.market,
            user_agent=args.user_agent,
            refresh=args.refresh,
            rebuild_facts=args.rebuild_facts,
        )
    except (OSError, ValueError, httpx.HTTPError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Facts: {summary.facts_path} ({summary.facts_rows} rows)")
    print(f"Snapshots: {summary.snapshot_path} ({summary.snapshot_rows} rows)")
    print(f"Report: {summary.report_path}")
    if summary.errors:
        print(f"WARN: {len(summary.errors)} symbols with missing/error coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

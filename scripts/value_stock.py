#!/usr/bin/env python3
"""Run a small stock valuation probe.

Prefer --source json for deterministic research. The Yahoo source is optional
and may fail under rate limits.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from us_quant.valuation import build_stock, fetch_yahoo_stock, run_valuation


def load_json_stock(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    return build_stock(data)


def format_money(value: float, currency: str) -> str:
    if value == 0:
        return "n/a"
    return f"{currency} {value:,.2f}"


def print_report(report) -> None:
    title = f"{report.ticker} valuation probe"
    if report.name:
        title += f" - {report.name}"
    print(title)
    print(f"source={report.source} price={format_money(report.current_price, report.currency)}")
    if report.warnings:
        print("warnings=" + "; ".join(report.warnings))
    if report.errors:
        print("errors=" + "; ".join(report.errors))
    print()
    print(f"{'method_key':18s} {'fair_value':>16s} {'margin':>10s} {'confidence':>10s}  assessment")
    print("-" * 84)
    for item in report.results:
        print(
            f"{item.method_key:18s} "
            f"{format_money(item.fair_value, report.currency):>16s} "
            f"{item.premium_discount:>9.1f}% "
            f"{item.confidence:>10s}  "
            f"{item.assessment}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="轻量股票估值探针")
    parser.add_argument("symbol", nargs="?", help="股票代码；Yahoo 模式必填")
    parser.add_argument("--source", choices=["json", "yahoo"], default="yahoo")
    parser.add_argument("--input-json", type=Path, help="JSON 股票基本面输入")
    parser.add_argument(
        "--methods",
        default=None,
        help="逗号分隔估值方法；默认使用小范围探针方法集",
    )
    parser.add_argument("--output-json", type=Path, help="可选：保存结构化报告")
    args = parser.parse_args()

    try:
        if args.source == "json":
            if args.input_json is None:
                print("--source json requires --input-json", file=sys.stderr)
                return 2
            stock = load_json_stock(args.input_json)
            source = f"json:{args.input_json}"
        else:
            if not args.symbol:
                print("--source yahoo requires symbol", file=sys.stderr)
                return 2
            stock, errors = fetch_yahoo_stock(args.symbol)
            if stock is None:
                print(f"Yahoo fetch failed for {args.symbol.upper()}: {'; '.join(errors)}", file=sys.stderr)
                return 1
            source = "yahoo"

        report = run_valuation(stock, methods=args.methods, source=source)
        print_report(report)

        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        return 0
    except Exception as exc:
        print(f"valuation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


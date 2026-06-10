#!/usr/bin/env python3
"""Export the reported-only quality candidate as a protected dry-run preview."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from us_quant.rebalance import reconcile_positions


DEFAULT_HOLDINGS = Path(".cache/quality_satellite/latest_holdings.parquet")
DEFAULT_REPORT = Path(".cache/reports/quality_satellite_monitor_latest.md")
DEFAULT_OUTPUT = Path(".cache/signals/quality_reported_only_candidate_preview.json")
VARIANT = "reported_only"
STRATEGY = "quality_reported_only_candidate"


def read_promotion_status(report: Path) -> str:
    """Return explicit PASS or FAIL from a quality monitor report."""
    if not report.is_file():
        raise FileNotFoundError(f"quality monitor report not found: {report}")
    for line in report.read_text(encoding="utf-8").splitlines():
        if line.startswith("promotion_gate:"):
            status = line.split(":", 1)[1].strip()
            if status in {"PASS", "FAIL"}:
                return status
            break
    raise ValueError(f"quality monitor report has no valid promotion_gate status: {report}")


def build_preview_payload(
    holdings: pd.DataFrame,
    source_holdings: Path,
    source_report: Path,
    budget: float,
    max_holdings: int = 9,
    current_positions: Mapping[str, float] | None = None,
    min_trade_notional: float = 1.0,
) -> dict[str, Any]:
    """Export only the latest reported_only target as dry-run observation orders."""
    if budget <= 0:
        raise ValueError("budget must be positive")
    required = {
        "variant",
        "ticker",
        "target_weight",
        "rebalance_session",
        "debt_to_assets_source",
    }
    missing = required.difference(holdings.columns)
    if missing:
        raise ValueError(f"quality holdings missing columns: {', '.join(sorted(missing))}")

    selected = holdings.loc[holdings["variant"] == VARIANT].copy()
    if selected.empty:
        raise ValueError("reported_only holdings are empty")
    selected["rebalance_session"] = pd.to_datetime(selected["rebalance_session"])
    latest_session = selected["rebalance_session"].max()
    selected = selected.loc[selected["rebalance_session"] == latest_session].copy()
    if selected["ticker"].duplicated().any():
        raise ValueError("reported_only holdings contain duplicate tickers")
    if len(selected) > max_holdings:
        raise ValueError(f"reported_only holdings exceed maximum of {max_holdings}")
    if not selected["debt_to_assets_source"].eq("reported").all():
        raise ValueError("reported_only preview requires reported leverage sources only")
    if selected["target_weight"].isna().any() or (selected["target_weight"] <= 0).any():
        raise ValueError("reported_only holdings require positive target weights")
    total_weight = float(selected["target_weight"].sum())
    if total_weight <= 0:
        raise ValueError("reported_only holdings have no investable target weight")

    selected = selected.sort_values(
        ["target_weight", "ticker"], ascending=[False, True], kind="mergesort"
    )
    target_weights = {
        str(row.ticker): float(row.target_weight) / total_weight
        for row in selected.itertuples()
    }
    if current_positions is None:
        orders = [
            {
                "symbol": symbol,
                "side": "buy",
                "notional": round(budget * weight, 2),
            }
            for symbol, weight in sorted(target_weights.items(), key=lambda item: (-item[1], item[0]))
        ]
    else:
        orders = reconcile_positions(
            current_positions,
            target_weights,
            budget,
            min_trade_notional=min_trade_notional,
        )
    payload: dict[str, Any] = {
        "version": 1,
        "dry_run_only": True,
        "date": latest_session.date().isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": STRATEGY,
        "variant": VARIANT,
        "source_holdings_artifact": str(source_holdings),
        "source_report": str(source_report),
        "preview_budget": budget,
        "target_weights": target_weights,
        "rebalance": current_positions is not None,
        "holding_count": len(target_weights),
        "orders": orders,
    }
    if current_positions is not None:
        payload["current_positions"] = {
            symbol: float(value) for symbol, value in current_positions.items()
        }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出 reported_only 质量候选的 paper dry-run 观察单")
    parser.add_argument("--holdings", type=Path, default=DEFAULT_HOLDINGS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--budget", type=float, default=1_000.0)
    parser.add_argument("--max-holdings", type=int, default=9)
    parser.add_argument(
        "--current-positions",
        type=Path,
        help="Optional JSON map of symbol -> current market value for rebalance orders",
    )
    parser.add_argument("--min-trade-notional", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status = read_promotion_status(args.report)
    if status != "PASS":
        raise ValueError("quality monitor promotion gate must be PASS before preview export")
    current_positions = None
    if args.current_positions:
        current_positions = json.loads(args.current_positions.read_text(encoding="utf-8"))
    payload = build_preview_payload(
        pd.read_parquet(args.holdings),
        args.holdings,
        args.report,
        args.budget,
        max_holdings=args.max_holdings,
        current_positions=current_positions,
        min_trade_notional=args.min_trade_notional,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Quality candidate preview: {args.output}")
    print(
        f"Target rebalance: {payload['date']} | holdings: {payload['holding_count']} | "
        "dry_run_only: true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

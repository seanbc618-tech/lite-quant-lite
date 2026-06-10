#!/usr/bin/env python3
"""Export the monitored modern candidate portfolio as a dry-run-only preview."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.summarize_mlruns import read_meta
from us_quant.rebalance import reconcile_positions


DEFAULT_EXPERIMENT = (
    "lightgbm_alpha158_liquid100_modern_low_turnover_candidate_deterministic_monitor_full_benchspy"
)
DEFAULT_OUTPUT = Path(".cache/signals/modern_low_candidate_preview.json")


def find_latest_positions_artifact(mlruns_dir: Path, experiment_name: str) -> Path:
    candidates: list[tuple[int, Path]] = []
    for experiment_dir in mlruns_dir.glob("*"):
        if not experiment_dir.is_dir() or read_meta(experiment_dir / "meta.yaml").get("name") != experiment_name:
            continue
        for run_dir in experiment_dir.glob("*"):
            meta = read_meta(run_dir / "meta.yaml")
            artifact = run_dir / "artifacts" / "portfolio_analysis" / "positions_normal_1day.pkl"
            if meta.get("status") == "3" and artifact.is_file():
                candidates.append((int(meta.get("end_time") or 0), artifact))
    if not candidates:
        raise FileNotFoundError(f"no finished positions artifact found for experiment: {experiment_name}")
    return max(candidates, key=lambda item: (item[0], str(item[1])))[1]


def extract_weighted_holdings(snapshot: Any) -> list[tuple[str, float]]:
    if hasattr(snapshot, "get_stock_weight_dict"):
        return [
            (str(symbol), float(weight))
            for symbol, weight in snapshot.get_stock_weight_dict().items()
            if float(weight) > 0
        ]
    position = snapshot.get("position", {})
    return [
        (symbol, float(details["weight"]))
        for symbol, details in position.items()
        if isinstance(details, dict) and float(details.get("amount", 0)) > 0 and float(details.get("weight", 0)) > 0
    ]


def build_target_weights(
    holdings: list[tuple[str, float]],
    *,
    core_symbol: str | None = None,
    core_weight: float = 0.0,
) -> dict[str, float]:
    if core_symbol is None and core_weight != 0:
        raise ValueError("core_symbol is required when core_weight is set")
    if core_symbol is not None and not 0 < core_weight < 1:
        raise ValueError("core_weight must be between 0 and 1")
    invested_weight = sum(weight for _, weight in holdings)
    if invested_weight <= 0:
        raise ValueError("latest portfolio has no investable holdings")
    satellite_weight = 1 - core_weight if core_symbol else 1
    target_weights = {
        symbol: satellite_weight * weight / invested_weight
        for symbol, weight in holdings
    }
    if core_symbol:
        target_weights[core_symbol] = core_weight
    return target_weights


def build_preview_payload(
    positions: dict[Any, Any],
    source_artifact: Path,
    budget: float,
    core_symbol: str | None = None,
    core_weight: float = 0.0,
    current_positions: Mapping[str, float] | None = None,
    min_trade_notional: float = 1.0,
) -> dict[str, Any]:
    if budget <= 0:
        raise ValueError("budget must be positive")
    if core_symbol is None and core_weight != 0:
        raise ValueError("core_symbol is required when core_weight is set")
    if core_symbol is not None and not 0 < core_weight < 1:
        raise ValueError("core_weight must be between 0 and 1")
    if not positions:
        raise ValueError("positions artifact is empty")
    latest_date = max(positions)
    holdings = extract_weighted_holdings(positions[latest_date])
    if not holdings:
        raise ValueError("latest portfolio has no investable holdings")
    target_weights = build_target_weights(
        holdings,
        core_symbol=core_symbol,
        core_weight=core_weight,
    )
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
    strategy = "modern_low_turnover_candidate"
    allocation: dict[str, Any] | None = None
    if core_symbol:
        strategy = "modern_low_qqq_core_satellite_candidate"
        allocation = {
            "core_symbol": core_symbol,
            "core_weight": core_weight,
            "satellite_weight": 1 - core_weight,
        }
    payload = {
        "version": 1,
        "dry_run_only": True,
        "date": latest_date.strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": strategy,
        "source_artifact": str(source_artifact),
        "preview_budget": budget,
        "target_weights": target_weights,
        "rebalance": current_positions is not None,
        "orders": orders,
    }
    if allocation is not None:
        payload["allocation"] = allocation
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出现代低换手候选的 paper dry-run 观察单")
    parser.add_argument("--mlruns", type=Path, default=Path("mlruns"))
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--positions-artifact", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--budget", type=float, default=10_000.0)
    parser.add_argument("--core-symbol")
    parser.add_argument("--core-weight", type=float, default=0.0)
    parser.add_argument(
        "--current-positions",
        type=Path,
        help="Optional JSON map of symbol -> current market value for rebalance orders",
    )
    parser.add_argument("--min-trade-notional", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = args.positions_artifact or find_latest_positions_artifact(args.mlruns, args.experiment_name)
    with artifact.open("rb") as handle:
        positions = pickle.load(handle)
    current_positions = None
    if args.current_positions:
        current_positions = json.loads(args.current_positions.read_text(encoding="utf-8"))
    payload = build_preview_payload(
        positions,
        artifact,
        args.budget,
        core_symbol=args.core_symbol,
        core_weight=args.core_weight,
        current_positions=current_positions,
        min_trade_notional=args.min_trade_notional,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Candidate preview: {args.output}")
    print(f"Target date: {payload['date']} | holdings: {len(payload['orders'])} | dry_run_only: true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

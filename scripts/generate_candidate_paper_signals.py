#!/usr/bin/env python3
"""Export the monitored modern candidate portfolio as a dry-run-only preview."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.summarize_mlruns import read_meta


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


def build_preview_payload(positions: dict[Any, Any], source_artifact: Path, budget: float) -> dict[str, Any]:
    if budget <= 0:
        raise ValueError("budget must be positive")
    if not positions:
        raise ValueError("positions artifact is empty")
    latest_date = max(positions)
    holdings = extract_weighted_holdings(positions[latest_date])
    if not holdings:
        raise ValueError("latest portfolio has no investable holdings")
    invested_weight = sum(weight for _, weight in holdings)
    orders = [
        {
            "symbol": symbol,
            "side": "buy",
            "notional": round(budget * weight / invested_weight, 2),
        }
        for symbol, weight in sorted(holdings, key=lambda item: (-item[1], item[0]))
    ]
    return {
        "version": 1,
        "dry_run_only": True,
        "date": latest_date.strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": "modern_low_turnover_candidate",
        "source_artifact": str(source_artifact),
        "preview_budget": budget,
        "orders": orders,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出现代低换手候选的 paper dry-run 观察单")
    parser.add_argument("--mlruns", type=Path, default=Path("mlruns"))
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--positions-artifact", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--budget", type=float, default=10_000.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = args.positions_artifact or find_latest_positions_artifact(args.mlruns, args.experiment_name)
    with artifact.open("rb") as handle:
        positions = pickle.load(handle)
    payload = build_preview_payload(positions, artifact, args.budget)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Candidate preview: {args.output}")
    print(f"Target date: {payload['date']} | holdings: {len(payload['orders'])} | dry_run_only: true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

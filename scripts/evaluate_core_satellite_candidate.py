#!/usr/bin/env python3
"""Evaluate a passive QQQ core plus monitored LightGBM satellite portfolio."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from qlib.contrib.evaluate import risk_analysis

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.summarize_mlruns import read_meta


DEFAULT_EXPERIMENT_BASE = "lightgbm_alpha158_liquid100_modern_low_turnover_candidate_deterministic_monitor_"
DEFAULT_OUTPUT = Path(".cache/reports/modern_core_satellite_monitor_latest.md")
DEFAULT_WINDOWS = ("full", "63d", "126d", "252d")
DEFAULT_BENCHMARKS = ("SPY", "QQQ")


@dataclass(frozen=True)
class CoreSatelliteRow:
    benchmark: str
    window: str
    ann_excess_cost: float
    max_drawdown_cost: float
    ir_cost: float


def combined_excess_returns(
    satellite_report: pd.DataFrame,
    core_return: pd.Series,
    alpha_weight: float,
    core_entry_cost: float,
) -> pd.Series:
    if not 0 < alpha_weight < 1:
        raise ValueError("alpha_weight must be between 0 and 1")
    core = core_return.reindex(satellite_report.index)
    if core.isna().any():
        raise ValueError("core return series does not cover satellite dates")

    satellite_net = satellite_report["return"] - satellite_report["cost"]
    core_cost = pd.Series(0.0, index=core.index)
    entry_index = 1 if len(core_cost) > 1 else 0
    core_cost.iloc[entry_index] = core_entry_cost
    core_net = core - core_cost

    satellite_value = alpha_weight * (1 + satellite_net).cumprod()
    core_value = (1 - alpha_weight) * (1 + core_net).cumprod()
    combined_value = satellite_value + core_value
    combined_return = combined_value.pct_change()
    combined_return.iloc[0] = alpha_weight * satellite_net.iloc[0] + (1 - alpha_weight) * core_net.iloc[0]
    return combined_return - satellite_report["bench"]


def find_latest_report_artifact(mlruns_dir: Path, experiment_name: str) -> Path:
    candidates: list[tuple[int, Path]] = []
    for experiment_dir in mlruns_dir.glob("*"):
        if not experiment_dir.is_dir() or read_meta(experiment_dir / "meta.yaml").get("name") != experiment_name:
            continue
        for run_dir in experiment_dir.glob("*"):
            meta = read_meta(run_dir / "meta.yaml")
            artifact = run_dir / "artifacts" / "portfolio_analysis" / "report_normal_1day.pkl"
            if meta.get("status") == "3" and artifact.is_file():
                candidates.append((int(meta.get("end_time") or 0), artifact))
    if not candidates:
        raise FileNotFoundError(f"no finished report artifact found for experiment: {experiment_name}")
    return max(candidates, key=lambda item: (item[0], str(item[1])))[1]


def experiment_name(base: str, window: str, benchmark: str) -> str:
    return f"{base}{window}_bench{benchmark.lower()}"


def evaluate_rows(
    mlruns_dir: Path,
    experiment_base: str,
    alpha_weight: float,
    core_entry_cost: float,
    core_symbol: str = "QQQ",
) -> list[CoreSatelliteRow]:
    rows: list[CoreSatelliteRow] = []
    for benchmark in DEFAULT_BENCHMARKS:
        for window in DEFAULT_WINDOWS:
            satellite = pd.read_pickle(find_latest_report_artifact(mlruns_dir, experiment_name(experiment_base, window, benchmark)))
            core = pd.read_pickle(find_latest_report_artifact(mlruns_dir, experiment_name(experiment_base, window, core_symbol)))
            excess = combined_excess_returns(satellite, core["bench"], alpha_weight, core_entry_cost)
            metrics = risk_analysis(excess, freq="day")["risk"]
            rows.append(
                CoreSatelliteRow(
                    benchmark=benchmark,
                    window=window,
                    ann_excess_cost=float(metrics["annualized_return"]),
                    max_drawdown_cost=float(metrics["max_drawdown"]),
                    ir_cost=float(metrics["information_ratio"]),
                )
            )
    return rows


def render_core_satellite_report(
    rows: list[CoreSatelliteRow],
    alpha_weight: float,
    core_symbol: str,
) -> str:
    lines = [
        "# Modern Core-Satellite Candidate Monitor",
        "",
        f"core_weight: {(1 - alpha_weight) * 100:.2f}% {core_symbol}",
        f"satellite_weight: {alpha_weight * 100:.2f}% LightGBM low-turnover candidate",
        "allocation_model: independently growing sleeves without daily rebalancing",
        "",
        "This is a paper/research stress report, not an execution approval.",
        "",
        "| benchmark | window | ann_excess_cost | max_dd_cost | IR_cost |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.benchmark} | {row.window} | {row.ann_excess_cost * 100:.2f}% | "
            f"{row.max_drawdown_cost * 100:.2f}% | {row.ir_cost:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="评估 QQQ 核心仓 + LightGBM 卫星仓的 paper 候选")
    parser.add_argument("--mlruns", type=Path, default=Path("mlruns"))
    parser.add_argument("--experiment-base", default=DEFAULT_EXPERIMENT_BASE)
    parser.add_argument("--alpha-weight", type=float, default=0.4)
    parser.add_argument("--core-symbol", default="QQQ")
    parser.add_argument("--core-entry-cost", type=float, default=0.0005)
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = evaluate_rows(args.mlruns, args.experiment_base, args.alpha_weight, args.core_entry_cost, args.core_symbol)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_core_satellite_report(rows, args.alpha_weight, args.core_symbol), encoding="utf-8")
    print(f"Core-satellite report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

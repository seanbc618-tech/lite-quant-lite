#!/usr/bin/env python3
"""Summarize local MLflow file-store runs produced by Qlib workflows."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


STATUS_MAP = {
    "1": "SCHEDULED",
    "2": "RUNNING",
    "3": "FINISHED",
    "4": "FAILED",
    "5": "KILLED",
}

METRIC_PATHS = {
    "ic": "IC",
    "rank_ic": "Rank IC",
    "ann_excess_cost": "1day.excess_return_with_cost.annualized_return",
    "max_drawdown_cost": "1day.excess_return_with_cost.max_drawdown",
    "ir_cost": "1day.excess_return_with_cost.information_ratio",
    "ann_excess_no_cost": "1day.excess_return_without_cost.annualized_return",
}


@dataclass(frozen=True)
class RunSummary:
    experiment: str
    run_id: str
    status: str
    command: str
    ic: float | None = None
    rank_ic: float | None = None
    ann_excess_cost: float | None = None
    max_drawdown_cost: float | None = None
    ir_cost: float | None = None
    ann_excess_no_cost: float | None = None


def read_meta(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    if not path.is_file():
        return meta
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    return meta


def read_text_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def read_latest_metric(path: Path) -> float | None:
    if not path.is_file():
        return None
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    parts = lines[-1].split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[1])
    except ValueError:
        return None


def collect_runs(mlruns_dir: Path) -> list[RunSummary]:
    rows: list[RunSummary] = []
    if not mlruns_dir.is_dir():
        return rows

    for exp_dir in sorted(path for path in mlruns_dir.iterdir() if path.is_dir()):
        exp_meta = read_meta(exp_dir / "meta.yaml")
        experiment = exp_meta.get("name", exp_dir.name)
        for run_dir in sorted(path for path in exp_dir.iterdir() if path.is_dir()):
            run_meta = read_meta(run_dir / "meta.yaml")
            if not run_meta:
                continue
            raw_status = run_meta.get("status", "")
            metrics = {
                key: read_latest_metric(run_dir / "metrics" / metric_name)
                for key, metric_name in METRIC_PATHS.items()
            }
            rows.append(
                RunSummary(
                    experiment=experiment,
                    run_id=run_dir.name,
                    status=STATUS_MAP.get(raw_status, raw_status or "UNKNOWN"),
                    command=read_text_file(run_dir / "params" / "cmd-sys.argv"),
                    **metrics,
                )
            )

    return sorted(
        rows,
        key=lambda row: (
            row.ann_excess_cost is None,
            -(row.ann_excess_cost or float("-inf")),
            row.experiment,
            row.run_id,
        ),
    )


def fmt_float(value: float | None, digits: int = 4) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def fmt_pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.2f}%"


def short_run_id(run_id: str) -> str:
    return run_id[:8]


def format_markdown_table(rows: list[RunSummary]) -> str:
    header = (
        "| experiment | status | run_id | IC | Rank IC | ann_excess_cost | "
        "max_dd_cost | IR_cost | ann_excess_no_cost | command |"
    )
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"
    lines = [header, sep]
    for row in rows:
        command = row.command.replace("|", "\\|")
        lines.append(
            "| "
            + " | ".join(
                [
                    row.experiment,
                    row.status,
                    short_run_id(row.run_id),
                    fmt_float(row.ic),
                    fmt_float(row.rank_ic),
                    fmt_pct(row.ann_excess_cost),
                    fmt_pct(row.max_drawdown_cost),
                    fmt_float(row.ir_cost),
                    fmt_pct(row.ann_excess_no_cost),
                    command,
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总本地 MLflow/Qlib 实验结果")
    parser.add_argument("--mlruns", type=Path, default=Path("mlruns"), help="MLflow file-store 目录")
    args = parser.parse_args()

    rows = collect_runs(args.mlruns)
    if not rows:
        print(f"No runs found under {args.mlruns}")
        return 1
    print(format_markdown_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


#!/usr/bin/env python3
"""Run latest-date rolling stress scenarios for the modern low-turnover candidate."""
from __future__ import annotations

import argparse
import copy
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.summarize_mlruns import RunSummary, collect_runs, format_markdown_table


DEFAULT_BASE_CONFIG = Path("config/qlib/workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml")
DEFAULT_PROVIDER = Path.home() / ".qlib" / "qlib_data" / "us_modern_liquid100"
DEFAULT_OUTPUT_DIR = Path(".cache/qlib_monitor/modern_low")
DEFAULT_REPORT = Path(".cache/reports/modern_low_monitor_latest.md")
DEFAULT_BENCHMARKS = ("SPY", "QQQ")
DEFAULT_WINDOWS = ("full", "63d", "126d", "252d")


@dataclass(frozen=True)
class MonitorScenario:
    benchmark: str
    window: str
    start_time: str
    end_time: str


def read_calendar(provider_uri: Path) -> list[str]:
    path = provider_uri.expanduser() / "calendars" / "day.txt"
    sessions = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not sessions:
        raise ValueError(f"calendar is empty: {path}")
    return sessions


def build_monitor_scenarios(
    calendar: list[str],
    benchmarks: Iterable[str],
    windows: Iterable[str],
    full_start: str,
) -> list[MonitorScenario]:
    if len(calendar) < 2:
        raise ValueError("calendar must contain a future step after the evaluation session")
    # Qlib's daily simulator consumes one following calendar step to execute
    # the final trade decision, so a portfolio backtest cannot end at calendar[-1].
    end_time = calendar[-2]
    executable_calendar = calendar[:-1]
    scenarios: list[MonitorScenario] = []
    for benchmark in benchmarks:
        for window in windows:
            if window == "full":
                start_time = full_start
            elif window.endswith("d") and window[:-1].isdigit():
                count = int(window[:-1])
                if count < 1 or count > len(executable_calendar):
                    raise ValueError(f"window is outside calendar coverage: {window}")
                start_time = executable_calendar[-count]
            else:
                raise ValueError(f"unknown monitor window: {window}")
            scenarios.append(MonitorScenario(benchmark.upper(), window, start_time, end_time))
    return scenarios


def experiment_name(base_name: str, scenario: MonitorScenario) -> str:
    return f"{base_name}_monitor_{scenario.window}_bench{scenario.benchmark.lower()}"


def apply_monitor_config(base_config: dict, scenario: MonitorScenario) -> dict:
    config = copy.deepcopy(base_config)
    base_name = str(config.get("experiment_name") or "modern_low_candidate")
    config["experiment_name"] = experiment_name(base_name, scenario)
    config["benchmark"] = scenario.benchmark
    config["data_handler_config"]["end_time"] = scenario.end_time

    dataset = config["task"]["dataset"]["kwargs"]
    dataset["handler"]["kwargs"]["end_time"] = scenario.end_time
    dataset["segments"]["test"] = [scenario.start_time, scenario.end_time]

    backtest = config["port_analysis_config"]["backtest"]
    backtest["benchmark"] = scenario.benchmark
    backtest["start_time"] = scenario.start_time
    backtest["end_time"] = scenario.end_time
    return config


def workflow_path(output_dir: Path, scenario: MonitorScenario) -> Path:
    return output_dir / f"{scenario.window}_bench{scenario.benchmark.lower()}.yaml"


def write_workflow(base_config: dict, output_dir: Path, scenario: MonitorScenario) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = workflow_path(output_dir, scenario)
    payload = apply_monitor_config(base_config, scenario)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def run_workflow(path: Path) -> int:
    command = [sys.executable, "-m", "qlib.cli.run", str(path)]
    print("Running:", " ".join(command), flush=True)
    return subprocess.call(command)


def latest_rows_for_experiments(rows: list[RunSummary], experiments: Iterable[str]) -> list[RunSummary]:
    selected: list[RunSummary] = []
    for experiment in experiments:
        matching = [row for row in rows if row.experiment == experiment]
        finished = [row for row in matching if row.status == "FINISHED"]
        candidates = finished or matching
        if candidates:
            selected.append(max(candidates, key=lambda row: (row.end_time, row.run_id)))
    return selected


def render_monitor_report(rows: list[RunSummary], latest_session: str, evaluation_session: str) -> str:
    return "\n".join(
        [
            "# Modern Low-Turnover Candidate Monitor",
            "",
            f"latest_provider_session: {latest_session}",
            f"latest_evaluable_session: {evaluation_session}",
            "evaluation_lag: 1 trading session (required by Qlib execution calendar)",
            "",
            "This is a paper/research stress report, not an execution approval.",
            "",
            format_markdown_table(rows),
            "",
        ]
    )


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"workflow config must be a mapping: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行现代低换手候选的滚动压力测试")
    parser.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG)
    parser.add_argument("--provider-uri", type=Path, default=DEFAULT_PROVIDER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--mlruns", type=Path, default=Path("mlruns"))
    parser.add_argument("--benchmarks", default=",".join(DEFAULT_BENCHMARKS))
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    parser.add_argument("--dry-run", action="store_true", help="只生成动态 workflow 和报告，不运行 Qlib")
    parser.add_argument("--keep-going", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    calendar = read_calendar(args.provider_uri)
    base_config = load_yaml(args.base_config)
    full_start = str(base_config["task"]["dataset"]["kwargs"]["segments"]["test"][0])
    scenarios = build_monitor_scenarios(
        calendar,
        benchmarks=parse_list(args.benchmarks),
        windows=parse_list(args.windows),
        full_start=full_start,
    )
    failures: list[Path] = []
    names: list[str] = []
    for index, scenario in enumerate(scenarios, start=1):
        path = write_workflow(base_config, args.output_dir, scenario)
        names.append(experiment_name(str(base_config["experiment_name"]), scenario))
        print(f"[{index}/{len(scenarios)}] {path}", flush=True)
        if not args.dry_run:
            code = run_workflow(path)
            if code != 0:
                failures.append(path)
                if not args.keep_going:
                    return code

    rows = latest_rows_for_experiments(collect_runs(args.mlruns), names)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_monitor_report(rows, calendar[-1], scenarios[0].end_time), encoding="utf-8")
    print(f"Monitor report: {args.report}")
    if failures:
        print("Failed workflows:")
        for path in failures:
            print(f"- {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

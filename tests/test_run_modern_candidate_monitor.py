from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import yaml

from scripts.run_modern_candidate_monitor import (
    MonitorScenario,
    apply_monitor_config,
    build_monitor_scenarios,
    latest_rows_for_experiments,
    render_monitor_report,
)
from scripts.summarize_mlruns import RunSummary


def test_monitor_script_can_start_from_cli_entrypoint():
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [sys.executable, "scripts/run_modern_candidate_monitor.py", "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_build_monitor_scenarios_reserves_next_session_for_qlib_execution():
    calendar = [f"2026-01-{day:02d}" for day in range(1, 10)]

    scenarios = build_monitor_scenarios(
        calendar,
        benchmarks=["SPY", "QQQ"],
        windows=["full", "3d"],
        full_start="2025-01-02",
    )

    assert scenarios == [
        MonitorScenario("SPY", "full", "2025-01-02", "2026-01-08"),
        MonitorScenario("SPY", "3d", "2026-01-06", "2026-01-08"),
        MonitorScenario("QQQ", "full", "2025-01-02", "2026-01-08"),
        MonitorScenario("QQQ", "3d", "2026-01-06", "2026-01-08"),
    ]


def test_apply_monitor_config_updates_evaluation_horizon_and_benchmark():
    base = yaml.safe_load(
        """
experiment_name: candidate
benchmark: SPY
data_handler_config:
  start_time: "2020-11-02"
  end_time: "2026-05-15"
port_analysis_config:
  backtest:
    start_time: "2025-01-02"
    end_time: "2026-05-15"
    benchmark: SPY
task:
  dataset:
    kwargs:
      handler:
        kwargs:
          end_time: "2026-05-15"
      segments:
        test: ["2025-01-02", "2026-05-15"]
"""
    )
    scenario = MonitorScenario("QQQ", "63d", "2026-02-20", "2026-05-22")

    updated = apply_monitor_config(base, scenario)

    assert updated["experiment_name"] == "candidate_monitor_63d_benchqqq"
    assert updated["benchmark"] == "QQQ"
    assert updated["data_handler_config"]["end_time"] == "2026-05-22"
    assert updated["task"]["dataset"]["kwargs"]["handler"]["kwargs"]["end_time"] == "2026-05-22"
    assert updated["task"]["dataset"]["kwargs"]["segments"]["test"] == ["2026-02-20", "2026-05-22"]
    assert updated["port_analysis_config"]["backtest"]["benchmark"] == "QQQ"
    assert updated["port_analysis_config"]["backtest"]["start_time"] == "2026-02-20"
    assert updated["port_analysis_config"]["backtest"]["end_time"] == "2026-05-22"


def test_latest_rows_for_experiments_keeps_newest_repeated_scenario():
    old = RunSummary("candidate_monitor_full_benchspy", "old", "FINISHED", "old", end_time=100)
    new = RunSummary("candidate_monitor_full_benchspy", "new", "FINISHED", "new", end_time=200)
    qqq = RunSummary("candidate_monitor_full_benchqqq", "qqq", "FINISHED", "qqq", end_time=150)

    rows = latest_rows_for_experiments([old, qqq, new], ["candidate_monitor_full_benchspy", "candidate_monitor_full_benchqqq"])

    assert [row.run_id for row in rows] == ["new", "qqq"]


def test_render_monitor_report_mentions_provider_and_evaluable_dates():
    rows = [
        RunSummary(
            "candidate_monitor_full_benchspy",
            "abc12345",
            "FINISHED",
            "qrun",
            ann_excess_cost=0.10,
            end_time=200,
        )
    ]

    report = render_monitor_report(rows, latest_session="2026-05-22", evaluation_session="2026-05-21")

    assert "# Modern Low-Turnover Candidate Monitor" in report
    assert "latest_provider_session: 2026-05-22" in report
    assert "latest_evaluable_session: 2026-05-21" in report
    assert "10.00%" in report

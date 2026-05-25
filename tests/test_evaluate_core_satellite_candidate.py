from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.evaluate_core_satellite_candidate import (
    CoreSatelliteRow,
    combined_excess_returns,
    evaluate_rows,
    render_core_satellite_report,
)


def test_combined_excess_returns_uses_independently_growing_sleeves_and_core_entry_cost():
    index = pd.date_range("2026-05-18", periods=3, freq="B")
    satellite = pd.DataFrame(
        {
            "return": [0.0, 0.10, 0.0],
            "cost": [0.0, 0.01, 0.0],
            "bench": [0.0, 0.02, 0.01],
        },
        index=index,
    )
    core_return = pd.Series([0.0, 0.04, 0.02], index=index)

    excess = combined_excess_returns(
        satellite,
        core_return,
        alpha_weight=0.4,
        core_entry_cost=0.005,
    )

    assert excess.iloc[0] == pytest.approx(0.0)
    assert excess.iloc[1] == pytest.approx(0.037)
    expected_total_day_1 = 0.4 * 1.09 + 0.6 * 1.035
    expected_total_day_2 = 0.4 * 1.09 + 0.6 * 1.035 * 1.02
    assert excess.iloc[2] == pytest.approx(expected_total_day_2 / expected_total_day_1 - 1 - 0.01)


def test_render_core_satellite_report_states_weights_and_research_only_scope():
    rows = [
        CoreSatelliteRow(
            benchmark="QQQ",
            window="63d",
            ann_excess_cost=-0.1174,
            max_drawdown_cost=-0.0643,
            ir_cost=-1.67,
        )
    ]

    report = render_core_satellite_report(rows, alpha_weight=0.4, core_symbol="QQQ")

    assert "# Modern Core-Satellite Candidate Monitor" in report
    assert "core_weight: 60.00% QQQ" in report
    assert "satellite_weight: 40.00%" in report
    assert "paper/research stress report" in report
    assert "-11.74%" in report


def test_evaluate_rows_reads_returns_for_selected_core_symbol(monkeypatch):
    artifact_names: list[str] = []
    index = pd.date_range("2026-05-18", periods=2, freq="B")
    report = pd.DataFrame(
        {"return": [0.0, 0.01], "cost": [0.0, 0.0], "bench": [0.0, 0.01]},
        index=index,
    )

    def fake_find_latest_report_artifact(_mlruns_dir, name):
        artifact_names.append(name)
        return Path(f"{name}.pkl")

    monkeypatch.setattr("scripts.evaluate_core_satellite_candidate.DEFAULT_BENCHMARKS", ("QQQ",))
    monkeypatch.setattr("scripts.evaluate_core_satellite_candidate.DEFAULT_WINDOWS", ("full",))
    monkeypatch.setattr(
        "scripts.evaluate_core_satellite_candidate.find_latest_report_artifact",
        fake_find_latest_report_artifact,
    )
    monkeypatch.setattr("scripts.evaluate_core_satellite_candidate.pd.read_pickle", lambda _path: report)
    monkeypatch.setattr(
        "scripts.evaluate_core_satellite_candidate.risk_analysis",
        lambda _returns, freq: {
            "risk": {
                "annualized_return": 0.0,
                "max_drawdown": 0.0,
                "information_ratio": 0.0,
            }
        },
    )

    evaluate_rows(Path("mlruns"), "candidate_", 0.4, 0.0005, core_symbol="SPY")

    assert artifact_names == ["candidate_full_benchqqq", "candidate_full_benchspy"]


def test_core_satellite_report_script_can_start_from_cli_entrypoint():
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_core_satellite_candidate.py", "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0, result.stderr

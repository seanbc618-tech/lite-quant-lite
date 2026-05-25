from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pandas as pd

from scripts.generate_candidate_paper_signals import build_preview_payload, find_latest_positions_artifact


class FakeQlibPosition:
    def get_stock_weight_dict(self):
        return {"MSFT": 0.25, "AAPL": 0.50}


def test_candidate_signal_export_script_can_start_from_cli_entrypoint():
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [sys.executable, "scripts/generate_candidate_paper_signals.py", "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_build_preview_payload_uses_latest_target_portfolio_and_normalizes_budget(tmp_path):
    positions = {
        pd.Timestamp("2026-05-21"): {"position": {"cash": 10.0, "AAPL": {"weight": 0.4}}},
        pd.Timestamp("2026-05-22"): {
            "position": {
                "cash": 100.0,
                "now_account_value": 10_000.0,
                "MSFT": {"weight": 0.25, "amount": 2},
                "AAPL": {"weight": 0.50, "amount": 4},
            }
        },
    }

    payload = build_preview_payload(positions, Path("positions.pkl"), budget=3000.0)

    assert payload["dry_run_only"] is True
    assert payload["date"] == "2026-05-22"
    assert payload["strategy"] == "modern_low_turnover_candidate"
    assert payload["orders"] == [
        {"symbol": "AAPL", "side": "buy", "notional": 2000.0},
        {"symbol": "MSFT", "side": "buy", "notional": 1000.0},
    ]


def test_build_preview_payload_accepts_qlib_position_object():
    positions = {pd.Timestamp("2026-05-22"): FakeQlibPosition()}

    payload = build_preview_payload(positions, Path("positions.pkl"), budget=3000.0)

    assert payload["orders"] == [
        {"symbol": "AAPL", "side": "buy", "notional": 2000.0},
        {"symbol": "MSFT", "side": "buy", "notional": 1000.0},
    ]


def test_find_latest_positions_artifact_selects_newest_finished_matching_experiment(tmp_path):
    mlruns = tmp_path / "mlruns"
    experiment = mlruns / "1"
    old = experiment / "old"
    newest = experiment / "new"
    failed = experiment / "failed"
    artifact_rel = Path("artifacts/portfolio_analysis/positions_normal_1day.pkl")
    experiment.mkdir(parents=True)
    (experiment / "meta.yaml").write_text("name: candidate_monitor_full_benchspy\n", encoding="utf-8")

    for run, status, end_time in ((old, "3", "100"), (newest, "3", "200"), (failed, "4", "300")):
        run.mkdir()
        (run / "meta.yaml").write_text(f"status: {status}\nend_time: {end_time}\n", encoding="utf-8")
        path = run / artifact_rel
        path.parent.mkdir(parents=True)
        path.write_bytes(b"artifact")

    result = find_latest_positions_artifact(mlruns, "candidate_monitor_full_benchspy")

    assert result == newest / artifact_rel

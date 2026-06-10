from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from scripts.generate_quality_paper_signals import (
    build_preview_payload,
    main,
    read_promotion_status,
)


def reported_holding(
    ticker: str,
    weight: float,
    *,
    rebalance_session: str = "2026-05-01",
    source: str = "reported",
    variant: str = "reported_only",
) -> dict:
    return {
        "variant": variant,
        "ticker": ticker,
        "target_weight": weight,
        "rebalance_session": pd.Timestamp(rebalance_session),
        "debt_to_assets_source": source,
    }


def test_build_preview_payload_exports_latest_reported_only_holdings_as_dry_run():
    holdings = pd.DataFrame(
        [
            reported_holding("OLD", 1.0, rebalance_session="2026-04-01"),
            reported_holding("AAPL", 0.5),
            reported_holding("MSFT", 0.5),
            reported_holding("BASE", 1.0, variant="base"),
        ]
    )

    payload = build_preview_payload(
        holdings,
        Path("holdings.parquet"),
        Path("monitor.md"),
        budget=900.0,
    )

    assert payload["dry_run_only"] is True
    assert payload["strategy"] == "quality_reported_only_candidate"
    assert payload["variant"] == "reported_only"
    assert payload["date"] == "2026-05-01"
    assert payload["orders"] == [
        {"symbol": "AAPL", "side": "buy", "notional": 450.0},
        {"symbol": "MSFT", "side": "buy", "notional": 450.0},
    ]


def test_read_promotion_status_requires_explicit_status(tmp_path: Path):
    passing = tmp_path / "passing.md"
    failing = tmp_path / "failing.md"
    missing = tmp_path / "missing.md"
    passing.write_text("promotion_gate: PASS\n", encoding="utf-8")
    failing.write_text("promotion_gate: FAIL\n", encoding="utf-8")
    missing.write_text("# old report\n", encoding="utf-8")

    assert read_promotion_status(passing) == "PASS"
    assert read_promotion_status(failing) == "FAIL"
    with pytest.raises(ValueError, match="promotion_gate"):
        read_promotion_status(missing)


def test_build_preview_payload_rebalances_when_current_positions_are_provided():
    holdings = pd.DataFrame(
        [
            reported_holding("AAPL", 0.5),
            reported_holding("MSFT", 0.5),
        ]
    )

    payload = build_preview_payload(
        holdings,
        Path("holdings.parquet"),
        Path("monitor.md"),
        budget=900.0,
        current_positions={"AAPL": 450.0, "GOOG": 450.0},
    )

    assert payload["rebalance"] is True
    assert payload["orders"] == [
        {"symbol": "GOOG", "side": "sell", "notional": 450.0},
        {"symbol": "MSFT", "side": "buy", "notional": 450.0},
    ]


def test_build_preview_payload_rejects_nonreported_leverage_and_holding_overflow():
    derived = pd.DataFrame(
        [reported_holding("AAPL", 1.0, source="derived_assets_minus_equity")]
    )
    overflowing = pd.DataFrame(
        [reported_holding(f"S{index}", 0.1) for index in range(10)]
    )

    with pytest.raises(ValueError, match="reported"):
        build_preview_payload(derived, Path("holdings.parquet"), Path("monitor.md"), 900.0)
    with pytest.raises(ValueError, match="maximum"):
        build_preview_payload(overflowing, Path("holdings.parquet"), Path("monitor.md"), 900.0)


def test_main_refuses_to_write_preview_when_monitor_gate_fails(tmp_path: Path, monkeypatch):
    report = tmp_path / "monitor.md"
    holdings = tmp_path / "holdings.parquet"
    output = tmp_path / "preview.json"
    report.write_text("promotion_gate: FAIL\n", encoding="utf-8")
    pd.DataFrame([reported_holding("AAPL", 1.0)]).to_parquet(holdings, index=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_quality_paper_signals.py",
            "--report",
            str(report),
            "--holdings",
            str(holdings),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(ValueError, match="PASS"):
        main()

    assert not output.exists()


def test_quality_signal_export_script_can_start_from_cli_entrypoint():
    result = subprocess.run(
        [sys.executable, "scripts/generate_quality_paper_signals.py", "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0, result.stderr

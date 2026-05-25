from __future__ import annotations

import json

from scripts.trade_v2 import process_signals


def test_process_signals_rejects_dry_run_only_preview_in_submit_mode(tmp_path):
    signal_file = tmp_path / "candidate_preview.json"
    signal_file.write_text(
        json.dumps(
            {
                "dry_run_only": True,
                "orders": [{"symbol": "AAPL", "side": "buy", "notional": 100.0}],
            }
        ),
        encoding="utf-8",
    )

    assert process_signals(None, signal_file, dry_run=False) == 1


def test_process_signals_rejects_oversized_notional_in_dry_run(tmp_path, monkeypatch):
    from scripts import trade_v2

    monkeypatch.setattr(trade_v2.config.trading, "max_order_notional", 1000.0)
    signal_file = tmp_path / "oversized_preview.json"
    signal_file.write_text(
        json.dumps(
            {
                "dry_run_only": True,
                "orders": [{"symbol": "QQQ", "side": "buy", "notional": 1000.01}],
            }
        ),
        encoding="utf-8",
    )

    assert process_signals(None, signal_file, dry_run=True) == 1


def test_process_signals_rejects_too_many_target_positions_in_dry_run(tmp_path, monkeypatch):
    from scripts import trade_v2

    monkeypatch.setattr(trade_v2.config.trading, "max_open_positions", 10)
    signal_file = tmp_path / "too_many_targets.json"
    signal_file.write_text(
        json.dumps(
            {
                "dry_run_only": True,
                "orders": [
                    {"symbol": f"S{index}", "side": "buy", "notional": 10.0}
                    for index in range(11)
                ],
            }
        ),
        encoding="utf-8",
    )

    assert process_signals(None, signal_file, dry_run=True) == 1

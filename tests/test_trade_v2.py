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

from __future__ import annotations

import json

from scripts.trade_v2 import process_signals, resolve_orders


class FakePosition:
    def __init__(self, symbol, market_value):
        self.symbol = symbol
        self.market_value = market_value


class FakeClient:
    def get_all_positions(self):
        return [FakePosition("AAPL", "1000")]


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


def test_resolve_orders_rebalances_from_target_weights():
    orders = resolve_orders(
        {
            "rebalance": True,
            "preview_budget": 2000.0,
            "current_positions": {"AAPL": 1000.0, "MSFT": 500.0},
            "target_weights": {"MSFT": 0.5, "NVDA": 0.5},
        },
        None,
        dry_run=True,
    )

    assert orders == [
        {"symbol": "AAPL", "side": "sell", "notional": 1000.0},
        {"symbol": "NVDA", "side": "buy", "notional": 1000.0},
        {"symbol": "MSFT", "side": "buy", "notional": 500.0},
    ]


def test_resolve_orders_fetches_live_positions_when_not_dry_run():
    orders = resolve_orders(
        {
            "rebalance": True,
            "preview_budget": 1000.0,
            "current_positions": {"AAPL": 0.0},
            "target_weights": {"MSFT": 1.0},
        },
        FakeClient(),
        dry_run=False,
    )

    assert orders == [
        {"symbol": "AAPL", "side": "sell", "notional": 1000.0},
        {"symbol": "MSFT", "side": "buy", "notional": 1000.0},
    ]


def test_process_signals_executes_rebalance_preview_in_dry_run(tmp_path):
    signal_file = tmp_path / "rebalance_preview.json"
    signal_file.write_text(
        json.dumps(
            {
                "dry_run_only": True,
                "rebalance": True,
                "preview_budget": 1000.0,
                "current_positions": {"AAPL": 1000.0},
                "target_weights": {"MSFT": 1.0},
            }
        ),
        encoding="utf-8",
    )

    assert process_signals(None, signal_file, dry_run=True) == 0

from __future__ import annotations

import pytest

from us_quant.rebalance import reconcile_positions


def test_reconcile_positions_emits_sells_before_buys_for_rotation():
    orders = reconcile_positions(
        current={"AAPL": 1000.0, "MSFT": 500.0},
        target_weights={"MSFT": 0.5, "NVDA": 0.5},
        budget=2000.0,
    )

    assert orders == [
        {"symbol": "AAPL", "side": "sell", "notional": 1000.0},
        {"symbol": "NVDA", "side": "buy", "notional": 1000.0},
        {"symbol": "MSFT", "side": "buy", "notional": 500.0},
    ]


def test_reconcile_positions_trims_overweight_without_full_exit():
    orders = reconcile_positions(
        current={"AAPL": 1300.0, "MSFT": 700.0},
        target_weights={"AAPL": 0.6, "MSFT": 0.4},
        budget=2000.0,
    )

    assert orders == [
        {"symbol": "AAPL", "side": "sell", "notional": 100.0},
        {"symbol": "MSFT", "side": "buy", "notional": 100.0},
    ]


def test_reconcile_positions_ignores_dust_below_threshold():
    orders = reconcile_positions(
        current={"AAPL": 1000.0},
        target_weights={"AAPL": 1.0},
        budget=1000.5,
        min_trade_notional=1.0,
    )

    assert orders == []


def test_reconcile_positions_preserves_cash_when_target_weights_sum_below_one():
    orders = reconcile_positions(
        current={},
        target_weights={"AAPL": 0.5},
        budget=1000.0,
    )

    assert orders == [{"symbol": "AAPL", "side": "buy", "notional": 500.0}]


def test_reconcile_positions_rejects_invalid_weights():
    with pytest.raises(ValueError, match="at most 1"):
        reconcile_positions({"AAPL": 100.0}, {"AAPL": 0.6, "MSFT": 0.5}, 1000.0)

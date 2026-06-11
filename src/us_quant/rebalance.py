"""Portfolio reconciliation helpers for paper trading signals."""
from __future__ import annotations

from typing import Any, Mapping


def reconcile_positions(
    current: Mapping[str, float],
    target_weights: Mapping[str, float],
    budget: float,
    *,
    min_trade_notional: float = 1.0,
) -> list[dict[str, Any]]:
    """Diff current holdings against target weights and emit sell-then-buy orders.

    Args:
        current: Symbol -> current market value in USD.
        target_weights: Symbol -> target portfolio weight (non-negative, sum <= 1).
        budget: Total portfolio value used to size target notionals.
        min_trade_notional: Ignore trades smaller than this threshold.

    Returns:
        Sell orders first, then buy orders. Each order has symbol, side, notional.
    """
    if budget <= 0:
        raise ValueError("budget must be positive")
    if min_trade_notional < 0:
        raise ValueError("min_trade_notional must be non-negative")

    normalized_current = {
        symbol.strip().upper(): float(value)
        for symbol, value in current.items()
        if float(value) > 0
    }
    normalized_targets = {
        symbol.strip().upper(): float(weight)
        for symbol, weight in target_weights.items()
        if float(weight) > 0
    }
    if not normalized_targets:
        raise ValueError("target_weights must contain at least one positive weight")

    total_weight = sum(normalized_targets.values())
    if total_weight <= 0:
        raise ValueError("target_weights must sum to a positive value")
    if total_weight > 1.000001:
        raise ValueError("target_weights must sum to at most 1")

    target_notionals = {
        symbol: budget * weight
        for symbol, weight in normalized_targets.items()
    }
    symbols = sorted(set(normalized_current) | set(target_notionals))

    sells: list[dict[str, Any]] = []
    buys: list[dict[str, Any]] = []
    for symbol in symbols:
        current_value = normalized_current.get(symbol, 0.0)
        target_value = target_notionals.get(symbol, 0.0)
        delta = target_value - current_value
        if delta < -min_trade_notional:
            sells.append(
                {
                    "symbol": symbol,
                    "side": "sell",
                    "notional": round(-delta, 2),
                }
            )
        elif delta > min_trade_notional:
            buys.append(
                {
                    "symbol": symbol,
                    "side": "buy",
                    "notional": round(delta, 2),
                }
            )

    sells.sort(key=lambda order: (-order["notional"], order["symbol"]))
    buys.sort(key=lambda order: (-order["notional"], order["symbol"]))
    return sells + buys

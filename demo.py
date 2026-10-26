"""Deterministic teaching simulation; no network, accounts, or external data."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from us_quant.rebalance import reconcile_positions

ROOT = Path(__file__).resolve().parent
SYMBOLS = ('SYN_A', 'SYN_B')
TARGET = {symbol: 0.4 for symbol in SYMBOLS}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(scenario: dict, cost_bps: int) -> dict:
    prices = scenario['prices']
    if set(prices) != set(SYMBOLS) or any(len(prices[s]) != 8 for s in SYMBOLS):
        raise ValueError('Expected the complete two-symbol, eight-observation universe')
    gaps = [{'symbol': s, 'observation': t} for s in SYMBOLS
            for t, price in enumerate(prices[s]) if price is None]
    result = {'scenario': scenario['name'], 'cost_bps': cost_bps,
              'status': 'INVALID_DECLARED_GAP' if gaps else 'VALID_SYNTHETIC',
              'gaps': gaps, 'ending_equity': None, 'total_return': None,
              'cost': None, 'traded_notional': None, 'ledger': []}
    if gaps:
        if not scenario.get('gap_reason'):
            raise ValueError('Missing inputs need an explicit fixture gap declaration')
        result['gap_reason'] = scenario['gap_reason']
        return result
    if any(not math.isfinite(p) or p <= 0 for s in SYMBOLS for p in prices[s]):
        raise ValueError('Prices must be finite and positive')
    cash, costs, turnover = 1000.0, 0.0, 0.0
    units = dict.fromkeys(SYMBOLS, 0.0)
    for t in range(8):
        values = {s: units[s] * prices[s][t] for s in SYMBOLS}
        equity = cash + sum(values.values())
        if t == 7:
            # The inherited function does not accept an all-cash target.
            # Explicit final liquidation belongs to this teaching simulation.
            orders = [{'symbol': s, 'side': 'sell', 'notional': values[s]}
                      for s in SYMBOLS if values[s] > 0]
        else:
            orders = reconcile_positions(values, TARGET, equity)
        sides = [o['side'] for o in orders]
        assert sides == sorted(sides, key=lambda side: side != 'sell')
        step_cost = 0.0
        for order in orders:
            s, notional = order['symbol'], order['notional']
            fee = notional * cost_bps / 10000
            direction = 1 if order['side'] == 'buy' else -1
            units[s] += direction * notional / prices[s][t]
            cash -= direction * notional + fee
            costs += fee
            step_cost += fee
            turnover += notional
        after = cash + sum(units[s] * prices[s][t] for s in SYMBOLS)
        assert math.isclose(after, equity - step_cost, abs_tol=1e-8)
        assert cash >= -1e-8 and all(q >= -1e-8 for q in units.values())
        result['ledger'].append({'observation': t, 'equity_before': round(equity, 8),
                                 'equity_after': round(after, 8), 'cash': round(cash, 8),
                                 'cost': round(step_cost, 8), 'orders': orders})
    result.update(ending_equity=round(cash, 8), total_return=round(cash / 1000 - 1, 10),
                  cost=round(costs, 8), traded_notional=round(turnover, 8))
    return result


def run() -> dict:
    source = ROOT / 'examples/scenarios.json'
    scenarios = json.loads(source.read_text())['scenarios']
    return {'scope': 'Synthetic engineering demonstration; no economic inference',
            'protocol_sha256': sha256(ROOT / 'PROTOCOL.md'),
            'input_sha256': sha256(source), 'initial_equity': 1000,
            'cash_baseline_ending_equity': 1000,
            'results': [simulate(s, cost) for s in scenarios for cost in (0, 10)]}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True, allow_nan=False))

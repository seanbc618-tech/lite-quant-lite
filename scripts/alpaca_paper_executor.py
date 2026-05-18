#!/usr/bin/env python3
"""
Alpaca 纸面交易薄执行层：读取 JSON 信号、风控校验后提交市价单。
不替代任何现有脚本；为新建工具。

环境变量（任选一组）:
  APCA_API_KEY_ID + APCA_API_SECRET_KEY
  或 ALPACA_API_KEY + ALPACA_SECRET_KEY

Kill-switch:
  - 环境变量 MAX_DAILY_LOSS_PCT: 相对昨收权益 last_equity 的日内回撤比例上限（默认 0.05）
  - 环境变量 MAX_ORDER_NOTIONAL: 单笔最大名义金额 USD（默认 1000）
  - 环境变量 MAX_OPEN_POSITIONS: 持仓标的数量上限（默认 10）
  - 文件 ./signals/KILL_SWITCH（或环境变量 KILL_SWITCH_PATH）存在且非空则拒绝一切下单

用法:
  .venv/bin/python scripts/alpaca_paper_executor.py --dry-run --signals signals/example_signals.json
  .venv/bin/python scripts/alpaca_paper_executor.py --signals signals/example_signals.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


def _f(x: str | None) -> float:
    return float(x) if x is not None else 0.0


def load_credentials() -> tuple[str, str]:
    key = os.environ.get("APCA_API_KEY_ID") or os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("APCA_API_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit(
            "缺少密钥：请设置 APCA_API_KEY_ID / APCA_API_SECRET_KEY "
            "或 ALPACA_API_KEY / ALPACA_SECRET_KEY"
        )
    return key, secret


def kill_switch_active() -> bool:
    p = Path(os.environ.get("KILL_SWITCH_PATH", "signals/KILL_SWITCH"))
    return p.is_file() and p.stat().st_size > 0


def risk_check_account(client: TradingClient) -> None:
    if kill_switch_active():
        raise SystemExit("Kill-switch 文件存在，已阻止下单")

    max_loss = float(os.environ.get("MAX_DAILY_LOSS_PCT", "0.05"))
    acct = client.get_account()
    eq = _f(acct.equity)
    last = _f(acct.last_equity)
    if last > 0 and (eq - last) / last <= -max_loss:
        raise SystemExit(
            f"日内权益回撤超过限制: equity={eq} last_equity={last} 阈值={max_loss:.2%}"
        )
    if acct.trading_blocked or acct.account_blocked or acct.trade_suspended_by_user:
        raise SystemExit("账户处于禁止交易状态")


def risk_check_order(
    client: TradingClient,
    symbol: str,
    side: str,
    notional: float | None,
    qty: float | None,
) -> None:
    max_notional = float(os.environ.get("MAX_ORDER_NOTIONAL", "1000"))
    max_positions = int(os.environ.get("MAX_OPEN_POSITIONS", "10"))

    if notional is not None and notional > max_notional:
        raise SystemExit(f"{symbol}: 单笔名义 {notional} 超过 MAX_ORDER_NOTIONAL={max_notional}")
    if qty is not None and qty <= 0:
        raise SystemExit(f"{symbol}: qty 必须为正")

    positions = client.get_all_positions()
    sym_have = {p.symbol for p in positions}
    if side.lower() == "buy" and symbol not in sym_have and len(positions) >= max_positions:
        raise SystemExit(f"持仓数 {len(positions)} 已达上限 {max_positions}（新开仓被拒）")


def submit(
    client: TradingClient | None,
    symbol: str,
    side: str,
    notional: float | None,
    qty: float | None,
    dry_run: bool,
) -> None:
    side_e = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    if dry_run or client is None:
        print(f"[dry-run] {side} {symbol} notional={notional} qty={qty}")
        return
    risk_check_order(client, symbol, side, notional, qty)
    if notional is not None:
        req = MarketOrderRequest(
            symbol=symbol,
            notional=notional,
            side=side_e,
            time_in_force=TimeInForce.DAY,
        )
    else:
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side_e,
            time_in_force=TimeInForce.DAY,
        )
    order = client.submit_order(req)
    print(f"已提交: {symbol} {side} id={order.id} status={order.status}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", type=Path, default=Path("signals/example_signals.json"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    path = args.signals
    if not path.is_file():
        print(f"信号文件不存在: {path}", file=sys.stderr)
        return 1

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    orders = raw.get("orders", [])
    if not isinstance(orders, list) or not orders:
        print("无 orders 列表或为空")
        return 1

    client: TradingClient | None = None
    if not args.dry_run:
        k, s = load_credentials()
        client = TradingClient(api_key=k, secret_key=s, paper=True)
        risk_check_account(client)

    for o in orders:
        symbol = str(o["symbol"])
        side = str(o["side"])
        notional = o.get("notional")
        qty = o.get("qty")
        if notional is not None and qty is not None:
            print(f"{symbol}: notional 与 qty 不可同时指定", file=sys.stderr)
            return 1
        if notional is None and qty is None:
            print(f"{symbol}: 必须指定 notional 或 qty", file=sys.stderr)
            return 1
        nf = float(notional) if notional is not None else None
        qf = float(qty) if qty is not None else None
        submit(client, symbol, side, nf, qf, args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

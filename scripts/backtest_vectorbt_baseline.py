#!/usr/bin/env python3
"""
VectorBT 最小可复现示例：双均线策略 + 按时间切分的样本内/样本外表现。
数据：Yahoo Finance（真实行情）。不替代任何现有脚本；为新建工具。

用法:
  .venv/bin/python scripts/backtest_vectorbt_baseline.py [--symbol AAPL] [--split 2022-01-01]
"""
from __future__ import annotations

import argparse

import pandas as pd
import vectorbt as vbt


def run_segment(close: pd.Series, fast: int, slow: int, init_cash: float, label: str) -> None:
    if len(close) < slow + 5:
        print(f"{label}: 数据过短，跳过")
        return
    fast_ma = vbt.MA.run(close, fast)
    slow_ma = vbt.MA.run(close, slow)
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)
    pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=init_cash, freq="1d")
    ret = float(pf.total_return())
    sharpe = float(pf.sharpe_ratio())
    print(f"{label}: bars={len(close)}  total_return={ret:.4f}  sharpe={sharpe:.4f}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="AAPL")
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default="2025-01-01")
    p.add_argument("--split", default="2022-01-01", help="样本外起始日（UTC 日历对齐 Yahoo 索引）")
    p.add_argument("--fast", type=int, default=10)
    p.add_argument("--slow", type=int, default=30)
    p.add_argument("--cash", type=float, default=10_000.0)
    args = p.parse_args()

    data = vbt.YFData.download(args.symbol, start=args.start, end=args.end)
    close = data.get("Close")
    if close is None or close.empty:
        print("未能下载收盘价")
        return 1

    split_ts = pd.Timestamp(args.split).tz_localize("UTC")
    is_mask = close.index < split_ts
    oos_mask = close.index >= split_ts

    print(f"标的={args.symbol}  fast={args.fast} slow={args.slow}  切分={args.split}")
    run_segment(close[is_mask], args.fast, args.slow, args.cash, "样本内(IS)")
    run_segment(close[oos_mask], args.fast, args.slow, args.cash, "样本外(OOS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

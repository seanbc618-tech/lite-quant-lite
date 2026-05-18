#!/usr/bin/env python3
"""
Qlib 本地数据最小校验：读取 us_data 的 $close，双均线规则回测 + IS/OOS 时间切分。
用于确认 Qlib 数据与简单信号链路可用；完整 ML 工作流请用官方 qrun + workflow YAML。

用法:
  .venv/bin/python scripts/backtest_qlib_baseline.py [--symbol AAPL] [--split 2022-01-01]
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import qlib
from qlib.data import D


def equity_from_ma(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """多头持有：快线上穿慢线买入，下穿平仓；日频简单复利净值。"""
    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow).mean()
    pos = (fast_ma > slow_ma).astype(float).shift(1).fillna(0.0)
    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos * daily_ret
    return (1.0 + strat_ret).cumprod()


def metrics(equity: pd.Series) -> tuple[float, float]:
    r = equity.pct_change().dropna()
    if r.empty or r.std() == 0:
        return float(equity.iloc[-1] / equity.iloc[0] - 1), float("nan")
    # 日化无风险≈0 的简化夏普
    sharpe = float(np.sqrt(252) * r.mean() / r.std())
    total = float(equity.iloc[-1] / equity.iloc[0] - 1)
    return total, sharpe


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="AAPL")
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument(
        "--split",
        default=None,
        help="样本外起始日；默认按 --split_pct 在可用区间内切分（官方 us 包常止于约 2020-11）",
    )
    p.add_argument(
        "--split_pct",
        type=float,
        default=0.75,
        help="当未指定 --split 时，前 split_pct 为 IS，其余为 OOS",
    )
    p.add_argument("--fast", type=int, default=10)
    p.add_argument("--slow", type=int, default=30)
    p.add_argument(
        "--provider_uri",
        default="~/.qlib/qlib_data/us_data",
        help="与 download_qlib_us.py 输出目录一致",
    )
    args = p.parse_args()

    qlib.init(provider_uri=args.provider_uri, region="us")
    raw = D.features(
        [args.symbol],
        ["$close"],
        start_time=args.start,
        end_time=args.end,
    )
    close = raw["$close"].xs(args.symbol, level="instrument").sort_index()
    close.index = pd.to_datetime(close.index)

    if args.split:
        split = pd.Timestamp(args.split)
    else:
        idx = close.index.sort_values()
        cut_i = max(int(len(idx) * args.split_pct), args.slow + 5)
        cut_i = min(cut_i, len(idx) - args.slow - 5)
        split = idx[cut_i]
    is_ser = close[close.index < split]
    oos_ser = close[close.index >= split]

    print(
        f"标的={args.symbol}  Qlib $close  fast={args.fast} slow={args.slow}  "
        f"切分点={split.date()} (IS<{split.date()} OOS>={split.date()})"
    )
    for label, seg in [("样本内(IS)", is_ser), ("样本外(OOS)", oos_ser)]:
        if len(seg) < args.slow + 2:
            print(f"{label}: 数据过短")
            continue
        eq = equity_from_ma(seg, args.fast, args.slow)
        eq = eq.dropna()
        tot, sh = metrics(eq)
        print(f"{label}: bars={len(seg)}  total_return={tot:.4f}  sharpe~={sh:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

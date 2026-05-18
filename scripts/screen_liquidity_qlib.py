#!/usr/bin/env python3
"""
基于 Qlib 本地 us_data 的简易流动性选股：按「近 N 日平均成交额（收盘价×成交量）」横截面排序。

不替代 qrun 里的 ML 因子选股；用于演示「规则选股 / 初筛 universe」的一种做法。
与现有 scripts 的关系：补充 verify_data / 回测 之前可做的标的池收缩。

用法:
  .venv/bin/python scripts/screen_liquidity_qlib.py --market nasdaq100 --top 20
"""
from __future__ import annotations

import argparse

import pandas as pd
import qlib
from qlib.data import D


def main() -> int:
    p = argparse.ArgumentParser(description="流动性排名选股（Qlib 本地数据）")
    p.add_argument("--provider_uri", default="~/.qlib/qlib_data/us_data")
    p.add_argument("--market", default="nasdaq100", choices=["sp500", "nasdaq100", "all"])
    p.add_argument("--lookback", type=int, default=20, help="回溯交易日数")
    p.add_argument("--top", type=int, default=30, help="输出前 K 只")
    p.add_argument(
        "--end",
        default=None,
        help="排序截止日 YYYY-MM-DD；默认用数据内最近可用日",
    )
    args = p.parse_args()

    qlib.init(provider_uri=args.provider_uri, region="us")

    inst = D.instruments(market=args.market)
    end = args.end or "2099-12-31"
    syms = D.list_instruments(instruments=inst, start_time="2000-01-01", end_time=end, as_list=True)
    if not syms:
        print("无可用标的")
        return 1

    # 多取一些日历日覆盖 lookback 个交易日
    raw = D.features(syms, ["$close", "$volume"], start_time="2018-01-01", end_time=end)
    if raw.empty:
        print("无行情数据")
        return 1

    raw["dollar_vol"] = raw["$close"] * raw["$volume"]
    last_day = raw.index.get_level_values("datetime").max()
    scores = []
    for sym in syms:
        try:
            s = raw.loc[pd.IndexSlice[sym, :], "dollar_vol"].dropna()
        except KeyError:
            continue
        if s.empty:
            continue
        tail = s.tail(args.lookback)
        if len(tail) < max(5, args.lookback // 2):
            continue
        last_dv = float(tail.iloc[-1]) if len(tail) else float("nan")
        scores.append((sym, float(tail.mean()), last_dv))

    df = pd.DataFrame(
        scores,
        columns=["symbol", f"avg_dollar_vol_{args.lookback}d", "last_bar_dollar_vol"],
    )
    df = df.sort_values(f"avg_dollar_vol_{args.lookback}d", ascending=False).head(args.top)
    print(f"universe={args.market}  asof≈{last_day.date()}  lookback={args.lookback}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

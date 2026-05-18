#!/usr/bin/env python3
"""
校验本地数据：Qlib us_data 目录结构 + Yahoo Finance 能否拉取真实行情。
不替代任何现有脚本；为新建工具。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def check_qlib_dir(us_data: Path) -> tuple[bool, str]:
    us_data = us_data.expanduser().resolve()
    if not us_data.is_dir():
        return False, f"目录不存在: {us_data}"
    calendars = us_data / "calendars"
    instruments = us_data / "instruments"
    features = us_data / "features"
    ok = calendars.is_dir() and instruments.is_dir() and features.is_dir()
    if ok:
        return True, f"Qlib 数据目录结构正常: {us_data}"
    missing = [p.name for p in (calendars, instruments, features) if not p.is_dir()]
    return False, f"缺少子目录 {missing}，请运行 scripts/download_qlib_us.py"


def check_yahoo(symbol: str) -> tuple[bool, str]:
    try:
        import yfinance as yf
    except ImportError as e:
        return False, f"yfinance 未安装: {e}"
    df = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
    if df is None or df.empty:
        return False, f"Yahoo 未返回数据: {symbol}"
    return True, f"Yahoo OK: {symbol} 最近 {len(df)} 根日线"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--qlib_us_dir",
        type=Path,
        default=Path.home() / ".qlib" / "qlib_data" / "us_data",
    )
    p.add_argument("--yahoo_symbol", default="AAPL")
    args = p.parse_args()

    ok_q, msg_q = check_qlib_dir(args.qlib_us_dir)
    print(msg_q)
    ok_y, msg_y = check_yahoo(args.yahoo_symbol)
    print(msg_y)
    return 0 if (ok_q and ok_y) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Update local OHLCV CSV files from Nasdaq historical quote JSON.

This is a fallback for periods when yfinance/Yahoo is rate-limited. It writes
the same CSV schema used by ``scripts/update_qlib_data.py`` so the existing
modern Qlib provider builder can consume the files.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CSV_DIR = Path.home() / ".qlib" / "stock_data" / "source" / "us_data"
DEFAULT_START = "2025-03-27"
DEFAULT_END = date.today().isoformat()
ETF_SYMBOLS = {"SPY", "QQQ"}
CSV_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "adjclose", "volume"]


def clean_number(value: Any) -> float:
    if value is None:
        return float("nan")
    text = str(value).strip().replace("$", "").replace(",", "")
    if text in {"", "N/A", "--"}:
        return float("nan")
    return float(text)


def parse_nasdaq_rows(symbol: str, rows: list[dict[str, Any]]) -> pd.DataFrame:
    parsed: list[dict[str, Any]] = []
    for row in rows:
        timestamp = pd.to_datetime(row.get("date"), format="%m/%d/%Y", errors="coerce")
        if pd.isna(timestamp):
            continue
        open_ = clean_number(row.get("open"))
        high = clean_number(row.get("high"))
        low = clean_number(row.get("low"))
        close = clean_number(row.get("close"))
        volume = clean_number(row.get("volume"))
        if any(math.isnan(value) for value in (open_, high, low, close, volume)):
            continue
        parsed.append(
            {
                "date": timestamp.strftime("%Y-%m-%d"),
                "symbol": symbol.upper(),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "adjclose": close,
                "volume": int(volume),
            }
        )
    if not parsed:
        return pd.DataFrame(columns=CSV_COLUMNS)
    frame = pd.DataFrame(parsed, columns=CSV_COLUMNS)
    return frame.sort_values("date").reset_index(drop=True)


def nasdaq_assetclass(symbol: str) -> str:
    return "etf" if symbol.upper() in ETF_SYMBOLS else "stocks"


def fetch_nasdaq_rows(symbol: str, start: str, end: str, timeout: int = 30) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "assetclass": nasdaq_assetclass(symbol),
            "fromdate": start,
            "todate": end,
            "limit": 9999,
        }
    )
    url = f"https://api.nasdaq.com/api/quote/{symbol.upper()}/historical?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": f"https://www.nasdaq.com/market-activity/{nasdaq_assetclass(symbol)}/{symbol.lower()}/historical",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = (((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or [])
    if not isinstance(rows, list):
        return []
    return rows


def merge_csv(path: Path, update: pd.DataFrame) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        existing = pd.read_csv(path)
        merged = pd.concat([existing, update], ignore_index=True)
    else:
        merged = update.copy()
    merged = merged.loc[:, CSV_COLUMNS]
    merged = merged.dropna(subset=["date", "close"])
    merged = merged.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    merged.to_csv(path, index=False)
    return merged


def read_provider_symbols(path: Path) -> list[str]:
    payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    symbols = payload.get("symbols") or []
    if not isinstance(symbols, list):
        return []
    return [str(symbol).upper() for symbol in symbols]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 Nasdaq 历史行情接口更新本地 CSV")
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR, help="CSV 输出目录")
    parser.add_argument("--start", default=DEFAULT_START, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", default=DEFAULT_END, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--symbols", nargs="*", default=[], help="显式标的列表")
    parser.add_argument("--symbols-from-provider", type=Path, default=None, help="读取 provider build_summary.json 中的 symbols")
    parser.add_argument("--sleep", type=float, default=0.15, help="请求间隔秒数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbols = [symbol.upper() for symbol in args.symbols]
    if args.symbols_from_provider is not None:
        symbols.extend(read_provider_symbols(args.symbols_from_provider))
    symbols = sorted(set(symbols))
    if not symbols:
        print("ERROR no symbols requested")
        return 2

    success: list[str] = []
    failed: list[str] = []
    for index, symbol in enumerate(symbols, start=1):
        print(f"[{index}/{len(symbols)}] {symbol} {args.start}..{args.end}")
        try:
            rows = fetch_nasdaq_rows(symbol, args.start, args.end)
            update = parse_nasdaq_rows(symbol, rows)
            if update.empty:
                raise ValueError("empty Nasdaq rows")
            merged = merge_csv(args.csv_dir.expanduser() / f"{symbol}.csv", update)
        except Exception as exc:
            print(f"  WARN {symbol}: {exc}")
            failed.append(symbol)
        else:
            print(f"  OK {symbol}: update_rows={len(update)} total_rows={len(merged)}")
            success.append(symbol)
        time.sleep(args.sleep)

    summary = {
        "source": "nasdaq",
        "date_range": f"{args.start} ~ {args.end}",
        "total_symbols": len(symbols),
        "success": len(success),
        "failed": len(failed),
        "failed_symbols": failed,
        "output_dir": str(args.csv_dir.expanduser()),
    }
    (args.csv_dir.expanduser() / "nasdaq_update_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

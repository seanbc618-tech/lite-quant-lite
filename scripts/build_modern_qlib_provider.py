#!/usr/bin/env python3
"""Build a small modern Qlib US daily provider from Yahoo Finance data.

The target provider is intentionally separate from the historical Qlib
``us_data`` bundle. It is meant for quick modern-era experiments before taking
on a full universe rebuild.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


DEFAULT_PROVIDER = Path.home() / ".qlib" / "qlib_data" / "us_modern_mega20"
DEFAULT_CSV_DIR = Path.home() / ".qlib" / "stock_data" / "source" / "us_data"
DEFAULT_START = "2018-01-01"
DEFAULT_END = date.today().isoformat()
DEFAULT_MARKET = "mega20"
DEFAULT_FIELDS = ("open", "high", "low", "close", "volume", "vwap", "factor", "change")
MEGA20_SYMBOLS = (
    "SPY",
    "QQQ",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "COST",
    "NFLX",
    "AMD",
    "ADBE",
    "CRM",
    "INTC",
    "CSCO",
    "PEP",
    "QCOM",
    "TXN",
)


@dataclass(frozen=True)
class ProviderBuildSummary:
    provider_uri: Path
    market: str
    symbols: list[str]
    calendar_start: str
    calendar_end: str
    sessions: int
    fields: list[str]


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def normalize_ohlcv(symbol: str, raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        raise ValueError(f"{symbol}: empty data")

    frame = raw.copy()
    if "Date" in frame.columns:
        frame.index = pd.to_datetime(frame.pop("Date"))
    elif "date" in frame.columns:
        frame.index = pd.to_datetime(frame.pop("date"))
    else:
        frame.index = pd.to_datetime(frame.index)

    frame.index = frame.index.tz_localize(None).normalize()
    frame = frame.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adjclose",
            "Volume": "volume",
        }
    )
    required = ["open", "high", "low", "close", "volume"]
    missing = [field for field in required if field not in frame.columns]
    if missing:
        raise ValueError(f"{symbol}: missing columns: {', '.join(missing)}")

    frame = frame[required].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["close"]).sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    if frame.empty:
        raise ValueError(f"{symbol}: no valid close rows")

    frame["factor"] = 1.0
    frame["vwap"] = frame["close"]
    frame["change"] = frame["close"].pct_change()
    return frame.loc[:, list(DEFAULT_FIELDS)]


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_feature_bin(path: Path, start_index: int, values: pd.Series) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = np.hstack([[float(start_index)], values.astype("float32").to_numpy(dtype="float32")])
    payload.astype("<f").tofile(path)


def build_provider_from_frames(
    frames: Mapping[str, pd.DataFrame],
    provider_uri: Path,
    market: str = DEFAULT_MARKET,
) -> ProviderBuildSummary:
    normalized: dict[str, pd.DataFrame] = {}
    for symbol, frame in frames.items():
        normalized_symbol = normalize_symbol(symbol)
        normalized[normalized_symbol] = normalize_ohlcv(normalized_symbol, frame)
    if not normalized:
        raise ValueError("no symbol data to build provider")

    provider_uri.mkdir(parents=True, exist_ok=True)
    calendar_index = sorted({timestamp for frame in normalized.values() for timestamp in frame.index})
    calendar_lines = [timestamp.strftime("%Y-%m-%d") for timestamp in calendar_index]
    date_to_index = {timestamp: index for index, timestamp in enumerate(calendar_index)}

    write_lines(provider_uri / "calendars/day.txt", calendar_lines)

    instrument_lines: list[str] = []
    for symbol in sorted(normalized):
        frame = normalized[symbol]
        start = frame.index.min()
        end = frame.index.max()
        instrument_lines.append(f"{symbol}\t{start:%Y-%m-%d}\t{end:%Y-%m-%d}")

        feature_dir = provider_uri / "features" / symbol.lower()
        symbol_calendar = pd.DatetimeIndex(calendar_index[date_to_index[start] : date_to_index[end] + 1])
        aligned = frame.reindex(symbol_calendar)
        for field in DEFAULT_FIELDS:
            write_feature_bin(feature_dir / f"{field}.day.bin", date_to_index[start], aligned[field])

    write_lines(provider_uri / "instruments" / f"{market}.txt", instrument_lines)
    write_lines(provider_uri / "instruments/all.txt", instrument_lines)

    summary = ProviderBuildSummary(
        provider_uri=provider_uri,
        market=market,
        symbols=sorted(normalized),
        calendar_start=calendar_lines[0],
        calendar_end=calendar_lines[-1],
        sessions=len(calendar_lines),
        fields=list(DEFAULT_FIELDS),
    )
    (provider_uri / "build_summary.json").write_text(json.dumps(asdict(summary), indent=2, default=str), encoding="utf-8")
    return summary


def download_yahoo_frames(symbols: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    frames: dict[str, pd.DataFrame] = {}
    for index, symbol in enumerate(symbols, start=1):
        print(f"[{index}/{len(symbols)}] downloading {symbol} {start}..{end}")
        frame = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=True, progress=False, threads=False)
        if frame.empty:
            print(f"  WARN {symbol}: empty data")
            continue
        frames[symbol] = frame.reset_index()
    return frames


def load_csv_frames(csv_dir: Path, symbols: list[str]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        path = csv_dir.expanduser() / f"{normalize_symbol(symbol)}.csv"
        if not path.is_file():
            print(f"  WARN {symbol}: missing csv {path}")
            continue
        frames[normalize_symbol(symbol)] = pd.read_csv(path)
    return frames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建小规模现代 Qlib 美股日线 provider")
    parser.add_argument("--provider-uri", type=Path, default=DEFAULT_PROVIDER, help="输出 Qlib provider 目录")
    parser.add_argument("--csv-dir", type=Path, default=None, help="从本地 CSV 目录读取 SYMBOL.csv，跳过 Yahoo 下载")
    parser.add_argument("--market", default=DEFAULT_MARKET, help="instrument 文件名")
    parser.add_argument("--start", default=DEFAULT_START, help="开始日期")
    parser.add_argument("--end", default=DEFAULT_END, help="结束日期，按 yfinance 习惯为右开区间")
    parser.add_argument("--symbols", nargs="+", default=list(MEGA20_SYMBOLS), help="标的列表")
    parser.add_argument("--overwrite", action="store_true", help="若 provider 目录已存在则先删除")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider_uri = args.provider_uri.expanduser()
    if provider_uri.exists() and any(provider_uri.iterdir()):
        if not args.overwrite:
            print(f"ERROR provider exists and is not empty: {provider_uri}")
            print("      pass --overwrite to rebuild it")
            return 2
        shutil.rmtree(provider_uri)

    symbols = [normalize_symbol(symbol) for symbol in args.symbols]
    if args.csv_dir is not None:
        frames = load_csv_frames(args.csv_dir, symbols)
    else:
        frames = download_yahoo_frames(symbols, start=args.start, end=args.end)
    try:
        summary = build_provider_from_frames(frames, provider_uri=provider_uri, market=args.market)
    except ValueError as exc:
        print(f"ERROR {exc}")
        return 1
    print(
        "built provider:",
        summary.provider_uri,
        f"symbols={len(summary.symbols)}",
        f"calendar={summary.calendar_start}..{summary.calendar_end}",
        f"sessions={summary.sessions}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

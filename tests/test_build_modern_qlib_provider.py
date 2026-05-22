from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.build_modern_qlib_provider import (
    DEFAULT_FIELDS,
    MEGA20_SYMBOLS,
    build_provider_from_frames,
    load_csv_frames,
    normalize_ohlcv,
)


def read_bin(path: Path) -> tuple[int, list[float]]:
    payload = np.fromfile(path, dtype="<f")
    return int(payload[0]), [float(value) for value in payload[1:]]


def test_normalize_ohlcv_accepts_yfinance_style_columns():
    raw = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-03", "2024-01-02"]),
            "Open": [101.0, 100.0],
            "High": [102.0, 101.0],
            "Low": [99.0, 98.0],
            "Close": [100.5, 99.5],
            "Volume": [2000, 1000],
        }
    )

    normalized = normalize_ohlcv("AAPL", raw)

    assert list(normalized.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert list(normalized.columns) == list(DEFAULT_FIELDS)
    assert normalized.loc[pd.Timestamp("2024-01-02"), "factor"] == 1.0
    assert pd.isna(normalized.loc[pd.Timestamp("2024-01-02"), "change"])
    assert normalized.loc[pd.Timestamp("2024-01-03"), "change"] == (100.5 / 99.5) - 1


def test_build_provider_from_frames_writes_qlib_layout(tmp_path):
    provider = tmp_path / "us_modern_mega20"
    frames = {
        "AAPL": pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03"],
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000, 1200],
            }
        ),
        "MSFT": pd.DataFrame(
            {
                "date": ["2024-01-03", "2024-01-04"],
                "open": [200.0, 201.0],
                "high": [201.0, 202.0],
                "low": [199.0, 200.0],
                "close": [200.5, 201.5],
                "volume": [2000, 2200],
            }
        ),
    }

    summary = build_provider_from_frames(frames, provider_uri=provider, market="mega2")

    assert summary.provider_uri == provider
    assert summary.symbols == ["AAPL", "MSFT"]
    assert summary.calendar_start == "2024-01-02"
    assert summary.calendar_end == "2024-01-04"
    assert summary.sessions == 3
    assert (provider / "calendars/day.txt").read_text(encoding="utf-8").splitlines() == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
    ]
    assert (provider / "instruments/mega2.txt").read_text(encoding="utf-8").splitlines() == [
        "AAPL\t2024-01-02\t2024-01-03",
        "MSFT\t2024-01-03\t2024-01-04",
    ]
    assert (provider / "instruments/all.txt").read_text(encoding="utf-8") == (
        provider / "instruments/mega2.txt"
    ).read_text(encoding="utf-8")

    start_index, close_values = read_bin(provider / "features/aapl/close.day.bin")
    assert start_index == 0
    assert close_values == [100.5, 101.5]

    start_index, msft_open_values = read_bin(provider / "features/msft/open.day.bin")
    assert start_index == 1
    assert msft_open_values == [200.0, 201.0]


def test_default_symbol_list_is_small_and_includes_benchmarks():
    assert len(MEGA20_SYMBOLS) == 20
    assert {"SPY", "QQQ", "AAPL", "MSFT", "NVDA"}.issubset(MEGA20_SYMBOLS)


def test_load_csv_frames_reads_available_symbol_files(tmp_path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    (csv_dir / "AAPL.csv").write_text(
        "date,symbol,open,high,low,close,adjclose,volume\n"
        "2024-01-02,AAPL,1,2,0.5,1.5,1.5,100\n",
        encoding="utf-8",
    )

    frames = load_csv_frames(csv_dir, ["AAPL", "MSFT"])

    assert list(frames) == ["AAPL"]
    assert frames["AAPL"].loc[0, "close"] == 1.5

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.update_nasdaq_csv import merge_csv, parse_nasdaq_rows


def test_parse_nasdaq_rows_normalizes_prices_and_dates():
    rows = [
        {
            "date": "05/22/2026",
            "close": "$745.64",
            "volume": "41,762,010",
            "open": "$746.24",
            "high": "$748.94",
            "low": "$744.48",
        },
        {
            "date": "05/21/2026",
            "close": "742.72",
            "volume": "43,332,230",
            "open": "738.64",
            "high": "744.87",
            "low": "737.03",
        },
    ]

    frame = parse_nasdaq_rows("SPY", rows)

    assert list(frame["date"]) == ["2026-05-21", "2026-05-22"]
    assert list(frame.columns) == ["date", "symbol", "open", "high", "low", "close", "adjclose", "volume"]
    assert frame.loc[0, "symbol"] == "SPY"
    assert frame.loc[0, "close"] == 742.72
    assert frame.loc[1, "volume"] == 41762010


def test_parse_nasdaq_rows_skips_incomplete_rows():
    rows = [
        {
            "date": "05/22/2026",
            "close": "745.64",
            "volume": "N/A",
            "open": "746.24",
            "high": "748.94",
            "low": "744.48",
        },
        {
            "date": "05/21/2026",
            "close": "742.72",
            "volume": "43,332,230",
            "open": "738.64",
            "high": "744.87",
            "low": "737.03",
        },
    ]

    frame = parse_nasdaq_rows("SPY", rows)

    assert list(frame["date"]) == ["2026-05-21"]


def test_merge_csv_keeps_latest_rows_and_sorts(tmp_path):
    path = tmp_path / "AAPL.csv"
    path.write_text(
        "date,symbol,open,high,low,close,adjclose,volume\n"
        "2026-05-21,AAPL,1,2,0.5,1.5,1.5,100\n",
        encoding="utf-8",
    )
    update = pd.DataFrame(
        {
            "date": ["2026-05-21", "2026-05-22"],
            "symbol": ["AAPL", "AAPL"],
            "open": [3.0, 4.0],
            "high": [4.0, 5.0],
            "low": [2.0, 3.0],
            "close": [3.5, 4.5],
            "adjclose": [3.5, 4.5],
            "volume": [300, 400],
        }
    )

    merged = merge_csv(path, update)

    assert list(merged["date"]) == ["2026-05-21", "2026-05-22"]
    assert merged.loc[0, "open"] == 3.0
    assert path.read_text(encoding="utf-8").splitlines()[-1] == "2026-05-22,AAPL,4.0,5.0,3.0,4.5,4.5,400"

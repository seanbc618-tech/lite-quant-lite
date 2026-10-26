"""Verbatim generic definitions selected from scripts/data_report.py."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class CalendarSummary:
    start: str
    end: str
    sessions: int

@dataclass(frozen=True)
class InstrumentSummary:
    market: str
    count: int
    path: Path

def parse_calendar(provider_uri: Path, frequency: str = "day") -> CalendarSummary:
    calendar_file = provider_uri.expanduser() / "calendars" / f"{frequency}.txt"
    lines = [line.strip() for line in calendar_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"calendar file is empty: {calendar_file}")
    return CalendarSummary(start=lines[0], end=lines[-1], sessions=len(lines))

def count_instruments(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

def read_instrument_symbols(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    symbols: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        symbols.add(line.split()[0].upper())
    return symbols

def collect_instrument_summaries(provider_uri: Path, markets: Iterable[str]) -> list[InstrumentSummary]:
    instruments_dir = provider_uri.expanduser() / "instruments"
    return [
        InstrumentSummary(market=market, count=count_instruments(instruments_dir / f"{market}.txt"), path=instruments_dir / f"{market}.txt")
        for market in markets
    ]

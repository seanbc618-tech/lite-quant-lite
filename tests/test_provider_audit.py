"""Two existing data-report tests, with imports redirected only."""
from pathlib import Path
from us_quant.provider_audit import CalendarSummary, InstrumentSummary, parse_calendar, collect_instrument_summaries

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def test_parse_calendar_reads_start_end_and_session_count(tmp_path):
    provider = tmp_path / "us_data"
    write_text(provider / "calendars/day.txt", "\n2020-01-02\n2020-01-03\n")

    summary = parse_calendar(provider)

    assert summary == CalendarSummary(start="2020-01-02", end="2020-01-03", sessions=2)

def test_collect_instrument_summaries_counts_nonempty_rows(tmp_path):
    provider = tmp_path / "us_data"
    write_text(provider / "instruments/sp500.txt", "AAPL\t2000-01-01\t2020-01-03\n\nMSFT\t2000-01-01\t2020-01-03\n")
    write_text(provider / "instruments/nasdaq100.txt", "AAPL\t2000-01-01\t2020-01-03\n# comment\n")

    summaries = collect_instrument_summaries(provider, ["sp500", "nasdaq100", "missing"])

    assert summaries == [
        InstrumentSummary(market="sp500", count=2, path=provider / "instruments/sp500.txt"),
        InstrumentSummary(market="nasdaq100", count=1, path=provider / "instruments/nasdaq100.txt"),
        InstrumentSummary(market="missing", count=0, path=provider / "instruments/missing.txt"),
    ]

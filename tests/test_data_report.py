from __future__ import annotations

from pathlib import Path

from scripts.data_report import (
    CalendarSummary,
    InstrumentSummary,
    WorkflowSummary,
    collect_instrument_summaries,
    data_age_note,
    format_report,
    parse_calendar,
    parse_workflow,
    workflow_status,
)


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


def test_parse_workflow_reads_dates_and_segments(tmp_path):
    workflow = tmp_path / "workflow_demo.yaml"
    write_text(
        workflow,
        """
experiment_name: demo_exp
market: nasdaq100
data_handler_config:
  start_time: 2010-01-01
  end_time: 2020-10-30
task:
  dataset:
    kwargs:
      segments:
        train: [2010-01-01, 2016-12-31]
        valid: [2017-01-01, 2018-12-31]
        test: [2019-01-01, 2020-10-30]
port_analysis_config:
  backtest:
    start_time: 2019-01-01
    end_time: 2020-10-30
""",
    )

    summary = parse_workflow(workflow)

    assert summary == WorkflowSummary(
        path=workflow,
        experiment_name="demo_exp",
        market="nasdaq100",
        handler_start="2010-01-01",
        handler_end="2020-10-30",
        train=("2010-01-01", "2016-12-31"),
        valid=("2017-01-01", "2018-12-31"),
        test=("2019-01-01", "2020-10-30"),
        backtest=("2019-01-01", "2020-10-30"),
    )
    assert workflow_status(summary, "2020-11-10") == "OK"
    assert workflow_status(summary, "2020-09-30") == "EXCEEDS_CALENDAR"


def test_data_age_note_marks_old_calendar_as_stale():
    assert data_age_note("2020-11-10", today="2026-05-23").startswith("STALE")
    assert data_age_note("2026-05-22", today="2026-05-23") == "OK (latest session is 1 days behind 2026-05-23)"


def test_format_report_includes_core_sections(tmp_path):
    workflow = WorkflowSummary(
        path=tmp_path / "workflow_demo.yaml",
        experiment_name="demo_exp",
        market="nasdaq100",
        handler_start="2010-01-01",
        handler_end="2020-10-30",
        train=("2010-01-01", "2016-12-31"),
        valid=("2017-01-01", "2018-12-31"),
        test=("2019-01-01", "2020-10-30"),
        backtest=("2019-01-01", "2020-10-30"),
    )

    report = format_report(
        provider_uri=tmp_path / "us_data",
        calendar=CalendarSummary("2020-01-02", "2020-11-10", 220),
        instruments=[InstrumentSummary("nasdaq100", 101, tmp_path / "nasdaq100.txt")],
        workflows=[workflow],
        symbol_coverages=[],
        today="2026-05-23",
    )

    assert "# Qlib Data Report" in report
    assert "calendar: 2020-01-02 -> 2020-11-10 (220 sessions)" in report
    assert "data_age: STALE" in report
    assert "| nasdaq100 | 101 |" in report
    assert "| workflow_demo.yaml | demo_exp | nasdaq100 | 2020-10-30 |" in report

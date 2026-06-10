from __future__ import annotations

from pathlib import Path

import scripts.health_check as health_check


def test_exit_code_ignores_warnings_when_no_failures():
    results = [
        health_check.CheckResult("local import", "PASS", "ok"),
        health_check.CheckResult("yahoo", "WARN", "rate limited"),
    ]

    assert health_check.exit_code(results) == 0


def test_exit_code_fails_on_failures():
    results = [
        health_check.CheckResult("qlib data", "FAIL", "missing"),
        health_check.CheckResult("yahoo", "WARN", "rate limited"),
    ]

    assert health_check.exit_code(results) == 1


def test_check_signal_file_rejects_missing_orders(tmp_path):
    signal_file = tmp_path / "signals.json"
    signal_file.write_text('{"orders": []}', encoding="utf-8")

    result = health_check.check_signal_file(signal_file)

    assert result.status == "FAIL"
    assert "orders" in result.message


def test_check_provider_freshness_warns_and_fails_by_lag(tmp_path):
    provider = tmp_path / "provider"
    calendar = provider / "calendars"
    calendar.mkdir(parents=True)
    (calendar / "day.txt").write_text("2026-06-01\n", encoding="utf-8")

    warn = health_check.check_provider_freshness(
        provider,
        "modern_freshness",
        warn_days=4,
        fail_days=7,
        today=health_check.date(2026, 6, 6),
    )
    fail = health_check.check_provider_freshness(
        provider,
        "modern_freshness",
        warn_days=4,
        fail_days=7,
        today=health_check.date(2026, 6, 10),
    )

    assert warn.status == "WARN"
    assert fail.status == "FAIL"


def test_check_qlib_dir_reports_missing_subdirectories(tmp_path):
    (tmp_path / "calendars").mkdir()
    (tmp_path / "features").mkdir()

    result = health_check.check_qlib_dir(Path(tmp_path))

    assert result.status == "FAIL"
    assert "instruments" in result.message

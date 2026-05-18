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


def test_check_qlib_dir_reports_missing_subdirectories(tmp_path):
    (tmp_path / "calendars").mkdir()
    (tmp_path / "features").mkdir()

    result = health_check.check_qlib_dir(Path(tmp_path))

    assert result.status == "FAIL"
    assert "instruments" in result.message

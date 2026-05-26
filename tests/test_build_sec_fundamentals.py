from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_sec_fundamentals import (
    build_fundamentals_dataset,
    load_or_fetch_json,
    main,
    validate_user_agent,
)
from tests.test_fundamentals import companyfacts_fixture


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_provider(path: Path) -> None:
    instruments = path / "instruments" / "liquid100.txt"
    instruments.parent.mkdir(parents=True)
    instruments.write_text(
        "SPY\t2025-04-24\t2025-05-10\nQQQ\t2025-04-24\t2025-05-10\nAAPL\t2025-04-24\t2025-05-10\n",
        encoding="utf-8",
    )
    calendar = path / "calendars" / "day.txt"
    calendar.parent.mkdir(parents=True)
    calendar.write_text("2025-04-24\n2025-04-25\n2025-05-09\n", encoding="utf-8")


def test_validate_user_agent_requires_contact_for_live_sec_requests():
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        validate_user_agent(None)
    with pytest.raises(ValueError, match="contact"):
        validate_user_agent("lite-quant-lite research")

    assert validate_user_agent("lite-quant-lite research contact@example.com") == (
        "lite-quant-lite research contact@example.com"
    )


def test_load_or_fetch_json_uses_cached_data_without_user_agent(tmp_path: Path):
    path = tmp_path / "cached.json"
    write_json(path, {"cached": True})

    assert load_or_fetch_json("https://data.sec.gov/example.json", path) == {"cached": True}


def test_live_fetch_throttles_and_retries_transient_sec_failure(tmp_path: Path):
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self):
            self.responses = [FakeResponse(503, {}), FakeResponse(200, {"live": True})]
            self.headers = []

        def get(self, _url: str, headers: dict) -> FakeResponse:
            self.headers.append(headers)
            return self.responses.pop(0)

    waits = []
    client = FakeClient()

    payload = load_or_fetch_json(
        "https://data.sec.gov/example.json",
        tmp_path / "live.json",
        user_agent="lite-quant-lite research contact@example.com",
        client=client,
        sleep=waits.append,
    )

    assert payload == {"live": True}
    assert len(client.headers) == 2
    assert client.headers[0]["User-Agent"] == "lite-quant-lite research contact@example.com"
    assert waits == [0.12, 0.5]


def test_build_fundamentals_dataset_from_cached_sec_payloads(tmp_path: Path):
    provider = tmp_path / "provider"
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "facts"
    report_path = tmp_path / "reports" / "latest.md"
    make_provider(provider)
    write_json(
        raw_dir / "ticker_mapping.json",
        {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple", "AAPL", "Nasdaq"]]},
    )
    write_json(raw_dir / "0000320193" / "companyfacts.json", companyfacts_fixture())
    write_json(raw_dir / "0000320193" / "submissions.json", {"cik": "0000320193"})

    summary = build_fundamentals_dataset(
        provider_uri=provider,
        raw_dir=raw_dir,
        output_dir=output_dir,
        report_path=report_path,
    )

    assert summary.requested_symbols == ["AAPL"]
    assert summary.covered_symbols == ["AAPL"]
    assert summary.errors == []
    facts = pd.read_parquet(output_dir / "sec_facts.parquet")
    daily = pd.read_parquet(output_dir / "quality_daily.parquet")
    assert set(facts["field"]) >= {"revenue", "net_income", "stockholders_equity"}
    assert daily["session"].tolist() == [pd.Timestamp("2025-04-25"), pd.Timestamp("2025-05-09")]
    report = report_path.read_text(encoding="utf-8")
    assert "# SEC Fundamentals Quality Report" in report
    assert "AAPL" in report
    assert "SPY" not in report
    assert "current-universe survivorship bias" in report
    assert "## Daily Metric Coverage" in report
    assert "period-normalized metrics" in report
    assert "| AAPL | 2 | 100.0% | 100.0% | 100.0% | Q1 |" in report


def test_repeated_same_universe_build_reuses_normalized_facts_without_raw_sec_files(tmp_path: Path):
    provider = tmp_path / "provider"
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "facts"
    report_path = tmp_path / "reports" / "latest.md"
    make_provider(provider)
    write_json(
        raw_dir / "ticker_mapping.json",
        {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple", "AAPL", "Nasdaq"]]},
    )
    write_json(raw_dir / "0000320193" / "companyfacts.json", companyfacts_fixture())
    write_json(raw_dir / "0000320193" / "submissions.json", {"cik": "0000320193"})
    build_fundamentals_dataset(
        provider_uri=provider,
        raw_dir=raw_dir,
        output_dir=output_dir,
        report_path=report_path,
    )
    shutil.rmtree(raw_dir)

    summary = build_fundamentals_dataset(
        provider_uri=provider,
        raw_dir=raw_dir,
        output_dir=output_dir,
        report_path=report_path,
    )

    assert summary.facts_source == "normalized parquet cache"
    assert "facts_source: normalized parquet cache" in report_path.read_text(encoding="utf-8")


def test_build_fails_if_uncached_live_request_has_no_sec_contact_identity(tmp_path: Path):
    provider = tmp_path / "provider"
    raw_dir = tmp_path / "raw"
    make_provider(provider)
    write_json(
        raw_dir / "ticker_mapping.json",
        {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple", "AAPL", "Nasdaq"]]},
    )

    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        build_fundamentals_dataset(
            provider_uri=provider,
            raw_dir=raw_dir,
            output_dir=tmp_path / "facts",
            report_path=tmp_path / "latest.md",
        )


def test_cli_main_builds_outputs_entirely_from_cached_sec_payloads(tmp_path: Path, monkeypatch, capsys):
    provider = tmp_path / "provider"
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "facts"
    report_path = tmp_path / "latest.md"
    make_provider(provider)
    write_json(
        raw_dir / "ticker_mapping.json",
        {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple", "AAPL", "Nasdaq"]]},
    )
    write_json(raw_dir / "0000320193" / "companyfacts.json", companyfacts_fixture())
    write_json(raw_dir / "0000320193" / "submissions.json", {"cik": "0000320193"})
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_sec_fundamentals.py",
            "--provider-uri",
            str(provider),
            "--raw-dir",
            str(raw_dir),
            "--output-dir",
            str(output_dir),
            "--report",
            str(report_path),
        ],
    )

    assert main() == 0
    output = capsys.readouterr().out
    assert "Facts:" in output
    assert (output_dir / "sec_facts.parquet").is_file()
    assert report_path.is_file()

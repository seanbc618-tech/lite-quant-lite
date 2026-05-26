from __future__ import annotations

from pathlib import Path

import pandas as pd

from us_quant.fundamentals import (
    FACT_COLUMNS,
    build_cik_mapping,
    build_daily_quality_snapshot,
    extract_canonical_facts,
    read_investable_symbols,
)


def sec_fact(value, filed, accession, tag_context=None, form="10-Q", period_end="2025-03-31"):
    record = {
        "val": value,
        "end": period_end,
        "filed": filed,
        "form": form,
        "fp": "Q1",
        "accn": accession,
    }
    if tag_context:
        record["frame"] = tag_context
    return record


def companyfacts_fixture() -> dict:
    accession = "0000320193-25-000010"
    filed = "2025-04-25"
    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [sec_fact(100.0, filed, accession)]}
                },
                "Revenues": {"units": {"USD": [sec_fact(999.0, filed, accession)]}},
                "NetIncomeLoss": {"units": {"USD": [sec_fact(10.0, filed, accession)]}},
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"USD": [sec_fact(12.0, filed, accession)]}
                },
                "Assets": {"units": {"USD": [sec_fact(200.0, filed, accession)]}},
                "Liabilities": {"units": {"USD": [sec_fact(80.0, filed, accession)]}},
                "StockholdersEquity": {"units": {"USD": [sec_fact(100.0, filed, accession)]}},
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {"shares": [sec_fact(5.0, filed, accession)]}
                }
            },
        }
    }


def foreign_us_gaap_fixture() -> dict:
    accession = "0000937966-26-000005"
    filed = "2026-02-11"
    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"EUR": [sec_fact(100.0, filed, accession, form="20-F")]}
                },
                "NetIncomeLoss": {"units": {"EUR": [sec_fact(10.0, filed, accession, form="20-F")]}},
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"EUR": [sec_fact(12.0, filed, accession, form="20-F")]}
                },
                "Assets": {"units": {"EUR": [sec_fact(200.0, filed, accession, form="20-F")]}},
                "Liabilities": {"units": {"EUR": [sec_fact(80.0, filed, accession, form="20-F")]}},
                "StockholdersEquity": {"units": {"EUR": [sec_fact(100.0, filed, accession, form="20-F")]}},
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {"shares": [sec_fact(5.0, filed, accession, form="20-F")]}
                }
            },
        }
    }


def ifrs_fixture() -> dict:
    accession = "0000901832-26-000010"
    filed = "2026-02-10"
    return {
        "facts": {
            "ifrs-full": {
                "Revenue": {"units": {"USD": [sec_fact(100.0, filed, accession, form="20-F")]}},
                "ProfitLoss": {"units": {"USD": [sec_fact(10.0, filed, accession, form="20-F")]}},
                "CashFlowsFromUsedInOperatingActivities": {
                    "units": {"USD": [sec_fact(12.0, filed, accession, form="20-F")]}
                },
                "Assets": {"units": {"USD": [sec_fact(200.0, filed, accession, form="20-F")]}},
                "Liabilities": {"units": {"USD": [sec_fact(80.0, filed, accession, form="20-F")]}},
                "Equity": {"units": {"USD": [sec_fact(100.0, filed, accession, form="20-F")]}},
            }
        }
    }


def canonical_fact(
    field: str,
    value: float,
    *,
    filed: str,
    accession: str,
    form: str,
    fiscal_period: str,
    period_start: str | None,
    period_end: str,
) -> dict:
    return {
        "ticker": "DEMO",
        "cik": "0000000001",
        "field": field,
        "value": value,
        "unit": "USD",
        "form": form,
        "fiscal_period": fiscal_period,
        "period_start": pd.to_datetime(period_start),
        "period_end": pd.to_datetime(period_end),
        "filed_date": pd.to_datetime(filed),
        "accession_number": accession,
        "tag": field,
    }


def bridge_facts(*, include_prior_fy: bool = True, include_liabilities: bool = True) -> pd.DataFrame:
    rows: list[dict] = []
    if include_prior_fy:
        rows.extend(
            canonical_fact(
                field,
                value,
                filed="2025-02-15",
                accession="fy-2024",
                form="10-K",
                fiscal_period="FY",
                period_start="2024-01-01" if field in {"revenue", "net_income", "operating_cash_flow"} else None,
                period_end="2024-12-31",
            )
            for field, value in {
                "revenue": 400.0,
                "net_income": 100.0,
                "operating_cash_flow": 120.0,
                "total_assets": 350.0,
                "total_liabilities": 140.0,
                "stockholders_equity": 210.0,
            }.items()
        )
    for period_end, values in (
        ("2024-06-30", {"revenue": 190.0, "net_income": 60.0, "operating_cash_flow": 65.0}),
        (
            "2025-06-30",
            {
                "revenue": 230.0,
                "net_income": 70.0,
                "operating_cash_flow": 80.0,
                "total_assets": 400.0,
                "stockholders_equity": 200.0,
                **({"total_liabilities": 150.0} if include_liabilities else {}),
            },
        ),
    ):
        rows.extend(
            canonical_fact(
                field,
                value,
                filed="2025-08-01",
                accession="q2-2025",
                form="10-Q",
                fiscal_period="Q2",
                period_start=f"{period_end[:4]}-01-01"
                if field in {"revenue", "net_income", "operating_cash_flow"}
                else None,
                period_end=period_end,
            )
            for field, value in values.items()
        )
    return pd.DataFrame(rows, columns=FACT_COLUMNS)


def test_build_cik_mapping_reads_official_fields_data_shape_and_pads_values():
    payload = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"], [789019, "Microsoft", "MSFT", "Nasdaq"]],
    }

    assert build_cik_mapping(payload) == {"AAPL": "0000320193", "MSFT": "0000789019"}


def test_read_investable_symbols_excludes_benchmark_etfs(tmp_path: Path):
    instrument = tmp_path / "instruments" / "liquid100.txt"
    instrument.parent.mkdir(parents=True)
    instrument.write_text(
        "SPY\t2020-01-01\t2026-05-22\nAAPL\t2020-01-01\t2026-05-22\nQQQ\t2020-01-01\t2026-05-22\nMSFT\t2020-01-01\t2026-05-22\n",
        encoding="utf-8",
    )

    assert read_investable_symbols(tmp_path) == ["AAPL", "MSFT"]


def test_extract_canonical_facts_prefers_primary_tag_and_retains_filing_metadata():
    facts = extract_canonical_facts("aapl", "0000320193", companyfacts_fixture())

    assert set(facts["field"]) == {
        "revenue",
        "net_income",
        "operating_cash_flow",
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
        "shares_outstanding",
    }
    revenue = facts.loc[facts["field"] == "revenue"].iloc[0]
    assert revenue["ticker"] == "AAPL"
    assert revenue["value"] == 100.0
    assert revenue["tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert revenue["accession_number"] == "0000320193-25-000010"
    assert revenue["filed_date"] == pd.Timestamp("2025-04-25")


def test_extract_canonical_facts_accepts_foreign_issuer_forms_and_non_usd_reporting_currency():
    facts = extract_canonical_facts("ASML", "0000937966", foreign_us_gaap_fixture())

    assert set(facts["field"]) == {
        "revenue",
        "net_income",
        "operating_cash_flow",
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
        "shares_outstanding",
    }
    assert set(facts.loc[facts["field"] != "shares_outstanding", "unit"]) == {"EUR"}
    daily = build_daily_quality_snapshot(facts, ["2026-02-11"])
    assert daily.loc[0, "roe"] == 0.10


def test_extract_canonical_facts_maps_ifrs_full_quality_fields():
    facts = extract_canonical_facts("AZN", "0000901832", ifrs_fixture())

    assert set(facts["field"]) == {
        "revenue",
        "net_income",
        "operating_cash_flow",
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
    }
    daily = build_daily_quality_snapshot(facts, ["2026-02-10"])
    assert daily.loc[0, "cash_conversion"] == 1.2
    assert daily.loc[0, "debt_to_assets"] == 0.4


def test_extract_canonical_facts_prefers_usd_when_dual_currency_is_reported():
    fixture = foreign_us_gaap_fixture()
    for payload in fixture["facts"]["us-gaap"].values():
        payload["units"]["USD"] = [sec_fact(200.0, "2026-02-11", "0000937966-26-000005", form="20-F")]

    facts = extract_canonical_facts("BIDU", "0001329099", fixture)

    assert set(facts.loc[facts["field"] != "shares_outstanding", "unit"]) == {"USD"}


def test_daily_quality_snapshot_uses_only_facts_visible_by_filing_date():
    original = extract_canonical_facts("AAPL", "0000320193", companyfacts_fixture())
    amendment = original.copy()
    amendment["filed_date"] = pd.Timestamp("2025-05-10")
    amendment["accession_number"] = "0000320193-25-000020"
    amendment.loc[amendment["field"] == "net_income", "value"] = 12.0
    amendment.loc[amendment["field"] == "operating_cash_flow", "value"] = 15.0
    all_facts = pd.concat([original, amendment], ignore_index=True)

    daily = build_daily_quality_snapshot(
        all_facts,
        ["2025-04-24", "2025-04-25", "2025-05-09", "2025-05-10"],
    )

    assert daily["session"].tolist() == [
        pd.Timestamp("2025-04-25"),
        pd.Timestamp("2025-05-09"),
        pd.Timestamp("2025-05-10"),
    ]
    assert daily["accession_number"].tolist() == [
        "0000320193-25-000010",
        "0000320193-25-000010",
        "0000320193-25-000020",
    ]
    assert daily["roe"].tolist() == [0.10, 0.10, 0.12]
    assert daily["cash_conversion"].tolist() == [1.2, 1.2, 1.25]
    assert daily["debt_to_assets"].tolist() == [0.4, 0.4, 0.4]


def test_daily_quality_snapshot_keeps_incomplete_filing_as_auditable_row():
    incomplete = extract_canonical_facts(
        "AAPL",
        "0000320193",
        {
            "facts": {
                "us-gaap": {
                    "NetIncomeLoss": {
                        "units": {"USD": [sec_fact(10.0, "2025-04-25", "0000320193-25-000010")]}
                    }
                }
            }
        },
    )

    daily = build_daily_quality_snapshot(incomplete, ["2025-04-25"])

    assert daily.loc[0, "available_fields"] == 1
    assert pd.isna(daily.loc[0, "roe"])
    assert pd.isna(daily.loc[0, "cash_conversion"])


def test_daily_quality_snapshot_selects_complete_period_not_later_share_context():
    facts = extract_canonical_facts("AAPL", "0000320193", companyfacts_fixture())
    later_shares = facts.loc[facts["field"] == "shares_outstanding"].copy()
    later_shares["period_end"] = pd.Timestamp("2025-04-20")
    facts = pd.concat([facts, later_shares], ignore_index=True)

    daily = build_daily_quality_snapshot(facts, ["2025-04-25"])

    assert daily.loc[0, "period_end"] == pd.Timestamp("2025-03-31")
    assert daily.loc[0, "roe"] == 0.10
    assert daily.loc[0, "available_fields"] == 7


def test_daily_quality_snapshot_aligns_duration_metrics_to_longest_same_period_window():
    facts = extract_canonical_facts("AAPL", "0000320193", companyfacts_fixture())
    facts.loc[
        facts["field"].isin(["net_income", "operating_cash_flow"]),
        "period_start",
    ] = pd.Timestamp("2024-10-01")
    quarterly_income = facts.loc[facts["field"] == "net_income"].copy()
    quarterly_income["value"] = 4.0
    quarterly_income["period_start"] = pd.Timestamp("2025-01-01")
    facts = pd.concat([quarterly_income, facts], ignore_index=True)

    daily = build_daily_quality_snapshot(facts, ["2025-04-25"])

    assert daily.loc[0, "cash_conversion"] == 1.2


def test_daily_quality_snapshot_emits_direct_fy_and_quarterly_ttm_bridge():
    daily = build_daily_quality_snapshot(bridge_facts(), ["2025-02-15", "2025-08-01"])
    fiscal_year = daily.loc[daily["session"] == pd.Timestamp("2025-02-15")].iloc[0]
    quarter = daily.loc[daily["session"] == pd.Timestamp("2025-08-01")].iloc[0]

    assert fiscal_year["ttm_source"] == "reported_fy"
    assert fiscal_year["net_income_ttm"] == 100.0
    assert quarter["ttm_source"] == "fy_plus_ytd_bridge"
    assert quarter["revenue_ttm"] == 440.0
    assert quarter["net_income_ttm"] == 110.0
    assert quarter["operating_cash_flow_ttm"] == 135.0
    assert quarter["roe_ttm"] == 0.55
    assert quarter["cash_conversion_ttm"] == 135.0 / 110.0


def test_daily_quality_snapshot_leaves_ttm_missing_when_bridge_has_no_prior_fy():
    daily = build_daily_quality_snapshot(bridge_facts(include_prior_fy=False), ["2025-08-01"])
    quarter = daily.iloc[0]

    assert pd.isna(quarter["net_income_ttm"])
    assert quarter["ttm_source"] == "missing"


def test_daily_quality_snapshot_does_not_bridge_with_future_fiscal_year_filing():
    facts = bridge_facts()
    facts.loc[facts["accession_number"] == "fy-2024", "filed_date"] = pd.Timestamp("2025-08-02")

    daily = build_daily_quality_snapshot(facts, ["2025-08-01"])

    assert pd.isna(daily.loc[0, "net_income_ttm"])
    assert daily.loc[0, "ttm_source"] == "missing"


def test_daily_quality_snapshot_records_bridge_source_when_only_some_ttm_fields_are_available():
    facts = bridge_facts()
    facts = facts.loc[facts["field"] != "revenue"]

    daily = build_daily_quality_snapshot(facts, ["2025-08-01"])

    assert pd.isna(daily.loc[0, "revenue_ttm"])
    assert daily.loc[0, "net_income_ttm"] == 110.0
    assert daily.loc[0, "ttm_source"] == "fy_plus_ytd_bridge"


def test_daily_quality_snapshot_marks_reported_and_derived_leverage_sources():
    reported = build_daily_quality_snapshot(bridge_facts(), ["2025-08-01"]).iloc[0]
    derived = build_daily_quality_snapshot(bridge_facts(include_liabilities=False), ["2025-08-01"]).iloc[0]
    incomplete_facts = bridge_facts(include_liabilities=False)
    incomplete_facts = incomplete_facts.loc[incomplete_facts["field"] != "stockholders_equity"]
    missing = build_daily_quality_snapshot(incomplete_facts, ["2025-08-01"]).iloc[0]

    assert reported["debt_to_assets"] == 150.0 / 400.0
    assert reported["debt_to_assets_source"] == "reported"
    assert derived["debt_to_assets"] == 0.5
    assert derived["debt_to_assets_source"] == "derived_assets_minus_equity"
    assert pd.isna(missing["debt_to_assets"])
    assert missing["debt_to_assets_source"] == "missing"

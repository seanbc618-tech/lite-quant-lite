"""Point-in-time SEC fundamentals normalization for quality research."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


EXCLUDED_BENCHMARK_FUNDS = frozenset({"SPY", "QQQ"})
ACCEPTED_FORMS = frozenset({"10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "20-F/A", "6-K", "6-K/A"})
FACT_COLUMNS = [
    "ticker",
    "cik",
    "field",
    "value",
    "unit",
    "form",
    "fiscal_period",
    "period_start",
    "period_end",
    "filed_date",
    "accession_number",
    "tag",
]
FIELD_TAGS: dict[str, tuple[tuple[str, str], ...]] = {
    "revenue": (
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
        ("ifrs-full", "RevenueFromContractsWithCustomers"),
        ("ifrs-full", "Revenue"),
    ),
    "net_income": (
        ("us-gaap", "NetIncomeLoss"),
        ("us-gaap", "ProfitLoss"),
        ("ifrs-full", "ProfitLoss"),
        ("ifrs-full", "ProfitLossAttributableToOwnersOfParent"),
    ),
    "operating_cash_flow": (
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
        ("ifrs-full", "CashFlowsFromUsedInOperations"),
    ),
    "total_assets": (("us-gaap", "Assets"), ("ifrs-full", "Assets")),
    "total_liabilities": (("us-gaap", "Liabilities"), ("ifrs-full", "Liabilities")),
    "stockholders_equity": (
        ("us-gaap", "StockholdersEquity"),
        (
            "us-gaap",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        ("ifrs-full", "Equity"),
        ("ifrs-full", "EquityAttributableToOwnersOfParent"),
    ),
    "shares_outstanding": (
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesOutstanding"),
    ),
}
MONETARY_FIELDS = frozenset(FIELD_TAGS) - {"shares_outstanding"}


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def _normalize_cik(cik: Any) -> str:
    return str(int(cik)).zfill(10)


def build_cik_mapping(payload: dict[str, Any]) -> dict[str, str]:
    """Build ticker-to-CIK mapping from either supported SEC ticker JSON shape."""
    mapping: dict[str, str] = {}
    if "fields" in payload and "data" in payload:
        fields = list(payload["fields"])
        ticker_index = fields.index("ticker")
        cik_index = fields.index("cik")
        records = ((row[ticker_index], row[cik_index]) for row in payload["data"])
    else:
        records = (
            (record["ticker"], record.get("cik_str", record.get("cik")))
            for record in payload.values()
            if isinstance(record, dict) and "ticker" in record
        )
    for ticker, cik in records:
        if ticker and cik is not None:
            mapping[_normalize_symbol(str(ticker))] = _normalize_cik(cik)
    return mapping


def read_investable_symbols(provider_uri: Path, market: str = "liquid100") -> list[str]:
    """Read the current provider universe while leaving ETFs as benchmarks only."""
    path = Path(provider_uri).expanduser() / "instruments" / f"{market}.txt"
    symbols = {
        _normalize_symbol(line.split("\t", 1)[0])
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    return sorted(symbols - EXCLUDED_BENCHMARK_FUNDS)


def _select_monetary_unit(all_facts: dict[str, Any]) -> str | None:
    units: set[str] = set()
    for field in MONETARY_FIELDS:
        for taxonomy, tag in FIELD_TAGS[field]:
            tag_units = all_facts.get(taxonomy, {}).get(tag, {}).get("units", {})
            for unit, records in tag_units.items():
                if any(record.get("form") in ACCEPTED_FORMS for record in records):
                    units.add(unit)
    if not units:
        return None
    for preferred in ("USD", "EUR", "CNY", "GBP"):
        if preferred in units:
            return preferred
    return sorted(units)[0]


def extract_canonical_facts(ticker: str, cik: str, companyfacts: dict[str, Any]) -> pd.DataFrame:
    """Normalize selected SEC facts and expose the tag used for each observation."""
    rows: list[dict[str, Any]] = []
    all_facts = companyfacts.get("facts", {})
    monetary_unit = _select_monetary_unit(all_facts)
    for field, tags in FIELD_TAGS.items():
        unit = "shares" if field == "shares_outstanding" else monetary_unit
        if unit is None:
            continue
        for priority, (taxonomy, tag) in enumerate(tags):
            records = all_facts.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, [])
            for record in records:
                if record.get("form") not in ACCEPTED_FORMS:
                    continue
                if record.get("filed") is None or record.get("end") is None or record.get("val") is None:
                    continue
                rows.append(
                    {
                        "ticker": _normalize_symbol(ticker),
                        "cik": _normalize_cik(cik),
                        "field": field,
                        "value": float(record["val"]),
                        "unit": unit,
                        "form": record["form"],
                        "fiscal_period": record.get("fp"),
                        "period_start": pd.to_datetime(record.get("start")),
                        "period_end": pd.to_datetime(record["end"]),
                        "filed_date": pd.to_datetime(record["filed"]),
                        "accession_number": record.get("accn", ""),
                        "tag": tag,
                        "_priority": priority,
                    }
                )
    if not rows:
        return pd.DataFrame(columns=FACT_COLUMNS)
    frame = pd.DataFrame(rows).sort_values(
        ["field", "filed_date", "period_end", "accession_number", "_priority"]
    )
    observation_key = [
        "ticker",
        "field",
        "form",
        "fiscal_period",
        "period_start",
        "period_end",
        "filed_date",
        "accession_number",
    ]
    frame = frame.drop_duplicates(observation_key, keep="first")
    return frame.loc[:, FACT_COLUMNS].sort_values(["filed_date", "field"]).reset_index(drop=True)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator / denominator.replace(0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


def build_daily_quality_snapshot(facts: pd.DataFrame, sessions: Iterable[str | pd.Timestamp]) -> pd.DataFrame:
    """Build daily filing-visible ratio snapshots without future-data leakage."""
    columns = [
        "session",
        "ticker",
        "cik",
        "filed_date",
        "period_end",
        "form",
        "fiscal_period",
        "accession_number",
        "roe",
        "cash_conversion",
        "debt_to_assets",
        "available_fields",
    ]
    if facts.empty:
        return pd.DataFrame(columns=columns)

    frame = facts.copy()
    frame["filed_date"] = pd.to_datetime(frame["filed_date"])
    frame["period_end"] = pd.to_datetime(frame["period_end"])
    frame["period_start"] = pd.to_datetime(frame["period_start"])
    group_columns = [
        "ticker",
        "cik",
        "filed_date",
        "period_end",
        "form",
        "fiscal_period",
        "accession_number",
    ]
    frame["_period_start_sort"] = frame["period_start"].fillna(frame["period_end"])
    frame = frame.sort_values([*group_columns, "field", "_period_start_sort"])
    filing = (
        frame.pivot_table(index=group_columns, columns="field", values="value", aggfunc="first")
        .reset_index()
    )
    for field in FIELD_TAGS:
        if field not in filing:
            filing[field] = np.nan
    filing["roe"] = _safe_ratio(filing["net_income"], filing["stockholders_equity"])
    filing["cash_conversion"] = _safe_ratio(filing["operating_cash_flow"], filing["net_income"])
    filing["debt_to_assets"] = _safe_ratio(filing["total_liabilities"], filing["total_assets"])
    filing["available_fields"] = filing.notna().loc[:, list(FIELD_TAGS)].sum(axis=1)
    filing["_available_metrics"] = filing[["roe", "cash_conversion", "debt_to_assets"]].notna().sum(axis=1)
    filing = (
        filing.sort_values(
            ["ticker", "filed_date", "accession_number", "_available_metrics", "available_fields", "period_end"]
        )
        .groupby(["ticker", "filed_date", "accession_number"], dropna=False, as_index=False)
        .tail(1)
        .sort_values(["ticker", "filed_date", "period_end", "accession_number"])
    )

    session_frame = pd.DataFrame({"session": sorted(pd.to_datetime(list(sessions)))})
    snapshots: list[pd.DataFrame] = []
    for _, history in filing.groupby("ticker", sort=True):
        history = history.sort_values(["filed_date", "period_end", "accession_number"])
        visible = pd.merge_asof(
            session_frame,
            history,
            left_on="session",
            right_on="filed_date",
            direction="backward",
        ).dropna(subset=["filed_date"])
        if not visible.empty:
            snapshots.append(visible.loc[:, columns])
    if not snapshots:
        return pd.DataFrame(columns=columns)
    return pd.concat(snapshots, ignore_index=True).sort_values(["session", "ticker"]).reset_index(drop=True)

"""Lightweight stock valuation helpers built around ValueInvest.

The wrapper keeps data acquisition separate from valuation math. JSON/manual
inputs are deterministic and testable; Yahoo is treated as an optional,
best-effort source by the CLI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Iterable

from valueinvest import Stock, ValuationEngine
from valueinvest.data.fetcher.yfinance import YFinanceFetcher


DEFAULT_VALUATION_METHODS = [
    "graham_number",
    "dcf",
    "reverse_dcf",
    "owner_earnings",
    "altman_z",
    "piotroski_f",
]


@dataclass(frozen=True)
class ValuationMethodResult:
    method_key: str
    method: str
    fair_value: float
    current_price: float
    premium_discount: float
    assessment: str
    confidence: str
    applicability: str
    missing_fields: list[str]


@dataclass(frozen=True)
class ValuationReport:
    ticker: str
    name: str
    current_price: float
    currency: str
    exchange: str
    source: str
    results: list[ValuationMethodResult]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "current_price": self.current_price,
            "currency": self.currency,
            "exchange": self.exchange,
            "source": self.source,
            "results": [asdict(result) for result in self.results],
            "warnings": self.warnings,
            "errors": self.errors,
        }


def build_stock(data: dict[str, Any]) -> Stock:
    """Build a ValueInvest Stock from a plain mapping.

    Extra keys are ignored so callers can pass raw records from JSON or fetchers
    without pre-cleaning every field.
    """
    allowed = {field.name for field in fields(Stock)}
    clean = {key: value for key, value in data.items() if key in allowed}
    if "ticker" in clean and isinstance(clean["ticker"], str):
        clean["ticker"] = clean["ticker"].upper()
    return Stock(**clean)


def parse_methods(methods: str | Iterable[str] | None) -> list[str]:
    if methods is None:
        return list(DEFAULT_VALUATION_METHODS)
    if isinstance(methods, str):
        return [item.strip() for item in methods.split(",") if item.strip()]
    return [str(item).strip() for item in methods if str(item).strip()]


def run_valuation(
    stock: Stock,
    methods: str | Iterable[str] | None = None,
    source: str = "manual",
) -> ValuationReport:
    method_keys = parse_methods(methods)
    engine = ValuationEngine()
    raw_results = engine.run_multiple(stock, method_keys)

    results = [
        ValuationMethodResult(
            method_key=method_key,
            method=result.method,
            fair_value=float(result.fair_value),
            current_price=float(result.current_price),
            premium_discount=float(result.premium_discount),
            assessment=result.assessment,
            confidence=result.confidence,
            applicability=result.applicability,
            missing_fields=list(result.missing_fields),
        )
        for method_key, result in zip(method_keys, raw_results)
    ]

    return ValuationReport(
        ticker=stock.ticker,
        name=stock.name,
        current_price=float(stock.current_price),
        currency=stock.currency,
        exchange=stock.exchange,
        source=source,
        results=results,
        warnings=list(stock.warnings),
        errors=[],
    )


def fetch_yahoo_stock(symbol: str) -> tuple[Stock | None, list[str]]:
    """Fetch a stock through ValueInvest's yfinance adapter.

    Returns errors instead of raising so callers can treat Yahoo as best-effort.
    """
    fetcher = YFinanceFetcher()
    result = fetcher.fetch_all(symbol.upper())
    if not result.success:
        return None, result.errors or [f"Yahoo fetch failed for {symbol.upper()}"]
    stock = build_stock(result.data)
    return stock, result.errors


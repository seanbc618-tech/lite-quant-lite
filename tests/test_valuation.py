from __future__ import annotations

from us_quant.valuation import (
    DEFAULT_VALUATION_METHODS,
    build_stock,
    run_valuation,
)


def stock_fixture() -> dict:
    return {
        "ticker": "demo",
        "name": "Demo Compounder",
        "current_price": 100.0,
        "shares_outstanding": 1_000_000_000,
        "eps": 6.0,
        "bvps": 25.0,
        "revenue": 10_000_000_000,
        "net_income": 1_000_000_000,
        "fcf": 900_000_000,
        "total_assets": 8_000_000_000,
        "current_assets": 3_000_000_000,
        "total_liabilities": 2_000_000_000,
        "current_liabilities": 1_000_000_000,
        "net_debt": -500_000_000,
        "operating_cash_flow": 1_200_000_000,
        "capex": 300_000_000,
        "growth_rate": 8.0,
        "growth_rate_1_5": 8.0,
        "growth_rate_6_10": 4.0,
        "discount_rate": 10.0,
        "terminal_growth": 2.5,
        "currency": "USD",
        "exchange": "NASDAQ",
        "unknown_field": "ignored",
    }


def test_build_stock_filters_extra_fields_and_normalizes_ticker():
    stock = build_stock(stock_fixture())

    assert stock.ticker == "DEMO"
    assert stock.name == "Demo Compounder"
    assert stock.current_price == 100.0
    assert stock.currency == "USD"
    assert not hasattr(stock, "unknown_field")


def test_run_valuation_returns_selected_methods():
    stock = build_stock(stock_fixture())

    report = run_valuation(stock, methods=["graham_number", "dcf"])

    assert report.ticker == "DEMO"
    assert report.current_price == 100.0
    assert [item.method_key for item in report.results] == ["graham_number", "dcf"]
    assert all(item.method for item in report.results)
    assert all(item.current_price == 100.0 for item in report.results)
    assert report.errors == []


def test_default_methods_are_small_probe_set():
    assert DEFAULT_VALUATION_METHODS == [
        "graham_number",
        "dcf",
        "reverse_dcf",
        "owner_earnings",
        "altman_z",
        "piotroski_f",
    ]

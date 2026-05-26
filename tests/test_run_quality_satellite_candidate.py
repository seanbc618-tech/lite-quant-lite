from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from scripts.run_quality_satellite_candidate import (
    PromotionCheck,
    StressRow,
    assess_promotion,
    build_benchmark_returns,
    build_stress_rows,
    build_monthly_targets,
    read_monitor_evaluation_session,
    read_lightgbm_reference,
    render_report,
    score_snapshot,
    simulate_portfolio,
)


def quality_row(
    session: str,
    ticker: str,
    *,
    roe: float = 0.20,
    cash_conversion: float = 1.20,
    debt_to_assets: float = 0.30,
    leverage_source: str = "reported",
    net_income: float = 10.0,
) -> dict:
    return {
        "session": pd.Timestamp(session),
        "ticker": ticker,
        "roe_ttm": roe,
        "cash_conversion_ttm": cash_conversion,
        "debt_to_assets": debt_to_assets,
        "debt_to_assets_source": leverage_source,
        "net_income_ttm": net_income,
    }


def test_score_snapshot_selects_at_most_nine_with_deterministic_ticker_ties():
    snapshot = pd.DataFrame(
        [quality_row("2026-01-30", ticker) for ticker in reversed(["AAPL", "ADBE", "AMD", "AMGN", "AMZN", "AVGO", "BKNG", "COST", "CSCO", "GOOG", "META"])]
    )

    selected = score_snapshot(snapshot, variant="base", topk=9)

    assert selected["ticker"].tolist() == ["AAPL", "ADBE", "AMD", "AMGN", "AMZN", "AVGO", "BKNG", "COST", "CSCO"]
    assert selected["target_weight"].tolist() == [1.0 / 9] * 9


def test_score_snapshot_reported_only_excludes_derived_leverage():
    snapshot = pd.DataFrame(
        [
            quality_row("2026-01-30", "AAPL", leverage_source="reported"),
            quality_row("2026-01-30", "MSFT", leverage_source="derived_assets_minus_equity", roe=0.50),
        ]
    )

    selected = score_snapshot(snapshot, variant="reported_only")

    assert selected["ticker"].tolist() == ["AAPL"]


def test_monthly_targets_use_only_preceding_session_visible_quality():
    calendar = pd.to_datetime(["2026-01-30", "2026-02-02", "2026-02-03", "2026-03-02"]).tolist()
    quality = pd.DataFrame(
        [
            quality_row("2026-01-30", "AAPL"),
            quality_row("2026-02-02", "FUTURE", roe=0.99, cash_conversion=3.0, debt_to_assets=0.01),
            quality_row("2026-02-03", "AAPL"),
            quality_row("2026-02-03", "FUTURE", roe=0.99, cash_conversion=3.0, debt_to_assets=0.01),
        ]
    )

    targets = build_monthly_targets(quality, calendar, variant="base", topk=9)
    february = targets.loc[targets["rebalance_session"] == pd.Timestamp("2026-02-02")]
    march = targets.loc[targets["rebalance_session"] == pd.Timestamp("2026-03-02")]

    assert february["ticker"].tolist() == ["AAPL"]
    assert "FUTURE" not in february["ticker"].tolist()
    assert march["ticker"].tolist()[0] == "FUTURE"
    assert february["information_session"].unique().tolist() == [pd.Timestamp("2026-01-30")]
    assert march["information_session"].unique().tolist() == [pd.Timestamp("2026-02-03")]


def test_simulate_portfolio_preserves_drift_between_monthly_rebalances_and_charges_cost():
    sessions = pd.to_datetime(["2026-02-02", "2026-02-03", "2026-03-02", "2026-03-03"])
    prices = pd.DataFrame(
        {
            "AAPL": [100.0, 110.0, 110.0, 110.0],
            "MSFT": [100.0, 100.0, 100.0, 110.0],
        },
        index=sessions,
    )
    targets = pd.DataFrame(
        [
            {"rebalance_session": sessions[0], "ticker": "AAPL", "target_weight": 1.0},
            {"rebalance_session": sessions[2], "ticker": "MSFT", "target_weight": 1.0},
        ]
    )

    daily = simulate_portfolio(prices, targets, open_cost=0.0005, close_cost=0.0015)

    assert daily.loc[pd.Timestamp("2026-02-03"), "cost"] == pytest.approx(0.0005)
    assert daily.loc[pd.Timestamp("2026-02-03"), "net_return"] == pytest.approx(0.0995)
    assert daily.loc[pd.Timestamp("2026-03-02"), "cost"] == pytest.approx(0.0)
    assert daily.loc[pd.Timestamp("2026-03-03"), "cost"] > 0.0015
    assert daily["holding_count"].max() == 1


def test_build_stress_rows_emits_four_windows_for_each_benchmark():
    sessions = pd.bdate_range("2024-08-01", periods=400)
    daily = pd.DataFrame(
        {
            "net_return": [0.001 + (index % 5) * 0.0001 for index in range(len(sessions))],
            "turnover": [1.0] * len(sessions),
            "cost": [0.0] * len(sessions),
        },
        index=sessions,
    )
    benchmark_returns = {
        "SPY": pd.Series(0.0002, index=sessions),
        "QQQ": pd.Series(0.0003, index=sessions),
    }

    rows = build_stress_rows(daily, benchmark_returns, variant="base", full_start=sessions[100])

    assert [(row.benchmark, row.window) for row in rows] == [
        ("SPY", "full"),
        ("SPY", "63d"),
        ("SPY", "126d"),
        ("SPY", "252d"),
        ("QQQ", "full"),
        ("QQQ", "63d"),
        ("QQQ", "126d"),
        ("QQQ", "252d"),
    ]
    assert all(row.ann_excess_cost > 0 for row in rows)
    assert rows[0].turnover == 300.0
    assert rows[3].turnover == 252.0


def test_build_benchmark_returns_explicitly_matches_qlib_zero_gap_policy():
    prices = pd.DataFrame(
        {
            "SPY": [100.0, None, 110.0],
            "QQQ": [100.0, 101.0, 102.0],
        },
        index=pd.bdate_range("2026-05-18", periods=3),
    )

    returns = build_benchmark_returns(prices)

    assert returns["SPY"].tolist() == [0.0, 0.0, 0.0]
    assert returns["QQQ"].iloc[1] == pytest.approx(0.01)


def test_render_report_contains_sixteen_stress_rows_and_research_gate():
    rows = [
        StressRow(variant, benchmark, window, 0.01, -0.02, 0.20, 1.0, 0.001)
        for variant in ("base", "reported_only")
        for benchmark in ("SPY", "QQQ")
        for window in ("full", "63d", "126d", "252d")
    ]
    holdings = pd.DataFrame(
        [
            {
                "variant": "base",
                "ticker": "AAPL",
                "quality_score": 0.95,
                "roe_ttm": 0.22,
                "cash_conversion_ttm": 1.10,
                "debt_to_assets": 0.30,
                "debt_to_assets_source": "derived_assets_minus_equity",
                "target_weight": 1.0 / 9,
            }
        ]
    )
    checks = [PromotionCheck("holding cap", True, "maximum holdings: 9")]

    report = render_report(rows, holdings, "2026-05-22", 9, checks)

    assert "# Independent Quality Satellite Candidate Report" in report
    assert report.count("| base |") == 8
    assert report.count("| reported_only |") == 8
    assert "research-only; it is not approved for paper execution" in report
    assert "derived_assets_minus_equity" in report
    assert "## Promotion Gate" in report
    assert "promotion_gate: PASS" in report
    assert "benchmark_missing_policy: explicit Qlib-compatible zero benchmark return" in report


def test_quality_satellite_script_exposes_cli_help_and_make_target():
    result = subprocess.run(
        [sys.executable, "scripts/run_quality_satellite_candidate.py", "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert result.returncode == 0, result.stderr
    assert "quality" in result.stdout.lower()
    assert "quality-satellite:" in makefile
    assert "scripts/run_quality_satellite_candidate.py" in makefile


def test_read_lightgbm_reference_extracts_monitor_threshold_inputs(tmp_path: Path):
    report = tmp_path / "monitor.md"
    report.write_text(
        "| lightgbm_candidate_monitor_full_benchspy | FINISHED | id | 0 | 0 | 12.37% | -18.72% | 0 | 0 | cmd |\n"
        "| lightgbm_candidate_monitor_63d_benchqqq | FINISHED | id | 0 | 0 | -28.72% | -16.29% | 0 | 0 | cmd |\n",
        encoding="utf-8",
    )

    references = read_lightgbm_reference(report)

    assert references[("SPY", "full")] == pytest.approx((0.1237, -0.1872))
    assert references[("QQQ", "63d")] == pytest.approx((-0.2872, -0.1629))


def test_read_monitor_evaluation_session_aligns_quality_report_end_date(tmp_path: Path):
    report = tmp_path / "monitor.md"
    report.write_text("latest_provider_session: 2026-05-22\nlatest_evaluable_session: 2026-05-21\n", encoding="utf-8")

    assert read_monitor_evaluation_session(report) == "2026-05-21"


def test_assess_promotion_requires_reported_only_variant_to_pass_same_gate():
    references = {
        ("SPY", "full"): (0.1237, -0.1872),
        ("QQQ", "full"): (0.0545, -0.2627),
        ("QQQ", "63d"): (-0.2872, -0.1629),
        ("QQQ", "126d"): (0.1454, -0.1153),
    }
    rows = []
    for variant in ("base", "reported_only"):
        rows.extend(
            [
                StressRow(variant, "SPY", "full", 0.02, -0.20, 0.2, 1.0, 0.001),
                StressRow(variant, "QQQ", "full", 0.01, -0.25, 0.1, 1.0, 0.001),
                StressRow(variant, "QQQ", "63d", -0.18, -0.10, -0.5, 1.0, 0.001),
                StressRow(variant, "QQQ", "126d", 0.10, -0.10, 0.4, 1.0, 0.001),
            ]
        )
    rows[-2] = StressRow("reported_only", "QQQ", "63d", -0.20, -0.10, -0.5, 1.0, 0.001)

    checks = assess_promotion(rows, references, maximum_holding_count=9)

    assert any(check.rule == "base QQQ/63d improvement" and check.passed for check in checks)
    assert any(check.rule == "reported_only QQQ/63d improvement" and not check.passed for check in checks)

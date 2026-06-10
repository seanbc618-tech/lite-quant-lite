from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from scripts.run_quality_satellite_candidate import StressRow, simulate_portfolio
from scripts.run_quality_trend_defense_overlay import (
    OverlayCheck,
    apply_return_overlay,
    assess_overlay_gate,
    build_trend_states,
    evaluate_lightgbm_comparison,
    render_overlay_report,
    simulate_quality_overlay,
)


def test_trend_states_use_prior_session_prices_for_three_exposures():
    prices = pd.DataFrame(
        {"SPY": [10, 10, 10, 12, 8, 8], "QQQ": [10, 10, 10, 12, 12, 8]},
        index=pd.bdate_range("2026-01-02", periods=6),
        dtype=float,
    )

    states = build_trend_states(prices, lookback=3)

    assert states.loc[prices.index[3], "state"] == "risk_on"
    assert states.loc[prices.index[3], "exposure"] == 1.0
    assert states.loc[prices.index[4], "state"] == "risk_on"
    assert states.loc[prices.index[5], "state"] == "defensive"
    assert states.loc[prices.index[5], "exposure"] == 0.5


def test_trend_state_fails_closed_when_prior_signal_price_is_missing():
    prices = pd.DataFrame(
        {"SPY": [10, 10, 10, None, 12], "QQQ": [10, 10, 10, 12, 12]},
        index=pd.bdate_range("2026-01-02", periods=5),
        dtype=float,
    )

    states = build_trend_states(prices, lookback=3)

    assert states.loc[prices.index[4], "exposure"] == 0.0
    assert states.loc[prices.index[4], "failure_reason"] == "missing_prior_close:SPY"


def test_gentle_profile_reduces_normal_market_states_without_going_fully_to_cash():
    prices = pd.DataFrame(
        {"SPY": [10, 10, 10, 12, 8, 8, 8], "QQQ": [10, 10, 10, 12, 12, 8, 8]},
        index=pd.bdate_range("2026-01-02", periods=7),
        dtype=float,
    )

    states = build_trend_states(prices, lookback=3, profile="gentle")

    assert states.loc[prices.index[5], "state"] == "defensive"
    assert states.loc[prices.index[5], "exposure"] == 0.75
    assert states.loc[prices.index[6], "state"] == "cash"
    assert states.loc[prices.index[6], "exposure"] == 0.50


def test_gentle_profile_still_fails_closed_to_zero_exposure_for_missing_signal_price():
    prices = pd.DataFrame(
        {"SPY": [10, 10, 10, None, 12], "QQQ": [10, 10, 10, 12, 12]},
        index=pd.bdate_range("2026-01-02", periods=5),
        dtype=float,
    )

    states = build_trend_states(prices, lookback=3, profile="gentle")

    assert states.loc[prices.index[4], "exposure"] == 0.0
    assert states.loc[prices.index[4], "failure_reason"] == "missing_prior_close:SPY"


def test_trend_states_reject_unknown_exposure_profile():
    prices = pd.DataFrame(
        {"SPY": [10, 10, 10], "QQQ": [10, 10, 10]},
        index=pd.bdate_range("2026-01-02", periods=3),
        dtype=float,
    )

    with pytest.raises(ValueError, match="unknown trend exposure profile"):
        build_trend_states(prices, lookback=2, profile="unknown")


def test_quality_overlay_scales_holdings_and_charges_transition_once():
    sessions = pd.to_datetime(["2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05"])
    prices = pd.DataFrame({"AAPL": [100.0, 100.0, 100.0, 100.0]}, index=sessions)
    targets = pd.DataFrame(
        [{"rebalance_session": sessions[0], "ticker": "AAPL", "target_weight": 1.0}]
    )
    states = pd.DataFrame(
        {
            "state": ["risk_on", "defensive", "defensive", "cash"],
            "exposure": [1.0, 0.5, 0.5, 0.0],
            "failure_reason": [None] * 4,
        },
        index=sessions,
    )

    daily = simulate_quality_overlay(prices, targets, states, open_cost=0.0005, close_cost=0.0015)

    assert daily.loc[sessions[1], "cost"] == pytest.approx(0.0005)
    assert daily.loc[sessions[2], "cost"] == pytest.approx(0.0015 * (1 / 0.9995 - 0.5))
    assert daily.loc[sessions[3], "cost"] == pytest.approx(0.0)
    assert daily["holding_count"].max() == 1


def test_quality_overlay_combines_monthly_replacement_and_defensive_transition_into_one_trade():
    sessions = pd.to_datetime(["2026-02-02", "2026-02-03", "2026-03-02", "2026-03-03"])
    prices = pd.DataFrame(
        {"AAPL": [100.0] * 4, "MSFT": [100.0] * 4},
        index=sessions,
    )
    targets = pd.DataFrame(
        [
            {"rebalance_session": sessions[0], "ticker": "AAPL", "target_weight": 1.0},
            {"rebalance_session": sessions[2], "ticker": "MSFT", "target_weight": 1.0},
        ]
    )
    states = pd.DataFrame(
        {
            "state": ["risk_on", "risk_on", "defensive", "defensive"],
            "exposure": [1.0, 1.0, 0.5, 0.5],
            "failure_reason": [None] * 4,
        },
        index=sessions,
    )

    daily = simulate_quality_overlay(prices, targets, states, open_cost=0.0005, close_cost=0.0015)

    expected_cost = (1.0 / 0.9995) * 0.0015 + 0.5 * 0.0005
    assert daily.loc[sessions[3], "cost"] == pytest.approx(expected_cost)


def test_quality_overlay_matches_original_simulation_when_always_risk_on():
    sessions = pd.to_datetime(["2026-02-02", "2026-02-03", "2026-02-04"])
    prices = pd.DataFrame({"AAPL": [100.0, 110.0, 121.0]}, index=sessions)
    targets = pd.DataFrame(
        [{"rebalance_session": sessions[0], "ticker": "AAPL", "target_weight": 1.0}]
    )
    states = pd.DataFrame(
        {
            "state": ["risk_on"] * 3,
            "exposure": [1.0] * 3,
            "failure_reason": [None] * 3,
        },
        index=sessions,
    )

    original = simulate_portfolio(prices, targets, open_cost=0.0005, close_cost=0.0015)
    defended = simulate_quality_overlay(prices, targets, states, open_cost=0.0005, close_cost=0.0015)

    assert defended["net_return"].tolist() == pytest.approx(original["net_return"].tolist())
    assert defended["cost"].tolist() == pytest.approx(original["cost"].tolist())


def make_quality_rows(qqq_full: float, qqq_126: float, spy_full: float, qqq_dd: float, spy_dd: float) -> list[StressRow]:
    return [
        StressRow("reported_only", "SPY", "full", spy_full, spy_dd, 0.4, 1.0, 0.001),
        StressRow("reported_only", "QQQ", "full", qqq_full, qqq_dd, 0.4, 1.0, 0.001),
        StressRow("reported_only", "QQQ", "126d", qqq_126, qqq_dd, 0.4, 1.0, 0.001),
    ]


def test_overlay_gate_requires_absolute_drawdown_improvement_and_qqq_retention():
    original = make_quality_rows(qqq_full=0.11, qqq_126=0.22, spy_full=0.18, qqq_dd=-0.09, spy_dd=-0.09)
    defended = make_quality_rows(qqq_full=0.08, qqq_126=0.19, spy_full=0.12, qqq_dd=-0.08, spy_dd=-0.08)

    checks = assess_overlay_gate("PASS", original, defended, -0.16, -0.11, 9, 0)

    assert all(check.passed for check in checks)


@pytest.mark.parametrize(
    ("underlying_gate", "defended_dd", "defended_qqq_126", "failed_rule"),
    [
        ("PASS", -0.145, 0.19, "absolute full-period drawdown improvement"),
        ("PASS", -0.11, 0.15, "QQQ/126d excess retention"),
        ("FAIL", -0.11, 0.19, "underlying quality promotion gate"),
    ],
)
def test_overlay_gate_rejects_failed_underlying_or_lost_defensive_value(
    underlying_gate: str,
    defended_dd: float,
    defended_qqq_126: float,
    failed_rule: str,
):
    original = make_quality_rows(qqq_full=0.11, qqq_126=0.22, spy_full=0.18, qqq_dd=-0.09, spy_dd=-0.09)
    defended = make_quality_rows(qqq_full=0.08, qqq_126=defended_qqq_126, spy_full=0.12, qqq_dd=-0.08, spy_dd=-0.08)

    checks = assess_overlay_gate(underlying_gate, original, defended, -0.16, defended_dd, 9, 0)

    assert any(check.rule == failed_rule and not check.passed for check in checks)


def test_overlay_report_labels_gate_states_and_lightgbm_as_comparison_only():
    rows = make_quality_rows(qqq_full=0.08, qqq_126=0.19, spy_full=0.12, qqq_dd=-0.08, spy_dd=-0.08)
    states = pd.DataFrame(
        {
            "state": ["risk_on", "defensive", "cash"],
            "exposure": [1.0, 0.5, 0.0],
            "failure_reason": [None, None, None],
        },
        index=pd.bdate_range("2026-01-02", periods=3),
    )

    report = render_overlay_report(
        original_rows=rows,
        defended_rows=rows,
        lightgbm_original_rows=rows,
        lightgbm_defended_rows=rows,
        states=states,
        checks=[OverlayCheck("test", True, "pass")],
        underlying_gate="PASS",
        latest_provider_session="2026-05-22",
        evaluation_session="2026-05-21",
        quality_absolute=(0.1, -0.16, 0.08, -0.11),
        profile="gentle",
    )

    assert "overlay_gate: PASS" in report
    assert "exposure_profile: gentle" in report
    assert "trend_rule: SPY,QQQ SMA(200) -> 100%/75%/50%" in report
    assert "research_comparison_only" in report
    assert "underlying_quality_gate: PASS" in report
    assert "## Market States" in report
    assert "## Reported Only Comparison" in report
    assert "## LightGBM Comparison" in report


def test_lightgbm_overlay_does_not_double_charge_initial_scaled_entry_cost():
    net = pd.Series([0.10, -0.04], index=pd.to_datetime(["2026-02-03", "2026-02-04"]))
    exposure = pd.Series([0.5, 0.0], index=net.index)

    defended = apply_return_overlay(net, exposure, open_cost=0.0005, close_cost=0.0015)

    assert defended.iloc[0] == pytest.approx(0.10 * 0.5)
    assert defended.iloc[1] == pytest.approx(-0.0015 * 0.5)


def test_lightgbm_comparison_uses_each_scenario_artifact_instead_of_tail_of_full():
    sessions = pd.bdate_range("2026-02-02", periods=4)
    states = pd.DataFrame(
        {
            "state": ["risk_on"] * 4,
            "exposure": [1.0] * 4,
            "failure_reason": [None] * 4,
        },
        index=sessions,
    )
    scenarios = {
        ("SPY", "full"): pd.DataFrame(
            {"return": [0.010, 0.012, 0.009], "cost": [0.0] * 3, "bench": [0.0] * 3, "turnover": [0.0] * 3},
            index=sessions[1:],
        ),
        ("QQQ", "63d"): pd.DataFrame(
            {"return": [0.040, 0.041, 0.039], "cost": [0.0] * 3, "bench": [0.0] * 3, "turnover": [0.0] * 3},
            index=sessions[1:],
        ),
    }

    original, defended = evaluate_lightgbm_comparison(scenarios, states)
    lookup = {(row.benchmark, row.window): row for row in original}

    assert lookup[("QQQ", "63d")].ann_excess_cost > lookup[("SPY", "full")].ann_excess_cost
    assert len(defended) == 2


def test_trend_defense_script_exposes_cli_help():
    result = subprocess.run(
        [sys.executable, "scripts/run_quality_trend_defense_overlay.py", "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "trend" in result.stdout.lower()
    assert "--profile" in result.stdout
    assert "Gym has been unmaintained" not in result.stderr

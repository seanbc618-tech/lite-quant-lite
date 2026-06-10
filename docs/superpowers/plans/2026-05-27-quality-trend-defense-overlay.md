# Quality Trend Defense Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a research-only `SPY`/`QQQ` long-term trend defense overlay for the passing `reported_only` quality candidate, plus a non-executable LightGBM comparison, and determine whether the overlay improves drawdown without sacrificing required excess return.

**Architecture:** Create one standalone research runner alongside the existing quality candidate rather than modifying its selected holdings or current paper preview. The runner builds lagged ETF trend states, applies exact exposure-and-cash transitions to quality holdings with one transaction-cost calculation per trade date, applies an explicitly approximate return-level overlay to LightGBM only for comparison, and writes an auditable gate report. Add a Make entry point for the research run only; do not add a paper-dry output until observed results pass the approved gate.

**Tech Stack:** Python 3.11, pandas, Qlib `risk_analysis`, MLflow report artifacts already emitted by the Qlib workflows, pytest, Make.

---

### Task 1: Lagged Trend States And Exact Quality Overlay Engine

**Files:**
- Create: `scripts/run_quality_trend_defense_overlay.py`
- Create: `tests/test_run_quality_trend_defense_overlay.py`

- [ ] **Step 1: Write failing tests for the delayed three-state ETF signal**

```python
from scripts.run_quality_trend_defense_overlay import build_trend_states


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
```

```python
def test_trend_state_fails_closed_when_prior_signal_price_is_missing():
    prices = pd.DataFrame(
        {"SPY": [10, 10, 10, None, 12], "QQQ": [10, 10, 10, 12, 12]},
        index=pd.bdate_range("2026-01-02", periods=5),
        dtype=float,
    )

    states = build_trend_states(prices, lookback=3)

    assert states.loc[prices.index[4], "exposure"] == 0.0
    assert states.loc[prices.index[4], "failure_reason"] == "missing_prior_close:SPY"
```

- [ ] **Step 2: Run the focused tests to establish RED**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py
```

Expected: FAIL during import because `scripts.run_quality_trend_defense_overlay` does not yet exist.

- [ ] **Step 3: Implement the lagged trend state function**

Create these public definitions in `scripts/run_quality_trend_defense_overlay.py`:

```python
TREND_SYMBOLS = ("SPY", "QQQ")
DEFAULT_LOOKBACK = 200


def build_trend_states(prices: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK) -> pd.DataFrame:
    """Return exposure effective on session t using closes visible through t-1."""
    rows = []
    for index, effective_session in enumerate(prices.index):
        prior = prices.index[index - 1] if index else None
        failure_reason = None
        passes = 0
        if prior is None:
            failure_reason = "no_prior_session"
        else:
            for symbol in TREND_SYMBOLS:
                prior_close = prices.at[prior, symbol]
                history = prices.loc[:prior, symbol].dropna().tail(lookback)
                if pd.isna(prior_close):
                    failure_reason = f"missing_prior_close:{symbol}"
                    break
                if len(history) < lookback:
                    failure_reason = f"insufficient_history:{symbol}"
                    break
                passes += int(prior_close >= history.mean())
        exposure = 0.0 if failure_reason else passes / len(TREND_SYMBOLS)
        state = {1.0: "risk_on", 0.5: "defensive", 0.0: "cash"}[exposure]
        rows.append({"session": effective_session, "state": state, "exposure": exposure, "failure_reason": failure_reason})
    return pd.DataFrame(rows).set_index("session")
```

- [ ] **Step 4: Add failing tests for exact quality trades and unified transaction cost**

```python
from scripts.run_quality_trend_defense_overlay import simulate_quality_overlay


def test_quality_overlay_scales_holdings_and_charges_one_trade_when_state_changes():
    sessions = pd.to_datetime(["2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05"])
    prices = pd.DataFrame({"AAPL": [100.0, 100.0, 100.0, 100.0]}, index=sessions)
    targets = pd.DataFrame(
        [{"rebalance_session": sessions[0], "ticker": "AAPL", "target_weight": 1.0}]
    )
    states = pd.DataFrame(
        {"state": ["risk_on", "defensive", "defensive", "cash"], "exposure": [1.0, 0.5, 0.5, 0.0]},
        index=sessions,
    )

    daily = simulate_quality_overlay(prices, targets, states, open_cost=0.0005, close_cost=0.0015)

    assert daily.loc[sessions[1], "cost"] == pytest.approx(0.0005)
    assert daily.loc[sessions[2], "cost"] == pytest.approx(0.0015 * 0.5)
    assert daily.loc[sessions[3], "cost"] == pytest.approx(0.0)
    assert daily["holding_count"].max() == 1
```

```python
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
        {"state": ["risk_on", "risk_on", "defensive", "defensive"], "exposure": [1.0, 1.0, 0.5, 0.5]},
        index=sessions,
    )

    daily = simulate_quality_overlay(prices, targets, states, open_cost=0.0005, close_cost=0.0015)

    expected_cost = 1.0 * 0.0015 + 0.5 * 0.0005
    assert daily.loc[sessions[3], "cost"] == pytest.approx(expected_cost)
```

- [ ] **Step 5: Implement exact quality exposure simulation and verify GREEN**

Implement:

```python
def simulate_quality_overlay(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    states: pd.DataFrame,
    open_cost: float = 0.0005,
    close_cost: float = 0.0015,
) -> pd.DataFrame:
    """Trade actual holdings to monthly targets scaled by lagged market exposure."""
```

The function maintains `base_target`, actual drifted `holdings`, cash, and
the last applied exposure. On a target date it sets `base_target`; on a
target date or exposure transition it computes one `desired` stock-weight
series and charges buys/sells once. Each return row must retain `state`,
`exposure`, `failure_reason`, `cost`, `turnover`, and `holding_count`.

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py
```

Expected: PASS for the signal and simulation tests.

### Task 2: Quality Overlay Metrics, Gate, And Auditable Report

**Files:**
- Modify: `scripts/run_quality_trend_defense_overlay.py`
- Modify: `tests/test_run_quality_trend_defense_overlay.py`

- [ ] **Step 1: Write failing tests for absolute drawdown and overlay gate**

```python
from scripts.run_quality_trend_defense_overlay import (
    assess_overlay_gate,
    summarize_absolute_returns,
)


def make_quality_rows(qqq_full, qqq_126, spy_full, qqq_dd, spy_dd):
    return [
        StressRow("reported_only", "SPY", "full", spy_full, spy_dd, 0.4, 1.0, 0.001),
        StressRow("reported_only", "QQQ", "full", qqq_full, qqq_dd, 0.4, 1.0, 0.001),
        StressRow("reported_only", "QQQ", "126d", qqq_126, qqq_dd, 0.4, 1.0, 0.001),
    ]


def test_overlay_gate_requires_absolute_drawdown_improvement_and_qqq_retention():
    original = make_quality_rows(qqq_full=0.11, qqq_126=0.22, spy_full=0.18, qqq_dd=-0.09, spy_dd=-0.09)
    defended = make_quality_rows(qqq_full=0.08, qqq_126=0.19, spy_full=0.12, qqq_dd=-0.08, spy_dd=-0.08)

    checks = assess_overlay_gate(
        underlying_gate="PASS",
        original_rows=original,
        defended_rows=defended,
        original_absolute_max_drawdown=-0.16,
        defended_absolute_max_drawdown=-0.11,
        maximum_holding_count=9,
        hidden_failure_count=0,
    )

    assert all(check.passed for check in checks)
```

```python
@pytest.mark.parametrize(
    ("underlying_gate", "defended_dd", "defended_qqq_126", "failed_rule"),
    [
        ("PASS", -0.145, 0.19, "absolute full-period drawdown improvement"),
        ("PASS", -0.11, 0.15, "QQQ/126d excess retention"),
        ("FAIL", -0.11, 0.19, "underlying quality promotion gate"),
    ],
)
def test_overlay_gate_rejects_failed_underlying_or_lost_defensive_value(
    underlying_gate, defended_dd, defended_qqq_126, failed_rule
):
    original = make_quality_rows(qqq_full=0.11, qqq_126=0.22, spy_full=0.18, qqq_dd=-0.09, spy_dd=-0.09)
    defended = make_quality_rows(qqq_full=0.08, qqq_126=defended_qqq_126, spy_full=0.12, qqq_dd=-0.08, spy_dd=-0.08)

    checks = assess_overlay_gate(
        underlying_gate, original, defended, -0.16, defended_dd, 9, 0
    )

    assert any(check.rule == failed_rule and not check.passed for check in checks)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py
```

Expected: FAIL because the report and gate functions are not yet defined.

- [ ] **Step 3: Implement metric and gate functions**

Define:

```python
@dataclass(frozen=True)
class OverlayCheck:
    rule: str
    passed: bool
    detail: str


def summarize_absolute_returns(daily: pd.DataFrame, full_start: str) -> tuple[float, float]:
    """Return after-cost annualized strategy return and its own maximum drawdown."""


def assess_overlay_gate(
    underlying_gate: str,
    original_rows: list[StressRow],
    defended_rows: list[StressRow],
    original_absolute_max_drawdown: float,
    defended_absolute_max_drawdown: float,
    maximum_holding_count: int,
    hidden_failure_count: int,
) -> list[OverlayCheck]:
    """Apply approved promotion rules to the protected reported_only candidate."""
```

Use the approved thresholds exactly: quality monitor must pass; nine holdings
maximum; full absolute drawdown improvement `>= 0.02`; defended SPY/full and
QQQ/full excess positive; QQQ/full and QQQ/126d loss relative to original no
greater than `0.05`; full relative drawdowns not deeper by more than `0.02`;
hidden failure count must be zero.

- [ ] **Step 4: Write report-rendering tests and implementation**

```python
from scripts.run_quality_trend_defense_overlay import OverlayCheck, render_overlay_report


def test_overlay_report_labels_gate_states_and_lightgbm_as_comparison_only():
    rows = make_quality_rows(qqq_full=0.08, qqq_126=0.19, spy_full=0.12, qqq_dd=-0.08, spy_dd=-0.08)
    states = pd.DataFrame(
        {"state": ["risk_on", "defensive", "cash"], "exposure": [1.0, 0.5, 0.0], "failure_reason": [None, None, None]},
        index=pd.bdate_range("2026-01-02", periods=3),
    )
    report = render_overlay_report(
        original_rows=rows,
        defended_rows=rows,
        lightgbm_rows=rows,
        states=states,
        checks=[OverlayCheck("test", True, "pass")],
        underlying_gate="PASS",
        latest_provider_session="2026-05-22",
        evaluation_session="2026-05-21",
    )

    assert "overlay_gate: PASS" in report
    assert "trend_rule: SPY,QQQ SMA(200) -> 100%/50%/0%" in report
    assert "research_comparison_only" in report
    assert "underlying_quality_gate: PASS" in report
    assert "## Market States" in report
    assert "## Reported Only Comparison" in report
    assert "## LightGBM Comparison" in report
```

Implement `render_overlay_report(...)` and write states to
`.cache/quality_trend_defense/daily_states.parquet`. Include failed-close
reasons in the report so the fail-closed policy is inspectable.

- [ ] **Step 5: Run focused tests to verify GREEN**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py tests/test_run_quality_satellite_candidate.py
```

Expected: PASS.

### Task 3: LightGBM Research Comparator And Command Entry Point

**Files:**
- Modify: `scripts/run_quality_trend_defense_overlay.py`
- Modify: `tests/test_run_quality_trend_defense_overlay.py`
- Modify: `tests/test_modern_strategy_workflows.py`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Write failing tests for the comparison-only model and Make target**

```python
from scripts.run_quality_trend_defense_overlay import apply_return_overlay


def test_lightgbm_overlay_scales_net_return_and_marks_transition_cost_only_for_research():
    net = pd.Series([0.10, -0.04], index=pd.to_datetime(["2026-02-03", "2026-02-04"]))
    exposure = pd.Series([0.5, 0.0], index=net.index)

    defended = apply_return_overlay(net, exposure, open_cost=0.0005, close_cost=0.0015)

    assert defended.iloc[0] == pytest.approx(0.10 * 0.5 - 0.0005 * 0.5)
    assert defended.iloc[1] == pytest.approx(-0.0015 * 0.5)
```

Extend `tests/test_modern_strategy_workflows.py`:

```python
assert "quality-trend-defense:" in makefile
assert "$(MAKE) monitor-quality-satellite" in makefile
assert "scripts/run_quality_trend_defense_overlay.py" in makefile
assert "paper-dry-quality-trend-defense" not in makefile
```

- [ ] **Step 2: Verify RED**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py tests/test_modern_strategy_workflows.py
```

Expected: FAIL because `apply_return_overlay()` and `quality-trend-defense`
are not present.

- [ ] **Step 3: Implement research-only LightGBM comparison**

Add:

```python
def apply_return_overlay(
    original_net_returns: pd.Series,
    exposures: pd.Series,
    open_cost: float = 0.0005,
    close_cost: float = 0.0015,
) -> pd.Series:
    """Apply exposure transitions at return-series level for research comparison only."""
```

Read the latest full-window LightGBM daily artifact through the existing
`find_latest_report_artifact()` helper using:

```python
def load_lightgbm_daily(mlruns_dir: Path, experiment_base: str) -> pd.DataFrame:
    experiment = f"{experiment_base}full_benchspy"
    artifact = find_latest_report_artifact(mlruns_dir, experiment)
    report = pd.read_pickle(artifact).copy()
    report["net_return"] = report["return"] - report["cost"]
    return report
```

Calculate original and defended stress rows using the same four windows and
both benchmarks. Report explicitly that LightGBM overlay transition costs are
a return-level comparison model, not a trade-preview model.

- [ ] **Step 4: Add the research command and usage documentation**

In `Makefile`, expose only:

```make
quality-trend-defense:
	$(MAKE) monitor-quality-satellite
	$(PYTHONPATH) $(PY) scripts/run_quality_trend_defense_overlay.py --provider-uri $(MODERN_PROVIDER) $(ARGS)
```

In `README.md`, document that this command runs an isolated trend-defense
study for `reported_only`, includes LightGBM comparison only, and creates no
paper preview.

- [ ] **Step 5: Run focused tests and CLI help**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py tests/test_modern_strategy_workflows.py
PYTHONPATH=src .venv/bin/python scripts/run_quality_trend_defense_overlay.py --help
```

Expected: tests PASS and help text returns exit status `0`.

### Task 4: Real Research Run And Decision Evidence

**Files:**
- Modify only if evidence is recorded after the run: `docs/superpowers/plans/2026-05-27-quality-trend-defense-overlay.md`

- [ ] **Step 1: Run the real protected-candidate research report**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache make quality-trend-defense
```

Inspect:

```text
.cache/reports/quality_trend_defense_latest.md
.cache/quality_trend_defense/daily_states.parquet
```

Record the overlay gate, original versus defended absolute drawdown, QQQ
full/126d excess comparison, state counts, state transition count, and whether
the LightGBM comparison was informative.

- [ ] **Step 2: Run complete verification**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m compileall -q scripts src
git diff --check
git status --short --branch
```

Expected: all tests PASS; compilation and diff formatting checks return zero;
all local modifications are limited to this uncommitted strategy experiment
and its documentation.

- [ ] **Step 3: Decide whether to retain the experiment**

If `overlay_gate: PASS`, present the evidence and propose a separate
paper-dry design step. If `overlay_gate: FAIL`, retain it only as a documented
research result or discard it after user review; do not generate a new paper
preview in either case during this implementation.

## Execution Record

This implementation remains uncommitted at the operator's request while the
strategy is evaluated.

- Baseline before edits: `107 passed, 1 warning` from the complete pytest run.
- TDD RED: the initial focused suite failed because
  `scripts.run_quality_trend_defense_overlay` did not exist; later regression
  tests also caught the CLI import path and the need for cost-consistent
  risk-on equivalence with the original quality simulator.
- TDD GREEN: focused overlay, quality-regression, and Make-surface tests pass
  after implementing lagged states, exact quality exposure transitions,
  research-only LightGBM comparison, and the `quality-trend-defense` target.
- Real run: `MPLCONFIGDIR=/private/tmp/mplcache make quality-trend-defense`
  rebuilt the contemporaneous LightGBM and quality reports; underlying
  `reported_only` remained `PASS`, while the new overlay returned
  `overlay_gate: FAIL`.

### Observed Quality Result

| metric | original `reported_only` | defended | decision |
| --- | ---: | ---: | --- |
| absolute full annualized return | 36.36% | 27.19% | lower return |
| absolute full maximum drawdown | -27.78% | -12.58% | strong protection |
| QQQ/full annualized excess | 11.09% | 1.92% | fails 5-point retention gate |
| QQQ/126d annualized excess | 22.85% | 15.93% | fails 5-point retention gate |
| SPY/full excess drawdown | -9.38% | -19.81% | fails drawdown tolerance |
| QQQ/full excess drawdown | -9.07% | -27.34% | fails drawdown tolerance |

The overlay was in `risk_on` for `287` assessment sessions, `defensive` for
`5`, and `cash` for `55`, with average cash exposure of `16.57%`. It recorded
one explicit fail-closed session on `2026-04-21` because the prior `SPY` close
was unavailable. The simple `SMA(200)` three-state overlay therefore protects
absolute capital in this sample but is too blunt to preserve the quality
strategy's benchmark-relative strength, so it must not enter paper-dry
observation.

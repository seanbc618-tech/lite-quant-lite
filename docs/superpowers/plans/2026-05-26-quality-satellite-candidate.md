# Independent Quality Satellite Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a deterministic monthly quality satellite candidate from point-in-time SEC TTM metrics without wiring it into paper execution.

**Architecture:** Add one standalone runner that reads the existing daily quality Parquet, forms monthly top-nine portfolios from preceding-session visible facts, loads close prices from the modern Qlib provider, and calculates drift-aware after-cost daily returns. The runner emits a local Markdown stress report for base and reported-only leverage variants against SPY and QQQ, while existing LightGBM workflows and paper targets remain unchanged.

**Tech Stack:** Python 3.11, pandas, numpy, Qlib data provider and `risk_analysis`, pytest, Make.

---

### Task 1: Point-In-Time Monthly Selection

**Files:**
- Create: `scripts/run_quality_satellite_candidate.py`
- Create: `tests/test_run_quality_satellite_candidate.py`

- [x] **Step 1: Write failing tests for preceding-session selection and scoring**

Add tests that construct two daily quality snapshots, place a high-scoring
filing only on a rebalance date, and assert it cannot be selected until the
following monthly rebalance. Add eleven eligible rows with tied quality
values and assert that selection holds no more than nine stocks, sorted
deterministically by score then ticker.

```python
targets = build_monthly_targets(quality, calendar, variant="base", topk=9)
december = targets.loc[targets["rebalance_session"] == pd.Timestamp("2026-12-01")]
assert "FUTURE" not in december["ticker"].tolist()
assert december["ticker"].tolist()[:2] == ["AAPL", "ADBE"]
assert december["ticker"].nunique() == 9
```

- [x] **Step 2: Run tests and verify red**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_satellite_candidate.py
```

Expected: FAIL because the quality-candidate runner does not yet exist.

- [x] **Step 3: Implement eligible scoring and monthly targets**

Create focused functions:

```python
def score_snapshot(snapshot: pd.DataFrame, variant: str, topk: int = 9) -> pd.DataFrame:
    """Return scored top-k eligible rows for one information session."""

def build_monthly_targets(
    quality: pd.DataFrame, calendar: list[pd.Timestamp], variant: str, topk: int = 9
) -> pd.DataFrame:
    """Use the preceding session snapshot to form first-session monthly targets."""
```

Filter on complete TTM fields and positive `net_income_ttm`, exclude derived
leverage for `reported_only`, winsorize three inputs at `0.05/0.95`, compute
equal-weight percentile ranks, and select stable top-nine holdings using the
prior trading session's quality rows.

- [x] **Step 4: Verify green**

Re-run the focused tests and confirm that the PIT and holding-cap tests pass.

### Task 2: Drift-Aware Return Engine And Windows

**Files:**
- Modify: `scripts/run_quality_satellite_candidate.py`
- Modify: `tests/test_run_quality_satellite_candidate.py`

- [x] **Step 1: Write failing tests for monthly persistence and transaction costs**

Use a small price frame with one rebalance and one later switch. Assert no
target reset occurs between monthly dates, buy and sell turnover are charged
at `0.0005` and `0.0015`, and daily net returns preserve drifted holdings.

```python
daily = simulate_portfolio(prices, targets, open_cost=0.0005, close_cost=0.0015)
assert daily.loc[pd.Timestamp("2026-02-03"), "cost"] == pytest.approx(0.0005)
assert daily.loc[pd.Timestamp("2026-03-03"), "cost"] > 0
assert daily["holding_count"].max() <= 9
```

- [x] **Step 2: Run tests and verify red**

Run the focused suite; expected failure is missing `simulate_portfolio`.

- [x] **Step 3: Implement the return engine and risk rows**

Add:

```python
@dataclass(frozen=True)
class StressRow:
    variant: str
    benchmark: str
    window: str
    ann_excess_cost: float
    max_drawdown_cost: float
    ir_cost: float
    turnover: float
    transaction_cost: float

def simulate_portfolio(
    prices: pd.DataFrame, targets: pd.DataFrame, open_cost: float, close_cost: float
) -> pd.DataFrame:
    """Apply targets at formation close and preserve drifted holdings thereafter."""

def build_stress_rows(
    daily: pd.DataFrame,
    benchmark_returns: dict[str, pd.Series],
    variant: str,
    windows: tuple[str, ...] = ("full", "63d", "126d", "252d"),
) -> list[StressRow]:
    """Measure each benchmark/window from after-cost strategy returns."""
```

Trades take effect at rebalance-session close and earn only the next
close-to-close return. Maintain drifted stock and cash weights between
rebalances; compute after-cost excess risk with Qlib `risk_analysis`.

- [x] **Step 4: Verify green**

Run the focused suite after implementing return and window metrics.

### Task 3: Provider Loader, Report, And Command Surface

**Files:**
- Modify: `scripts/run_quality_satellite_candidate.py`
- Modify: `tests/test_run_quality_satellite_candidate.py`
- Modify: `Makefile`
- Modify: `README.md`

- [x] **Step 1: Write failing report and CLI tests**

Assert the report contains sixteen stress rows, research-only wording,
latest-holdings provenance, and a promotion-gate section. Assert the CLI
responds to `--help`, and assert the Makefile exposes:

```make
quality-satellite:
	$(PYTHONPATH) $(PY) scripts/run_quality_satellite_candidate.py $(ARGS)
```

- [x] **Step 2: Verify red**

Run focused tests and confirm report/command-surface assertions fail before
implementation.

- [x] **Step 3: Implement data loading, report rendering, and CLI**

The CLI defaults are:

```python
DEFAULT_QUALITY = Path(".cache/fundamentals/quality_daily.parquet")
DEFAULT_PROVIDER = Path.home() / ".qlib" / "qlib_data" / "us_modern_liquid100"
DEFAULT_REPORT = Path(".cache/reports/quality_satellite_candidate_latest.md")
DEFAULT_HOLDINGS = Path(".cache/quality_satellite/latest_holdings.parquet")
DEFAULT_LIGHTGBM_REPORT = Path(".cache/reports/modern_low_monitor_latest.md")
DEFAULT_FULL_START = "2025-01-02"
```

Load close prices for investable symbols plus benchmarks through Qlib,
calculate both leverage variants, write latest auditable holdings locally,
render all variant/benchmark/window rows, and evaluate the frozen promotion
thresholds against the available LightGBM monitor snapshot. Align the `full`
window with the LightGBM monitor at `2025-01-02`, while allowing earlier
portfolios only to establish holdings entering that evaluation interval.
End comparison windows on the monitor's `latest_evaluable_session` and
explicitly disclose Qlib-compatible zero benchmark returns for missing
benchmark closes. Document `make quality-satellite` as research-only.

- [x] **Step 4: Verify green**

Run the focused tests and confirm the new command behavior passes.

### Task 4: Real Stress Experiment And Publication

**Files:**
- Modify: `docs/superpowers/plans/2026-05-26-quality-satellite-candidate.md`

- [x] **Step 1: Run the real quality experiment**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache make quality-satellite
```

Inspect `.cache/reports/quality_satellite_candidate_latest.md`, record the
sixteen row outcome, latest holdings/provenance, holding-count compliance,
and whether both variants satisfy the promotion gate.

Observed comparable experiment result (`2025-01-02` through `2026-05-21`,
with the `2026-04-20` missing SPY close explicitly evaluated under Qlib's
zero-benchmark-return convention):

```text
base          SPY/full  +7.42% excess, -21.21% max drawdown
base          QQQ/full  +0.51% excess, -24.64% max drawdown
base          QQQ/63d  +26.00% excess,  -4.57% max drawdown
base          QQQ/126d +25.18% excess,  -8.05% max drawdown
reported_only SPY/full +18.00% excess,  -9.38% max drawdown
reported_only QQQ/full +11.09% excess,  -9.07% max drawdown
reported_only QQQ/63d  +17.62% excess,  -5.15% max drawdown
reported_only QQQ/126d +22.85% excess,  -9.07% max drawdown
maximum holdings: 9
promotion gate: PASS for both variants
```

The `reported_only` variant is the preferred next monitoring candidate
because it passes without reliance on derived leverage and has materially
stronger full-window drawdown behavior. This milestone intentionally does not
wire either variant into paper execution.

- [x] **Step 2: Run final verification**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m compileall -q src scripts tests
git diff --check
```

Observed:

```text
focused quality tests: 11 passed
full suite: 102 passed, 1 existing third-party websockets deprecation warning
compileall: passed
git diff --check: passed
real quality run: completed; Promotion gate: PASS
runtime advisory: Qlib dependency reports its legacy Gym package
```

- [x] **Step 3: Commit and push the research result**

Commit implementation, tests, command/documentation, and this validation
record; leave `.cache/` results ignored. Push the verified commits on `main`
to `origin/main`.

Published to `origin/main`:

```text
0e57d9f docs: design independent quality satellite candidate
77cdc0c feat: add independent quality satellite candidate
```

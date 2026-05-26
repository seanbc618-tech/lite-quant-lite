# Quality Satellite Observation Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated monitoring and paper-dry observation loop for the promoted `reported_only` quality satellite without changing executable candidate outputs.

**Architecture:** Reuse `scripts/run_quality_satellite_candidate.py` as the quality calculation engine and make its report expose an explicit promotion status. Add one dedicated preview exporter that accepts only the `reported_only` audited holdings after a passing monitor report, emits a `.cache` `dry_run_only` JSON payload, and relies on the existing `trade_v2.py --dry-run` guard. The Make entry point refreshes the existing LightGBM monitor first so quality promotion remains contemporaneous with its comparison baseline.

**Tech Stack:** Python 3.11, pandas, pytest, Qlib-backed existing runners, Make, Markdown documentation.

---

### Task 1: Explicit Monitor Status And Command Boundary

**Files:**
- Modify: `scripts/run_quality_satellite_candidate.py`
- Modify: `tests/test_run_quality_satellite_candidate.py`
- Modify: `Makefile`
- Modify: `tests/test_modern_strategy_workflows.py`

- [x] **Step 1: Write failing monitor-output and Make-boundary tests**

Extend the report test to require a machine-readable status:

```python
assert "promotion_gate: PASS" in report
```

Extend the Make command-surface test to require an isolated quality monitor
that refreshes its same-date comparison baseline and writes a dedicated
monitor report:

```python
assert "monitor-quality-satellite:" in makefile
assert "$(MAKE) monitor-modern-low" in makefile
assert "--report .cache/reports/quality_satellite_monitor_latest.md" in makefile
```

- [x] **Step 2: Run tests to verify red**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_satellite_candidate.py tests/test_modern_strategy_workflows.py
```

Expected: FAIL because the quality report lacks `promotion_gate:` and the
monitor command does not exist.

Observed: two expected failures, for the missing `promotion_gate: PASS` line
and the missing `monitor-quality-satellite` target; the remaining focused
assertions passed.

- [x] **Step 3: Implement explicit status and the isolated monitor target**

In `render_report()`, emit the aggregate status derived from the existing
promotion checks:

```python
promotion_status = "PASS" if all(check.passed for check in checks) else "FAIL"
lines = [
    "# Independent Quality Satellite Candidate Report",
    "",
    f"promotion_gate: {promotion_status}",
    ...
]
```

In `Makefile`, add:

```make
monitor-quality-satellite:
	$(MAKE) monitor-modern-low
	$(PYTHONPATH) $(PY) scripts/run_quality_satellite_candidate.py --provider-uri $(MODERN_PROVIDER) --report .cache/reports/quality_satellite_monitor_latest.md $(ARGS)
```

This target deliberately refreshes the current LightGBM reference report
before applying quality promotion gates.

- [x] **Step 4: Re-run tests to verify green**

Run the focused suite from Step 2 and confirm it passes.

Observed: `20 passed`.

### Task 2: Reported-Only Dry-Run Preview Exporter

**Files:**
- Create: `scripts/generate_quality_paper_signals.py`
- Create: `tests/test_generate_quality_paper_signals.py`

- [x] **Step 1: Write failing exporter tests**

Create tests covering:

```python
payload = build_preview_payload(
    holdings,
    Path("holdings.parquet"),
    Path("monitor.md"),
    budget=900.0,
)
assert payload["dry_run_only"] is True
assert payload["strategy"] == "quality_reported_only_candidate"
assert payload["orders"] == [{"symbol": "AAPL", "side": "buy", "notional": 450.0}, ...]
```

Also require failure when:

```python
read_promotion_status(failing_report) != "PASS"
build_preview_payload(derived_holding, ..., budget=900.0)  # raises ValueError
build_preview_payload(ten_holdings, ..., budget=900.0)      # raises ValueError
```

Assert the CLI starts with `--help`.

- [x] **Step 2: Run tests to verify red**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_generate_quality_paper_signals.py
```

Expected: FAIL because `scripts.generate_quality_paper_signals` does not yet
exist.

Observed: test collection failed with
`ModuleNotFoundError: No module named 'scripts.generate_quality_paper_signals'`.

- [x] **Step 3: Implement a fail-closed preview exporter**

Create a script with these public functions:

```python
def read_promotion_status(report: Path) -> str:
    """Return explicit PASS or FAIL from a quality monitor report."""

def build_preview_payload(
    holdings: pd.DataFrame,
    source_holdings: Path,
    source_report: Path,
    budget: float,
    max_holdings: int = 9,
) -> dict[str, Any]:
    """Export only the latest reported_only target as dry-run observation orders."""
```

Implementation rules:

- Select only `variant == "reported_only"` from the latest
  `rebalance_session`.
- Reject empty holdings, duplicate tickers, non-positive weights, more than
  nine holdings, or any `debt_to_assets_source != "reported"`.
- Normalize positive `target_weight` values to the requested preview budget.
- Emit `strategy: "quality_reported_only_candidate"` and
  `dry_run_only: true`.
- In `main()`, refuse to write a preview unless `read_promotion_status()`
  returns `PASS`.

- [x] **Step 4: Re-run tests to verify green**

Run the focused exporter suite and confirm it passes.

Observed: `5 passed`.

### Task 3: Isolated Paper-Dry Command And Readable Operations Guide

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `tests/test_modern_strategy_workflows.py`
- Modify: `docs/superpowers/specs/2026-05-26-quality-satellite-observation-design.md`

- [x] **Step 1: Write failing command-surface assertions**

Require the Makefile to expose:

```python
assert "paper-dry-quality-satellite:" in makefile
assert "scripts/generate_quality_paper_signals.py" in makefile
assert ".cache/signals/quality_reported_only_candidate_preview.json" in makefile
assert "scripts/trade_v2.py --dry-run --signals .cache/signals/quality_reported_only_candidate_preview.json" in makefile
```

- [x] **Step 2: Run tests to verify red**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_modern_strategy_workflows.py
```

Expected: FAIL because the quality paper-dry command is not exposed.

Observed: one expected failure for the missing
`paper-dry-quality-satellite` target; eight existing command-surface tests
passed.

- [x] **Step 3: Add the guarded Make command and README workflow**

Add:

```make
paper-dry-quality-satellite:
	$(MAKE) monitor-quality-satellite
	$(PYTHONPATH) $(PY) scripts/generate_quality_paper_signals.py --budget $(PAPER_PREVIEW_BUDGET) $(SIGNAL_ARGS)
	$(PYTHONPATH) $(PY) scripts/trade_v2.py --dry-run --signals .cache/signals/quality_reported_only_candidate_preview.json
```

Update README to explain:

- `reported_only` is the monitored quality candidate;
- `make monitor-quality-satellite` refreshes contemporaneous LightGBM and
  quality reports without contacting SEC;
- SEC data refresh remains an explicit prior command;
- `make paper-dry-quality-satellite` outputs only a protected `.cache`
  preview and never changes existing LightGBM candidate output.

- [x] **Step 4: Re-run focused tests to verify green**

Run the command-surface and exporter/report tests together.

Observed: `25 passed`.

### Task 4: Real Observation Run, Verification, And Publication

**Files:**
- Modify: `docs/superpowers/plans/2026-05-26-quality-satellite-observation.md`

- [x] **Step 1: Run a real current monitor refresh**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache make monitor-quality-satellite
```

Inspect `.cache/reports/quality_satellite_monitor_latest.md`; record current
provider/evaluation dates, promotion status, and `reported_only` key metrics.

Observed:

```text
latest_provider_session: 2026-05-22
latest_evaluable_session: 2026-05-21
promotion_gate: PASS
maximum_holding_count: 9
reported_only SPY/full: +18.00% ann excess, -9.38% max drawdown
reported_only QQQ/full: +11.09% ann excess, -9.07% max drawdown
reported_only QQQ/63d: +17.62% ann excess, -5.15% max drawdown
reported_only QQQ/126d: +22.85% ann excess, -9.07% max drawdown
```

The run refreshed all eight LightGBM comparison scenarios first. Qlib emitted
existing dependency/runtime advisories for legacy Gym, MLflow filesystem
tracking, and known provider missing-value handling; no scenario failed.

- [x] **Step 2: Run a real isolated paper-dry preview**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache make paper-dry-quality-satellite
```

Inspect `.cache/signals/quality_reported_only_candidate_preview.json` and
confirm it contains only reported-source holdings, at most nine buy-preview
orders, and `dry_run_only: true`.

Observed:

```text
strategy: quality_reported_only_candidate
variant: reported_only
target_rebalance: 2026-05-01
dry_run_only: true
holding_count: 9
reported leverage sources: 9 of 9
tickers: DXCM,FSLR,META,MU,NTES,NVDA,ODFL,QCOM,TXN
trade_v2 dry-run: 9 succeeded, 0 failed
```

The generated preview remained under `.cache/signals/` and no order
submission path was invoked. Reading the Parquet audit artifact emitted
Arrow `sysctlbyname` sandbox advisories but returned the expected data.

- [x] **Step 3: Run final verification**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m compileall -q src scripts tests
git diff --check
```

Expected: all project tests pass apart from identified third-party warnings;
compile and diff hygiene succeed.

Observed:

```text
full suite: 107 passed, 1 existing third-party websockets deprecation warning
compileall: passed
git diff --check: passed
```

The completion review found no actionable isolation or fail-closed defect in
the new report status, preview exporter, Make targets, or documentation.

- [x] **Step 4: Commit and push the verified implementation**

Stage only implementation, tests, README, specification clarification, and
this execution record; generated `.cache` artifacts remain ignored. Commit
and push to `origin/main`, then mark this publication step complete with the
actual commit identifiers.

Published to `origin/main`:

```text
4e6c185 docs: design quality satellite observation loop
398ff78 feat: add isolated quality satellite paper monitoring
```

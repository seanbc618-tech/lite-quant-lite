# TTM Quality Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add point-in-time trailing-twelve-month quality metrics and an auditable leverage fallback to the SEC fundamentals warehouse.

**Architecture:** Extend the existing canonical facts to daily snapshot pipeline rather than introducing a strategy workflow. For each visible filing, calculate FY-direct or FY-plus-YTD-bridge TTM metrics strictly from facts visible by its filing date, then expose reported/derived leverage provenance in both Parquet and coverage reports.

**Tech Stack:** Python 3.11, pandas/pyarrow, pytest, Make.

---

### Task 1: TTM Filing Measurements

**Files:**
- Modify: `src/us_quant/fundamentals.py`
- Modify: `tests/test_fundamentals.py`

- [x] **Step 1: Write failing tests for FY and quarterly TTM**

Add deterministic facts where `FY` values are used directly and where a `Q2`
filing bridges:

```python
net_income_ttm = 100.0 + 70.0 - 60.0
operating_cash_flow_ttm = 120.0 + 80.0 - 65.0
```

Assert `ttm_source` is respectively `reported_fy` and
`fy_plus_ytd_bridge`.

- [x] **Step 2: Verify red**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_fundamentals.py
```

Expected: FAIL because daily snapshots do not expose TTM fields.

- [x] **Step 3: Implement visible TTM calculation**

Extend `build_daily_quality_snapshot()` with:

```python
revenue_ttm
net_income_ttm
operating_cash_flow_ttm
roe_ttm
cash_conversion_ttm
ttm_source
```

Use only fact records whose `filed_date` is no later than the selected
filing's `filed_date`, prefer same-filing comparable YTD rows, and leave TTM
null per field if that field's bridge component is missing; keep the
construction method as provenance if another TTM field is produced.

- [x] **Step 4: Add missing-bridge and amendment/no-future tests**

Prove a quarterly row without a prior FY stays null and a later filed
amendment changes TTM only after its filing date.

- [x] **Step 5: Verify green**

Run focused tests until all TTM assertions pass.

### Task 2: Auditable Leverage Fallback

**Files:**
- Modify: `src/us_quant/fundamentals.py`
- Modify: `tests/test_fundamentals.py`

- [x] **Step 1: Write failing leverage-source tests**

Cover three selected filing states:

```python
reported = total_liabilities / total_assets
derived = (total_assets - stockholders_equity) / total_assets
missing = NaN
```

Assert matching `debt_to_assets_source` values of `reported`,
`derived_assets_minus_equity`, and `missing`.

- [x] **Step 2: Verify red**

Run the focused fundamentals test and confirm that provenance fields are not
yet emitted.

- [x] **Step 3: Implement fallback and provenance**

Retain reported values when available, compute the derived fallback only when
both balance-sheet inputs are present in the selected period, and expose
source in daily output.

- [x] **Step 4: Verify green**

Re-run the focused test suite and ensure prior raw quality ratio assertions
still pass.

### Task 3: Coverage Report And Real Cache Validation

**Files:**
- Modify: `scripts/build_sec_fundamentals.py`
- Modify: `tests/test_build_sec_fundamentals.py`
- Modify: `README.md`

- [x] **Step 1: Write failing report tests**

Assert the Markdown report contains TTM coverage, leverage provenance
coverage, and the warning that quality workflow promotion remains pending.

- [x] **Step 2: Implement report rendering**

Add TTM and leverage-source table content while preserving existing coverage
and cache-source reporting.

- [x] **Step 3: Run the cached full-universe build**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache make fundamentals-sec
```

Inspect `92/92` issuer coverage and record real TTM/leverage results in this
plan.

Observed cache-only validation:

```text
requested_symbols: 92
covered_symbols: 92
normalized_fact_rows: 101232
daily_snapshot_rows: 127704
latest roe_ttm available: 91
latest cash_conversion_ttm available: 90
latest debt_to_assets available: 91
latest ttm_source: fy_plus_ytd_bridge=73, reported_fy=18, missing=1
latest derived_assets_minus_equity: 22
cache refresh elapsed after indexing optimization: 2.40 seconds
```

- [x] **Step 4: Document the next strategy gate**

Update README to state that quality strategy evaluation uses TTM metrics and
cannot be promoted until coverage and later Qlib stress results pass.

### Task 4: Verification And Publication

**Files:**
- Modify: `docs/superpowers/plans/2026-05-26-ttm-quality-layer.md`

- [x] **Step 1: Run final verification**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m compileall -q src scripts tests
git diff --check
```

Observed result:

```text
91 passed, 1 third-party deprecation warning
compileall passed
git diff --check passed
```

- [x] **Step 2: Commit code and validation evidence**

Commit only tracked code/tests/docs changes; `.cache/` remains ignored.

- [x] **Step 3: Push the verified commits**

Push `main` to `origin/main` after confirming the worktree has no untracked
non-cache artifacts.

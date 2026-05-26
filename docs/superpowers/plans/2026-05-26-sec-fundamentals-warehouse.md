# SEC Fundamentals Warehouse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a point-in-time SEC fundamentals warehouse and coverage report for the modern equity universe, creating a dependable base for a later quality strategy.

**Architecture:** Read the modern provider universe, exclude benchmark ETFs, cache SEC JSON by CIK, normalize audited canonical facts with filing dates, build daily as-of quality snapshots, and write local-only Parquet/report outputs. Keep the strategy layer unchanged until live data coverage is inspected.

**Tech Stack:** Python 3.11, pandas/pyarrow, httpx, pytest, Make.

---

### Task 1: Canonical Facts Domain Model

**Files:**
- Create: `src/us_quant/fundamentals.py`
- Create: `tests/test_fundamentals.py`
- Modify: `src/us_quant/__init__.py`

- [x] **Step 1: Write failing normalization tests**

Add SEC-shaped fixture dictionaries that cover SEC ticker mapping, preferred
and fallback tags, accepted annual/quarterly forms, and canonical row columns.

- [x] **Step 2: Run the focused test and confirm red**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_fundamentals.py
```

Expected: FAIL because `us_quant.fundamentals` does not exist.

- [x] **Step 3: Implement the minimum normalizer**

Implement:

```python
build_cik_mapping(payload) -> dict[str, str]
read_investable_symbols(provider_uri, market="liquid100") -> list[str]
extract_canonical_facts(ticker, cik, companyfacts) -> pandas.DataFrame
```

Pad CIK values to ten digits, exclude `SPY` and `QQQ`, retain filing metadata,
accept `10-K`, `10-Q`, and their amendment forms, and apply documented tag
priority when duplicate canonical observations exist.

- [x] **Step 4: Run focused tests and self-review**

Confirm the output schema exposes the selected raw tag and no network or cache
side effects are hidden inside the normalizer.

### Task 2: Point-In-Time Quality Snapshots

**Files:**
- Modify: `src/us_quant/fundamentals.py`
- Modify: `tests/test_fundamentals.py`

- [x] **Step 1: Write failing point-in-time tests**

Test a quarterly filing visible from its `filed_date`, a later amendment
visible only after its later filing date, and filing-level calculation of
`roe`, `cash_conversion`, and `debt_to_assets`.

- [x] **Step 2: Run the test and confirm the missing behavior**

Run the same focused pytest command and inspect the failure for the new
snapshot API.

- [x] **Step 3: Implement daily as-of snapshot building**

Implement:

```python
build_daily_quality_snapshot(facts, sessions) -> pandas.DataFrame
```

Build quality ratios within a filing/accession before selecting the latest
visible filing per ticker/session. Preserve missing metrics as null values and
include source filing metadata for auditability.

- [x] **Step 4: Run focused tests and inspect PIT behavior**

Confirm the amendment test shows the original measurement before amendment
filing and the revised one afterward.

### Task 3: SEC Cache And Build Command

**Files:**
- Create: `scripts/build_sec_fundamentals.py`
- Create: `tests/test_build_sec_fundamentals.py`

- [x] **Step 1: Write failing orchestration tests**

Cover cached JSON loading, required contact-bearing user agent for uncached
requests, build output/report writing from fake SEC payloads, and ETF
exclusion from the provider universe.

- [x] **Step 2: Run script tests to confirm red**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_build_sec_fundamentals.py
```

- [x] **Step 3: Implement the cached SEC builder**

Add:

- Official SEC ticker/CIK mapping and per-CIK companyfacts/submissions fetches.
- `SEC_USER_AGENT` / `--user-agent` validation before any live request.
- Cache-first behavior with optional `--refresh`.
- `--symbols` for a small validation batch and provider-universe default.
- Local-only facts/snapshot Parquet outputs and a Markdown coverage report.

- [x] **Step 4: Run tests with fixture-shaped cached JSON**

Confirm no live SEC access is needed for the deterministic test suite.

### Task 4: Operational Entry Points And Documentation

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-05-26-sec-fundamentals-warehouse.md`

- [x] **Step 1: Add the `fundamentals-sec` target**

Expose the builder with `ARGS` support while leaving user-agent credentials in
the environment rather than hardcoding them.

- [x] **Step 2: Document local outputs and the small-run command**

Document the cache/report paths, SEC contact requirement, and the first live
validation pattern:

```bash
SEC_USER_AGENT="lite-quant-lite research contact@example.com" \
  make fundamentals-sec ARGS="--symbols AAPL,MSFT,NVDA"
```

- [x] **Step 3: Record scope honestly**

State that the provider still represents a current-universe sample and the
quality strategy will be implemented only after coverage review.

### Task 5: Verification And Delivery

**Files:**
- Modify: `docs/superpowers/plans/2026-05-26-sec-fundamentals-warehouse.md`

- [x] **Step 1: Run focused and full tests**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_fundamentals.py tests/test_build_sec_fundamentals.py
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
```

- [x] **Step 2: Run offline CLI smoke validation**

Use cached fixture-shaped SEC files in a temporary directory and verify the
facts table, daily snapshot, and coverage report can be written.

- [x] **Step 3: Defer the live full-universe request until contact is provided**

Do not invent a contact identity for SEC. Ask the operator for the compliant
`SEC_USER_AGENT` value needed for the three-symbol live smoke fetch and later
full-universe cache build.

- [ ] **Step 4: Commit the reviewed implementation**

Commit code, tests, docs, and command wiring only. Leave `.cache/` products
untracked.

### Verification Record (2026-05-26)

- The normalization test first failed because `us_quant.fundamentals` did not
  exist, then passed after adding canonical SEC field extraction.
- A missing-field filing test reproduced a `KeyError`; the snapshot builder now
  retains incomplete filings with null metrics and an explicit field count.
- A missing `SEC_USER_AGENT` test reproduced a false-success partial build; an
  uncached request without a contact identity now fails closed.
- A transient-request test verifies `0.12s` request spacing and retry behavior
  for a temporary SEC `503` response.
- `make fundamentals-sec ARGS="--help"` passes without network access.
- The offline CLI smoke test builds Parquet outputs and a report entirely from
  fixture-shaped cached SEC payloads.
- A live `AAPL,MSFT,NVDA` request was deferred until the operator supplied a
  compliant `SEC_USER_AGENT` contact string; its result is recorded below.

### Live Small-Batch Validation Record (2026-05-26)

- The operator supplied a compliant SEC contact identity and successfully
  fetched `AAPL`, `MSFT`, and `NVDA`: `4296` normalized fact rows and `4185`
  daily snapshot rows were cached locally.
- The initial live output exposed a filing-alignment defect: all three quality
  ratios had `0%` coverage because an isolated later shares-outstanding context
  was selected over the complete reporting-period context in the same filing.
- Two regression tests now cover complete-period selection and longest-duration
  alignment for income/cash-flow observations; rebuilding the cached sample
  yields `100.0%` daily coverage for all three metrics and all three issuers.
- The report now makes another important limit visible: latest fiscal periods
  differ (`AAPL Q2`, `MSFT Q3`, `NVDA Q1`), so a cross-sectional quality score
  must use period-normalized or trailing-twelve-month metrics before it is
  connected to strategy evaluation.

### Full-Universe Validation Record (2026-05-26)

- The operator fetched the full current equity universe and initially observed
  `99831` facts, `117433` snapshots, and seven missing issuers.
- Investigation showed all seven raw SEC files were available. Six foreign
  issuers required `20-F` / `6-K` support; `AZN` required `ifrs-full` field
  mappings, while `ASML` required preserving its `EUR` reporting unit.
- Regression tests now cover foreign issuer forms, IFRS quality mappings, and
  choosing `USD` when dual-currency issuer facts are available.
- After rebuilding from raw cache, coverage reached all `92` investable
  equities with `101232` fact rows and `127704` daily snapshots, with no
  retrieval errors.
- A repeated same-universe build originally took approximately `239s`.
  Normalized-fact reuse and vectorized as-of snapshots reduced a subsequent
  cache-only report refresh to `1.20s`.
- The next quality milestone must normalize income/cash-flow features to TTM
  periods and add an audited leverage fallback: `90` symbols reach at least
  `90%` ROE coverage and `88` reach that cash-conversion coverage, while only
  `67` reach that direct debt-to-assets coverage.

# Quality Trend Defense Gentle Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a named, research-only `gentle` exposure profile so the passing quality candidate can be retested with `100% / 75% / 50%` trend throttling while preserving the original hard-defense evidence.

**Architecture:** Extend the existing trend-state builder with a validated named mapping while keeping fail-closed data errors at zero exposure. Thread the selected profile through the CLI and report renderer, write gentle results to separate cache paths during the experiment, and reuse the existing gate unchanged so results remain comparable.

**Tech Stack:** Python 3.11, pandas, Qlib metrics already used by the runner, pytest, Make.

---

### Task 1: Named Exposure Profiles

**Files:**
- Modify: `scripts/run_quality_trend_defense_overlay.py`
- Modify: `tests/test_run_quality_trend_defense_overlay.py`

- [ ] **Step 1: Write failing behavior tests**

Add tests that call `build_trend_states(prices, lookback=3, profile="gentle")`
and assert that computable `defensive` and `cash` states expose `0.75` and
`0.50`, while a missing-prior-close state remains `0.0`. Add a test that an
unknown profile raises `ValueError`.

- [ ] **Step 2: Run RED**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py
```

Expected: FAIL because `build_trend_states` does not accept `profile`.

- [ ] **Step 3: Implement the minimal mapping**

Add:

```python
EXPOSURE_PROFILES = {
    "hard": {"risk_on": 1.0, "defensive": 0.5, "cash": 0.0},
    "gentle": {"risk_on": 1.0, "defensive": 0.75, "cash": 0.5},
}
```

Update `build_trend_states(..., profile: str = "hard")` to validate the
profile, derive the named state from the number of passing ETFs, map normal
states with `EXPOSURE_PROFILES[profile]`, and override exposure to `0.0`
whenever `failure_reason` is non-null.

- [ ] **Step 4: Run GREEN**

Run the focused pytest command from Step 2 and expect all tests in that file
to pass.

### Task 2: Auditable CLI And Report Profile

**Files:**
- Modify: `scripts/run_quality_trend_defense_overlay.py`
- Modify: `tests/test_run_quality_trend_defense_overlay.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing interface tests**

Extend the report test to pass `profile="gentle"` and assert:

```python
assert "exposure_profile: gentle" in report
assert "trend_rule: SPY,QQQ SMA(200) -> 100%/75%/50%" in report
```

Extend the CLI test to invoke `--profile gentle --help` or inspect the help
text for `--profile`.

- [ ] **Step 2: Run RED**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py
```

Expected: FAIL because the renderer and parser do not expose profiles.

- [ ] **Step 3: Thread the selected profile through the runner**

Add `--profile` with `choices=sorted(EXPOSURE_PROFILES)` and default `hard`;
pass it to `build_trend_states` and `render_overlay_report`. Render
`exposure_profile` and the selected normal-state exposure mapping. Update the
README defense paragraph to mention the optional gentle research invocation
and its independent output paths.

- [ ] **Step 4: Run GREEN and broader regression tests**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_quality_trend_defense_overlay.py tests/test_run_quality_satellite_candidate.py tests/test_modern_strategy_workflows.py
```

Expected: PASS.

### Task 3: Real Gentle-Profile Experiment

**Files:**
- Runtime output only: `.cache/reports/quality_trend_defense_gentle_latest.md`
- Runtime output only: `.cache/quality_trend_defense/gentle_daily_states.parquet`

- [ ] **Step 1: Run complete verification**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m compileall -q scripts src
git diff --check
```

Expected: test suite and checks succeed.

- [ ] **Step 2: Execute the gentle research chain**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache make quality-trend-defense DEFENSE_ARGS="--profile gentle --report .cache/reports/quality_trend_defense_gentle_latest.md --states-output .cache/quality_trend_defense/gentle_daily_states.parquet"
```

Expected: report and state parquet are written; `Overlay gate` truthfully
reports either `PASS` or `FAIL`.

- [ ] **Step 3: Interpret without paper integration**

Extract the gate table, original versus defended absolute drawdown, QQQ
retention, and excess drawdown tolerance. Do not add a paper target or commit
these research changes in this phase because the user requested testing first.

## Execution Record

Executed on the modern provider through `2026-05-22`, with the safe evaluable
session ending `2026-05-21`.

- TDD evidence: profile behavior tests first failed because `profile` was not
  accepted; report/CLI tests first failed because no profile field or CLI
  option existed. After implementation, focused regression tests passed.
- Verification evidence: full pytest suite passed with `123 passed, 1 warning`;
  `compileall` and `git diff --check` passed.
- Real run command:

```bash
MPLCONFIGDIR=/private/tmp/mplcache make quality-trend-defense DEFENSE_ARGS="--profile gentle --report .cache/reports/quality_trend_defense_gentle_latest.md --states-output .cache/quality_trend_defense/gentle_daily_states.parquet"
```

- Real result: `overlay_gate: FAIL` while the underlying
  `reported_only` quality gate remained `PASS`.

| metric | original | hard defense | gentle defense |
| --- | ---: | ---: | ---: |
| absolute annual return | 36.36% | 27.19% | 30.52% |
| absolute maximum drawdown | -27.78% | -12.58% | -19.52% |
| QQQ/full annual excess | 11.09% | 1.92% | 5.25% |
| QQQ/126d annual excess | 22.85% | 15.93% | 16.78% |
| average cash share | 0.00% | 16.57% | 8.43% |

The gentle profile preserved more return than the hard defense and retained
meaningful absolute drawdown improvement. It still failed the unchanged gate:
QQQ/full annual excess lost `5.84` percentage points, QQQ/126d lost `6.07`
percentage points, and QQQ/full excess drawdown worsened from `-9.07%` to
`-15.04%`. It must remain research-only and must not generate paper targets.

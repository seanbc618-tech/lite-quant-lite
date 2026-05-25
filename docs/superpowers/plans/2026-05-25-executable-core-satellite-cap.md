# Executable Core-Satellite Position-Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the `60% QQQ / 40% LightGBM` paper candidate with the configured ten-position execution guard.

**Architecture:** Test a distinct `topk=9` Qlib satellite against the configured limit, reject it if either performance or execution constraints fail, and make dry-run fail closed on position overflows. Do not truncate orders after evaluation and do not loosen risk limits.

**Tech Stack:** Python 3.11, Qlib, YAML, Make, pytest.

---

### Task 1: Capped Workflow Experiment

**Files:**
- Create: `config/qlib/workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml`
- Modify: `tests/test_modern_strategy_workflows.py`

- [x] **Step 1: Write the failing configuration test**

Add the workflow to `MODERN_WORKFLOWS` and add this test:

```python
def test_core_satellite_workflow_respects_execution_position_cap():
    workflow = load_workflow("workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml")
    strategy = workflow["port_analysis_config"]["strategy"]["kwargs"]

    assert workflow["experiment_name"] == "lightgbm_alpha158_liquid100_modern_core_satellite_topk9_deterministic"
    assert strategy["topk"] == 9
    assert strategy["n_drop"] == 1
    assert strategy["hold_thresh"] == 3
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_modern_strategy_workflows.py
```

Expected: FAIL because `config/qlib/workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml` does not exist.

- [x] **Step 3: Create experimental capped workflows**

Copy the existing low-turnover configuration content into the new workflow,
retaining its provider, model, data windows, and cost settings. Change exactly
the candidate identity and strategy target:

```yaml
experiment_name: lightgbm_alpha158_liquid100_modern_core_satellite_topk9_deterministic

port_analysis_config: &port_analysis_config
    strategy:
        class: DeterministicTopkDropoutStrategy
        module_path: us_quant.qlib_strategies
        kwargs:
            signal: <PRED>
            topk: 9
            n_drop: 2
            hold_thresh: 3
```

- [x] **Step 4: Run focused workflow tests and operational probes**

Result: an ordinary TopK workflow exceeded the hard constraint; a strategy
that prevented excess buys met the cap but failed benchmark validation. The
experimental config and command wiring were therefore not retained.

### Task 2: Fail-Closed Paper Guard

**Files:**
- Modify: `scripts/trade_v2.py`
- Modify: `tests/test_trade_v2.py`

- [x] **Step 1: Write the failing over-limit dry-run test**

Add a dry-run preview containing eleven distinct buy symbols and configure
`max_open_positions=10`.

```python
assert process_signals(None, signal_file, dry_run=True) == 1
```

- [x] **Step 2: Verify the existing warning-only behavior fails the test**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_trade_v2.py
```

Observed: FAIL because `process_signals(..., dry_run=True)` logged a warning
but returned `0` for eleven targets.

- [x] **Step 3: Fail closed when dry-run targets exceed the limit**

Change the target-count warning in `scripts/trade_v2.py` to an error and
return nonzero before simulated orders are accepted.

- [x] **Step 4: Run focused execution tests**

Observed: `tests/test_trade_v2.py` passed after the guard change.

### Task 3: Live Research And Dry-Run Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-25-executable-core-satellite-cap.md`

- [x] **Step 1: Run the full test suite**

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
```

Observed: `69 passed, 1 warning`; the warning is the existing third-party
`websockets.legacy` deprecation.

- [x] **Step 2: Generate and assess capped eight-window reports**

```bash
MPLCONFIGDIR=/private/tmp/mplcache make monitor-modern-core-satellite
```

Observed: the hard-capped `hold_thresh=3` run obeyed nine satellite holdings,
but QQQ composite excess after costs was negative for all four windows:
`-5.82%`, `-15.22%`, `-3.35%`, and `-3.78%`.

- [x] **Step 3: Reproduce and reject the overflowing preview**

```bash
MPLCONFIGDIR=/private/tmp/mplcache make paper-dry-modern-core-satellite
```

Observed before the guard fix: the apparently stronger uncapped variant
exported `11` target buy orders with a configured limit of `10`. This is a
failed execution candidate, not an approval.

- [x] **Step 4: Verify and commit the safety outcome**

Run the full tests and the over-limit dry-run reproduction after applying the
guard. Then commit only the fail-closed execution change, its regression test,
and this validation record.

```bash
git add scripts/trade_v2.py tests/test_trade_v2.py docs/superpowers/specs/2026-05-25-executable-core-satellite-cap-design.md docs/superpowers/plans/2026-05-25-executable-core-satellite-cap.md
git commit -m "fix: reject oversized paper preview targets"
```

Expected: no rejected strategy is wired into paper monitoring; over-limit
previews stop with a nonzero result.

### Verification Record (2026-05-26)

- Requested GitHub publication completed first: `origin/main` advanced through
  `fc5c1c9` before this investigation.
- The executable candidate probe reproduced `11` buy targets while
  `max_open_positions=10`.
- After the fail-closed guard change, running `trade_v2.py --dry-run` against
  that same generated preview returned nonzero and reported the position-limit
  violation before simulating orders.
- `MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q`
  completed with `69 passed, 1 warning`.
- No capped LightGBM variant was promoted: the hard-capped `hold_thresh=3`
  eight-window run failed all QQQ benchmark windows, and the `hold_thresh=1`
  full-window probe failed both SPY and QQQ.

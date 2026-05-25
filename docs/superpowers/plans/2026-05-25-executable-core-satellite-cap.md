# Executable Core-Satellite Position-Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the `60% QQQ / 40% LightGBM` paper candidate with the configured ten-position execution guard.

**Architecture:** Add a distinct `topk=9` Qlib satellite workflow and reuse the existing monitor, report combiner, and signal exporter with its experiment artifacts. Do not truncate orders after evaluation and do not loosen risk limits.

**Tech Stack:** Python 3.11, Qlib, YAML, Make, pytest.

---

### Task 1: Capped Workflow Contract

**Files:**
- Create: `config/qlib/workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml`
- Modify: `tests/test_modern_strategy_workflows.py`

- [ ] **Step 1: Write the failing configuration test**

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

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_modern_strategy_workflows.py
```

Expected: FAIL because `config/qlib/workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml` does not exist.

- [ ] **Step 3: Create the capped workflow**

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
            n_drop: 1
            hold_thresh: 3
```

- [ ] **Step 4: Run focused workflow tests**

Run the command from Step 2.

Expected: PASS.

### Task 2: Capped Operational Commands

**Files:**
- Modify: `Makefile`
- Modify: `tests/test_modern_strategy_workflows.py`

- [ ] **Step 1: Write failing Make command assertions**

Extend `test_makefile_exposes_monitor_and_guarded_paper_preview_commands()`:

```python
assert "CORE_SATELLITE_CONFIG := config/qlib/workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml" in makefile
assert "--base-config $(CORE_SATELLITE_CONFIG)" in makefile
assert "--experiment-base $(CORE_SATELLITE_EXPERIMENT_BASE)" in makefile
assert "--experiment-name $(CORE_SATELLITE_FULL_EXPERIMENT)" in makefile
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_modern_strategy_workflows.py::test_makefile_exposes_monitor_and_guarded_paper_preview_commands
```

Expected: FAIL because the current target still monitors the fifteen-name
satellite artifact.

- [ ] **Step 3: Wire the command surface to capped artifacts**

Add these Make variables:

```make
CORE_SATELLITE_CONFIG := config/qlib/workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml
CORE_SATELLITE_EXPERIMENT_BASE := lightgbm_alpha158_liquid100_modern_core_satellite_topk9_deterministic_monitor_
CORE_SATELLITE_FULL_EXPERIMENT := lightgbm_alpha158_liquid100_modern_core_satellite_topk9_deterministic_monitor_full_benchspy
```

Update the targets:

```make
monitor-modern-core-satellite:
	$(PYTHONPATH) $(PY) scripts/run_modern_candidate_monitor.py --base-config $(CORE_SATELLITE_CONFIG) --output-dir .cache/qlib_monitor/modern_core_satellite_topk9 --report .cache/reports/modern_core_satellite_satellite_latest.md --keep-going $(ARGS)
	$(PYTHONPATH) $(PY) scripts/evaluate_core_satellite_candidate.py --experiment-base $(CORE_SATELLITE_EXPERIMENT_BASE)

paper-dry-modern-core-satellite:
	$(MAKE) monitor-modern-core-satellite
	$(PYTHONPATH) $(PY) scripts/generate_candidate_paper_signals.py --experiment-name $(CORE_SATELLITE_FULL_EXPERIMENT) --output .cache/signals/modern_core_satellite_candidate_preview.json --budget $(PAPER_PREVIEW_BUDGET) --core-symbol QQQ --core-weight 0.6 $(SIGNAL_ARGS)
	$(PYTHONPATH) $(PY) scripts/trade_v2.py --dry-run --signals .cache/signals/modern_core_satellite_candidate_preview.json
```

- [ ] **Step 4: Run focused command tests**

Run both tests from Tasks 1 and 2.

Expected: PASS.

### Task 3: Live Research And Dry-Run Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-25-executable-core-satellite-cap.md`

- [ ] **Step 1: Run the full test suite**

```bash
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src .venv/bin/python -m pytest -q
```

Expected: all tests pass, allowing already-known third-party deprecation
warnings only.

- [ ] **Step 2: Generate the capped eight-window report**

```bash
MPLCONFIGDIR=/private/tmp/mplcache make monitor-modern-core-satellite
```

Expected: exit `0` and an updated
`.cache/reports/modern_core_satellite_monitor_latest.md` generated from the
`topk=9` experiment namespace.

- [ ] **Step 3: Generate the constrained dry-run preview**

```bash
MPLCONFIGDIR=/private/tmp/mplcache make paper-dry-modern-core-satellite
```

Expected: exit `0`, `dry_run_only: true`, no warning that target buys exceed
`max_open_positions=10`, and no more than ten buy orders in
`.cache/signals/modern_core_satellite_candidate_preview.json`.

- [ ] **Step 4: Record evidence and commit**

Append the actual report metrics, test count, and dry-run order count to this
plan. Then run:

```bash
git add Makefile config/qlib/workflow_lgb_alpha158_liquid100_modern_core_satellite_topk9.yaml tests/test_modern_strategy_workflows.py docs/superpowers/plans/2026-05-25-executable-core-satellite-cap.md
git commit -m "feat: cap core satellite paper holdings"
```

Expected: a commit containing only the capped workflow, command wiring,
tests, and verification record.

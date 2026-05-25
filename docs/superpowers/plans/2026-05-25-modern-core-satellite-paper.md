# Modern Core-Satellite Paper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repeatable reporting and guarded dry-run previews for a `60% QQQ / 40% LightGBM` paper-only candidate.

**Architecture:** Reuse the existing latest-window LightGBM monitor artifacts instead of retraining another alpha model. Add a focused report script for two-sleeve performance, extend the existing signal exporter for a passive core allocation, and make static order-limit checks visible during dry-run.

**Tech Stack:** Python 3.11, pandas, Qlib risk analysis, pytest, Make.

---

### Task 1: Core-Satellite Performance Report

**Files:**
- Create: `scripts/evaluate_core_satellite_candidate.py`
- Create: `tests/test_evaluate_core_satellite_candidate.py`

- [ ] Write a failing test for combining a satellite return series and a `QQQ`
  core series as independently growing sleeves, including each sleeve's entry
  and strategy costs.
- [ ] Run `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_evaluate_core_satellite_candidate.py`
  and confirm the module is missing.
- [ ] Implement `evaluate_sleeves`, report artifact discovery, scenario
  iteration, and Markdown rendering for the configured `0.4` alpha weight.
- [ ] Run the focused test again and confirm it passes.

### Task 2: Core-Satellite Preview Export

**Files:**
- Modify: `scripts/generate_candidate_paper_signals.py`
- Modify: `tests/test_generate_candidate_paper_signals.py`

- [ ] Write failing tests asserting that `core_symbol="QQQ"` and
  `core_weight=0.6` produce a `$600` core order from a `$1,000` preview plus
  satellite orders totaling `$400`, and that invalid weights are rejected.
- [ ] Run the focused tests and confirm failure because core allocation is not
  implemented.
- [ ] Add optional core arguments and allocation metadata while preserving
  satellite-only default behavior.
- [ ] Re-run the focused tests and confirm they pass.

### Task 3: Dry-Run Risk Visibility

**Files:**
- Modify: `scripts/trade_v2.py`
- Modify: `tests/test_trade_v2.py`

- [ ] Write a failing regression test where `--dry-run` receives a notional
  exceeding `config.trading.max_order_notional` and must return failure.
- [ ] Run the test and confirm the current dry-run incorrectly accepts the
  oversized order.
- [ ] Split static order validation from account-backed position validation;
  apply static validation in both modes and log target-count exposure in
  dry-run mode.
- [ ] Run the focused tests and confirm they pass.

### Task 4: Operational Commands And Verification

**Files:**
- Modify: `Makefile`
- Modify: `tests/test_modern_strategy_workflows.py`

- [ ] Write failing assertions for `monitor-modern-core-satellite` and
  `paper-dry-modern-core-satellite` Make targets.
- [ ] Implement targets that refresh the incumbent monitor, render the combined
  report, export a `$1,000` dry-run-only `QQQ` core preview, and execute it
  only under `--dry-run`.
- [ ] Run `PYTHONPATH=src .venv/bin/python -m pytest -q`.
- [ ] Run `make monitor-modern-core-satellite` and inspect its report.
- [ ] Run `make paper-dry-modern-core-satellite` and confirm static dry-run
  validation and dry-run-only protection remain active.

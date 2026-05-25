# Modern Candidate Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paper-only candidate preview and a rolling SPY/QQQ stress report driven by the newest safely evaluable modern-provider session.

**Architecture:** A focused monitor script clones the approved low-turnover YAML into dynamic scenario workflows and reports newest MLflow results. A separate exporter converts Qlib's latest portfolio artifact into a guarded dry-run JSON consumed by the existing trading executor.

**Tech Stack:** Python 3.11, PyYAML, pandas/pickle Qlib artifacts, pytest, GNU Make, Qlib/MLflow local artifacts

---

### Task 1: Dynamic Rolling Monitor

**Files:**
- Create: `scripts/run_modern_candidate_monitor.py`
- Create: `tests/test_run_modern_candidate_monitor.py`

- [x] Write failing tests proving trading-session windows reserve Qlib's required next execution-calendar session, generated workflows update benchmark/test/backtest ranges, and repeated experiment histories report only their newest run.
- [x] Run `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_modern_candidate_monitor.py` and confirm failures are caused by missing monitor behavior.
- [x] Implement calendar parsing, scenario generation, YAML mutation, workflow execution, and Markdown latest-run report writing.
- [x] Re-run the focused tests and confirm they pass.

### Task 2: Candidate Paper Preview Export

**Files:**
- Create: `scripts/generate_candidate_paper_signals.py`
- Create: `tests/test_generate_candidate_paper_signals.py`
- Modify: `scripts/trade_v2.py`
- Create: `tests/test_trade_v2.py`

- [x] Write failing tests for extracting latest holdings from a Qlib positions artifact, emitting normalized `dry_run_only` orders, and rejecting that payload without dry-run.
- [x] Run the focused tests and confirm they fail for missing behavior.
- [x] Implement the positions artifact discovery/exporter and the executor guard.
- [x] Re-run the focused tests and confirm they pass, including Qlib's native `Position` artifact type.

### Task 3: Operator Commands And Documentation

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `LOCAL_STACK.md`

- [x] Add `monitor-modern-low` for dynamic multi-window `SPY,QQQ` evaluation and `paper-dry-modern-low` for refreshed dry-run preview.
- [x] Document that these are observation-only commands, their generated output lives under `.cache/`, and order submission remains prohibited for candidate previews.
- [x] Run dry-run command construction and documentation-related tests through the full test suite.

### Task 4: Current-Data Verification And Publish

**Files:**
- Modify: `docs/superpowers/plans/2026-05-25-modern-candidate-monitor.md`

- [x] Run `make test`, `make health`, `make data-report-modern`, and Python compilation checks.
- [x] Run `make monitor-modern-low` against current local modern data and inspect the generated rolling report.
- [x] Run `make paper-dry-modern-low` and confirm the executor only previews the candidate holdings.
- [x] Record tested commands and the current observed monitoring status in this plan, then review the diff.
- Publication is performed after this checked-in verification record is complete.

## Design Coverage Review

- Dynamic latest-date SPY/QQQ pressure testing is covered by Task 1 and the `monitor-modern-low` command.
- Paper-only target portfolio visibility and submission protection are covered by Task 2.
- Repeatable operator entry points, documentation, real-data checks, and publishing are covered by Tasks 3 and 4.

## Verification Record

- `make test`: passed with `61 passed`.
- `make health`: passed.
- `make data-report-modern`: provider ends at `2026-05-22`, includes 94 `liquid100` instruments and both `SPY` and `QQQ`.
- `.venv/bin/python -m compileall scripts src tests`: passed.
- `make paper-dry-modern-low`: passed; exported 15 dry-run-only target holdings dated `2026-05-21`.
- `make monitor-modern-low`: completed all eight latest-window/benchmark scenarios. Qlib needs one following calendar session for the final execution step, so evaluation safely ends at `2026-05-21` while provider data reaches `2026-05-22`.

## Current Monitoring Readout

| benchmark | window | annualized excess with cost | max drawdown with cost | IR with cost |
|---|---:|---:|---:|---:|
| SPY | full | 12.37% | -18.72% | 0.7414 |
| SPY | 63d | 1.19% | -10.38% | 0.0751 |
| SPY | 126d | 25.48% | -7.89% | 1.9481 |
| SPY | 252d | 14.51% | -10.82% | 1.0889 |
| QQQ | full | 5.45% | -26.27% | 0.3095 |
| QQQ | 63d | -28.72% | -16.29% | -1.5931 |
| QQQ | 126d | 14.54% | -11.53% | 1.0567 |
| QQQ | 252d | 6.11% | -14.02% | 0.4232 |

Decision: retain the low-turnover workflow as a paper/research monitoring
candidate. Its full and medium-horizon SPY readings remain positive, while
the weak recent QQQ-relative window blocks any execution promotion.

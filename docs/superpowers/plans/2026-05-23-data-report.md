# Data Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `make data-report` to show whether the local Qlib data is old enough to limit strategy optimization.

**Architecture:** Implement a read-only report that parses Qlib calendar/instrument files, samples local Qlib feature coverage for key symbols, and inspects workflow YAML date windows. It should not download data or modify `mlruns/`.

**Tech Stack:** Python 3.11, pytest, pyyaml, qlib, Makefile.

---

### Task 1: Local Data Parsers

**Files:**
- Create: `scripts/data_report.py`
- Create: `tests/test_data_report.py`

- [x] Test calendar start/end parsing from `calendars/day.txt`.
- [x] Test instrument count parsing for `sp500` and `nasdaq100`.
- [x] Test workflow YAML parsing for experiment name, market, train/valid/test, and backtest windows.

### Task 2: Report Output

**Files:**
- Modify: `scripts/data_report.py`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `LOCAL_STACK.md`

- [x] Add Qlib sample symbol coverage using `D.features`.
- [x] Add Markdown-style output.
- [x] Add `make data-report`.
- [x] Document that the command is local-only and diagnostic.

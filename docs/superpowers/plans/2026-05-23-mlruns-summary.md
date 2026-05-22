# MLflow Runs Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `make report-runs` to summarize local Qlib MLflow experiments into a readable strategy comparison table.

**Architecture:** Implement a read-only parser for the local `mlruns/` file layout. It reads experiment metadata, run metadata, command parameters, and latest metric values, then prints a Markdown table sorted by cost-inclusive annualized excess return when available.

**Tech Stack:** Python 3.11, pytest, pathlib, simple YAML-like metadata parsing, Makefile.

---

### Task 1: Summary Parser

**Files:**
- Create: `scripts/summarize_mlruns.py`
- Create: `tests/test_summarize_mlruns.py`

- [ ] Build a tiny temporary `mlruns` fixture with one complete run and one failed/incomplete run.
- [ ] Test parsing experiment name, run id, status, command, IC, Rank IC, annualized return, max drawdown, and IR.
- [ ] Test Markdown table output includes sorted completed rows and incomplete rows.

### Task 2: Project Wiring

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `LOCAL_STACK.md`

- [ ] Add `make report-runs`.
- [ ] Document that `mlruns/` remains ignored and the report command reads local artifacts only.
- [ ] Run the command against real local `mlruns/`.


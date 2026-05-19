# ValueInvest Valuation Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small, stable valuation research probe using ValueInvest without making Yahoo Finance a hard dependency.

**Architecture:** Wrap ValueInvest's calculation engine behind `src/us_quant/valuation.py`. Support deterministic JSON/manual input first, with Yahoo as a best-effort CLI source that can fail gracefully under rate limits. Expose one CLI script and one Makefile target for small experiments before any broader strategy integration.

**Tech Stack:** Python 3.11, ValueInvest, pytest, argparse, JSON.

---

### Task 1: Valuation Core

**Files:**
- Create: `src/us_quant/valuation.py`
- Create: `tests/test_valuation.py`
- Modify: `src/us_quant/__init__.py`

- [ ] Write tests for mapping raw stock fields into a ValueInvest `Stock`.
- [ ] Write tests for running selected valuation methods from deterministic fixture data.
- [ ] Implement dataclasses for method results and valuation reports.
- [ ] Export the valuation helpers from `us_quant`.

### Task 2: CLI Probe

**Files:**
- Create: `scripts/value_stock.py`
- Create: `tests/test_value_stock_cli.py`

- [ ] Write a CLI test using a temporary JSON fixture and `--source json`.
- [ ] Implement readable table output and optional `--output-json`.
- [ ] Implement Yahoo mode as best-effort: return a clear non-zero error when Yahoo is unavailable.

### Task 3: Project Wiring

**Files:**
- Modify: `requirements.txt`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `LOCAL_STACK.md`

- [ ] Add `valueinvest[us]` to requirements.
- [ ] Add `make value SYMBOL=AAPL`.
- [ ] Document JSON/manual mode and Yahoo rate-limit caveat.
- [ ] Run `make test`, `make health`, and one JSON valuation CLI smoke test.


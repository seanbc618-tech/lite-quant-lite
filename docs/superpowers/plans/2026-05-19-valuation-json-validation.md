# Valuation JSON Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make offline valuation JSON inputs safer to maintain before expanding to real data ingestion.

**Architecture:** Add a small validator in `us_quant.valuation` that checks required identity, price, per-share, and cash-flow fields before a JSON file is accepted by the CLI. Add a `--validate-only` CLI mode and a second example based on ValueInvest's bundled Google-style preset data.

**Tech Stack:** Python 3.11, pytest, argparse, JSON, ValueInvest.

---

### Task 1: JSON Input Validation

**Files:**
- Modify: `src/us_quant/valuation.py`
- Modify: `tests/test_valuation.py`

- [ ] Add tests for missing required fields.
- [ ] Add tests for numeric fields that must be positive.
- [ ] Implement `validate_stock_input(data) -> list[str]`.

### Task 2: CLI Validate Mode

**Files:**
- Modify: `scripts/value_stock.py`
- Modify: `tests/test_value_stock_cli.py`

- [ ] Add `--validate-only` test for a valid fixture.
- [ ] Add `--validate-only` failure test for a missing field fixture.
- [ ] Implement CLI handling with clear output and exit codes.

### Task 3: Example and Docs

**Files:**
- Create: `examples/valuation/googl_valueinvest_preset.json`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `LOCAL_STACK.md`

- [ ] Add the GOOGL-style example.
- [ ] Add `make value-validate INPUT=...`.
- [ ] Document that examples are research fixtures, not live data.


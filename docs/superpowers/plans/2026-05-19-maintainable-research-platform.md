# Maintainable Research Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing local US quant stack into a maintainable research platform with repeatable local health checks, tests, and aligned docs.

**Architecture:** Keep the current script-first structure. Add a local-only health command that reports critical local dependencies and data state without requiring live broker credentials or reliable Yahoo access. Add tests around configuration compatibility and health-check behavior so future edits have a fast safety net.

**Tech Stack:** Python 3.11, pytest, Qlib, VectorBT, yfinance, Alpaca SDK, Pydantic settings, Makefile.

---

### Task 1: Test Harness

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Create: `tests/test_config.py`
- Create: `tests/test_health_check.py`

- [ ] **Step 1: Add pytest to development dependencies**

Add `pytest>=8.0.0` to `requirements.txt` so the local virtual environment can run the new checks.

- [ ] **Step 2: Configure pytest path**

Create `pytest.ini` with `pythonpath = src` and `testpaths = tests` so tests can import `us_quant` without shell-specific `PYTHONPATH` setup.

- [ ] **Step 3: Write config compatibility tests**

Cover both Alpaca variable families:

```python
def test_trading_config_accepts_apca_names(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret")
    cfg = TradingConfig()
    assert cfg.alpaca_api_key == "key"
    assert cfg.alpaca_secret_key == "secret"

def test_trading_config_accepts_legacy_alpaca_names(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    cfg = TradingConfig()
    assert cfg.alpaca_api_key == "key"
    assert cfg.alpaca_secret_key == "secret"
```

- [ ] **Step 4: Run tests and verify they fail before implementation**

Run `./.venv/bin/python -m pytest tests/test_config.py -q`.
Expected before implementation: the legacy Alpaca variable test fails because `TradingConfig` only declares the `APCA_*` validation aliases.

### Task 2: Health Check Script

**Files:**
- Create: `scripts/health_check.py`
- Create: `tests/test_health_check.py`
- Modify: `Makefile`

- [ ] **Step 1: Write health-check tests**

Test that local PASS/WARN/FAIL results are aggregated correctly and that warnings do not make the command fail when critical local checks pass.

- [ ] **Step 2: Implement `scripts/health_check.py`**

The script should report:

- Python package versions for `us_quant`, `qlib`, `vectorbt`, `numpy`, and `pandas`.
- Qlib data directory structure.
- Qlib data latest calendar date if available.
- Signal JSON validity for `signals/example_signals.json`.
- Optional Yahoo check only when `--check-yahoo` is passed; Yahoo failures should be `WARN`, not `FAIL`.

- [ ] **Step 3: Add Makefile target**

Add `health` target:

```make
health:
	$(PYTHONPATH) $(PY) scripts/health_check.py
```

- [ ] **Step 4: Verify**

Run `make health`.
Expected: exits 0 when local Qlib data, imports, and sample signal file are valid.

### Task 3: Trading Config Compatibility

**Files:**
- Modify: `src/us_quant/config.py`
- Modify: `scripts/trade_v2.py`
- Modify: `.env.example`

- [ ] **Step 1: Implement config compatibility**

Support both modern Alpaca names and legacy names:

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`

Also support the documented non-prefixed risk variables:

- `MAX_DAILY_LOSS_PCT`
- `MAX_ORDER_NOTIONAL`
- `MAX_OPEN_POSITIONS`
- `KILL_SWITCH_PATH`

- [ ] **Step 2: Simplify credential loading**

Update `trade_v2.py` to trust `config.trading.alpaca_api_key` and `config.trading.alpaca_secret_key`; remove the incorrect `model_config.get(...)` fallback.

- [ ] **Step 3: Verify tests**

Run `./.venv/bin/python -m pytest tests/test_config.py -q`.
Expected: both Alpaca variable families pass.

### Task 4: Documentation Alignment

**Files:**
- Modify: `README.md`
- Modify: `LOCAL_STACK.md`

- [ ] **Step 1: Add maintenance commands**

Document:

- `make smoke`
- `make health`
- `make test`
- `make paper-dry-v2`

- [ ] **Step 2: Clarify data source status**

State that local Qlib is the reliable offline research path and Yahoo checks can be rate-limited or unavailable.

- [ ] **Step 3: Verify commands**

Run `make smoke`, `make health`, `make test`, and `make paper-dry-v2`.
Expected: local-only commands pass; Yahoo is not required by default health.


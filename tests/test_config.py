from __future__ import annotations

from pathlib import Path

from us_quant.config import TradingConfig


def test_trading_config_accepts_apca_names(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "apca-key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "apca-secret")
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    cfg = TradingConfig()

    assert cfg.alpaca_api_key == "apca-key"
    assert cfg.alpaca_secret_key == "apca-secret"


def test_trading_config_accepts_legacy_alpaca_names(monkeypatch):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    monkeypatch.setenv("ALPACA_API_KEY", "legacy-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "legacy-secret")

    cfg = TradingConfig()

    assert cfg.alpaca_api_key == "legacy-key"
    assert cfg.alpaca_secret_key == "legacy-secret"


def test_trading_config_accepts_documented_risk_env(monkeypatch, tmp_path):
    kill_switch = tmp_path / "KILL_SWITCH"
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "0.03")
    monkeypatch.setenv("MAX_ORDER_NOTIONAL", "250")
    monkeypatch.setenv("MAX_OPEN_POSITIONS", "4")
    monkeypatch.setenv("KILL_SWITCH_PATH", str(kill_switch))

    cfg = TradingConfig()

    assert cfg.max_daily_loss_pct == 0.03
    assert cfg.max_order_notional == 250.0
    assert cfg.max_open_positions == 4
    assert cfg.kill_switch_path == Path(kill_switch)

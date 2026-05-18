"""统一配置管理模块。

支持环境变量、.env 文件和默认值，使用 Pydantic 进行类型验证。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataConfig(BaseSettings):
    """数据源配置"""

    model_config = SettingsConfigDict(
        env_prefix="DATA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qlib_provider_uri: str = Field(
        default=str(Path.home() / ".qlib" / "qlib_data" / "us_data"),
        description="Qlib 数据目录",
    )
    qlib_region: Literal["us", "cn"] = Field(default="us", description="Qlib 区域")

    yahoo_cache_dir: str | None = Field(
        default=".cache/yahoo",
        description="Yahoo 数据缓存目录",
    )
    yahoo_timeout: int = Field(default=30, description="Yahoo 请求超时秒数")
    yahoo_max_retries: int = Field(default=3, description="Yahoo 最大重试次数")

    @field_validator("yahoo_cache_dir")
    @classmethod
    def validate_cache_dir(cls, v: str | None) -> str | None:
        if v:
            Path(v).mkdir(parents=True, exist_ok=True)
        return v


class TradingConfig(BaseSettings):
    """交易配置"""

    model_config = SettingsConfigDict(
        env_prefix="TRADE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Alpaca API 配置（支持多种环境变量名）
    alpaca_api_key: str | None = Field(
        default=None,
        description="Alpaca API Key",
        validation_alias=AliasChoices(
            "APCA_API_KEY_ID",
            "ALPACA_API_KEY",
            "TRADE_ALPACA_API_KEY",
        ),
    )
    alpaca_secret_key: str | None = Field(
        default=None,
        description="Alpaca Secret Key",
        validation_alias=AliasChoices(
            "APCA_API_SECRET_KEY",
            "ALPACA_SECRET_KEY",
            "TRADE_ALPACA_SECRET_KEY",
        ),
    )
    alpaca_paper: bool = Field(default=True, description="是否使用纸面交易")

    # 风控参数
    max_daily_loss_pct: float = Field(
        default=0.05,
        description="日内最大损失比例",
        validation_alias=AliasChoices("MAX_DAILY_LOSS_PCT", "TRADE_MAX_DAILY_LOSS_PCT"),
    )
    max_order_notional: float = Field(
        default=1000.0,
        description="单笔最大名义金额",
        validation_alias=AliasChoices("MAX_ORDER_NOTIONAL", "TRADE_MAX_ORDER_NOTIONAL"),
    )
    max_open_positions: int = Field(
        default=10,
        description="最大持仓数量",
        validation_alias=AliasChoices("MAX_OPEN_POSITIONS", "TRADE_MAX_OPEN_POSITIONS"),
    )

    # Kill switch
    kill_switch_path: Path = Field(
        default=Path("signals/KILL_SWITCH"),
        description="Kill switch 文件路径",
        validation_alias=AliasChoices("KILL_SWITCH_PATH", "TRADE_KILL_SWITCH_PATH"),
    )


class LoggingConfig(BaseSettings):
    """日志配置"""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        description="日志格式",
    )
    log_dir: str = Field(default="logs", description="日志目录")
    retention_days: int = Field(default=30, description="日志保留天数")
    rotation_size: str = Field(default="10 MB", description="日志轮转大小")


class BacktestConfig(BaseSettings):
    """回测配置"""

    model_config = SettingsConfigDict(
        env_prefix="BACKTEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_start: str = Field(default="2015-01-01", description="默认开始日期")
    default_end: str = Field(default="2024-12-31", description="默认结束日期")
    default_split: str = Field(default="2022-01-01", description="默认样本外切分日期")
    default_cash: float = Field(default=10_000.0, description="默认初始资金")

    # 双均线默认参数
    ma_fast: int = Field(default=10, description="快均线周期")
    ma_slow: int = Field(default=30, description="慢均线周期")


class AppConfig(BaseSettings):
    """应用全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data: DataConfig = Field(default_factory=DataConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)

    # 项目路径
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2]
    )

    @property
    def signals_dir(self) -> Path:
        return self.project_root / "signals"

    @property
    def logs_dir(self) -> Path:
        path = self.project_root / self.logging.log_dir
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_config() -> AppConfig:
    """获取配置单例（缓存以提高性能）"""
    return AppConfig()


# 便捷导出
config = get_config()

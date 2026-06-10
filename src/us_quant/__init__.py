"""美股量化工具包。

提供数据获取、回测、交易执行等功能。
"""
from us_quant.config import config, get_config
from us_quant.data import (
    CacheManager,
    DataManager,
    DataRequest,
    QlibDataProvider,
    YahooDataProvider,
    get_data_manager,
)
from us_quant.fundamentals import (
    build_cik_mapping,
    build_daily_quality_snapshot,
    extract_canonical_facts,
    read_investable_symbols,
)
from us_quant.logger import get_logger, init_logging_from_config, logger
from us_quant.paths import PROJECT_ROOT, default_qlib_us_uri
from us_quant.rebalance import reconcile_positions
from us_quant.utils import (
    BacktestUtils,
    PerformanceMetrics,
    RiskManager,
    TechnicalIndicators,
    format_number,
    format_percent,
)
from us_quant.valuation import (
    DEFAULT_VALUATION_METHODS,
    ValuationMethodResult,
    ValuationReport,
    build_stock,
    fetch_yahoo_stock,
    run_valuation,
    validate_stock_input,
)

__version__ = "0.2.0"

__all__ = [
    # 配置
    "config",
    "get_config",
    # 日志
    "logger",
    "get_logger",
    "init_logging_from_config",
    # 数据
    "DataManager",
    "YahooDataProvider",
    "QlibDataProvider",
    "CacheManager",
    "DataRequest",
    "get_data_manager",
    # 基本面
    "build_cik_mapping",
    "build_daily_quality_snapshot",
    "extract_canonical_facts",
    "read_investable_symbols",
    # 路径
    "PROJECT_ROOT",
    "default_qlib_us_uri",
    "reconcile_positions",
    # 工具
    "TechnicalIndicators",
    "BacktestUtils",
    "RiskManager",
    "PerformanceMetrics",
    "format_number",
    "format_percent",
    # 估值
    "DEFAULT_VALUATION_METHODS",
    "ValuationMethodResult",
    "ValuationReport",
    "build_stock",
    "fetch_yahoo_stock",
    "run_valuation",
    "validate_stock_input",
]

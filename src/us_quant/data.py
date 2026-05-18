"""数据获取模块。

支持多种数据源（Yahoo Finance, Qlib），带本地缓存和自动重试机制。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Callable, TypeVar

import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from us_quant.config import config
from us_quant.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

T = TypeVar("T")


class DataError(Exception):
    """数据获取异常基类"""
    pass


class DataSourceError(DataError):
    """数据源错误"""
    pass


class CacheError(DataError):
    """缓存错误"""
    pass


@dataclass(frozen=True)
class DataRequest:
    """数据请求参数"""

    symbol: str
    start_date: str | None = None
    end_date: str | None = None
    interval: str = "1d"

    def cache_key(self) -> str:
        """生成缓存键"""
        content = f"{self.symbol}_{self.start_date}_{self.end_date}_{self.interval}"
        return hashlib.md5(content.encode()).hexdigest()


class CacheManager:
    """本地缓存管理器"""

    def __init__(self, cache_dir: str | Path | None = None, ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(".cache/data")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self._metadata_file = self.cache_dir / "cache_metadata.json"
        self._metadata: dict = self._load_metadata()

    def _load_metadata(self) -> dict:
        """加载缓存元数据"""
        if self._metadata_file.exists():
            try:
                return json.loads(self._metadata_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_metadata(self) -> None:
        """保存缓存元数据"""
        try:
            self._metadata_file.write_text(json.dumps(self._metadata, indent=2))
        except IOError as e:
            logger.warning(f"无法保存缓存元数据: {e}")

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.parquet"

    def get(self, key: str) -> pd.DataFrame | None:
        """获取缓存数据"""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        # 检查是否过期
        cached_time = self._metadata.get(key)
        if cached_time:
            cached_dt = datetime.fromisoformat(cached_time)
            if datetime.now() - cached_dt > self.ttl:
                logger.debug(f"缓存过期: {key}")
                self.delete(key)
                return None

        try:
            df = pd.read_parquet(cache_path)
            logger.debug(f"缓存命中: {key}")
            return df
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            return None

    def set(self, key: str, data: pd.DataFrame) -> None:
        """设置缓存数据"""
        cache_path = self._get_cache_path(key)
        try:
            data.to_parquet(cache_path, compression="zstd")
            self._metadata[key] = datetime.now().isoformat()
            self._save_metadata()
            logger.debug(f"缓存已保存: {key}")
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")

    def delete(self, key: str) -> None:
        """删除缓存"""
        cache_path = self._get_cache_path(key)
        try:
            if cache_path.exists():
                cache_path.unlink()
            self._metadata.pop(key, None)
            self._save_metadata()
        except IOError as e:
            logger.warning(f"删除缓存失败: {e}")

    def clear(self) -> None:
        """清空所有缓存"""
        for f in self.cache_dir.glob("*.parquet"):
            try:
                f.unlink()
            except IOError:
                pass
        self._metadata = {}
        self._save_metadata()
        logger.info("缓存已清空")


def with_cache(
    cache_manager: CacheManager | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """缓存装饰器工厂"""
    cm = cache_manager or CacheManager()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # 尝试从参数构建缓存键
            try:
                # 假设第一个参数是 DataRequest 或包含必要信息
                if args and isinstance(args[0], DataRequest):
                    cache_key = args[0].cache_key()
                elif "request" in kwargs and isinstance(kwargs["request"], DataRequest):
                    cache_key = kwargs["request"].cache_key()
                else:
                    # 使用函数名和参数构建键
                    key_data = f"{func.__name__}_{args}_{kwargs}"
                    cache_key = hashlib.md5(key_data.encode()).hexdigest()

                # 尝试读取缓存
                cached = cm.get(cache_key)
                if cached is not None:
                    return cached  # type: ignore

                # 执行函数
                result = func(*args, **kwargs)

                # 保存缓存
                if isinstance(result, pd.DataFrame):
                    cm.set(cache_key, result)

                return result
            except Exception:
                # 缓存失败不影响主功能
                return func(*args, **kwargs)

        return wrapper

    return decorator


class YahooDataProvider:
    """Yahoo Finance 数据提供者"""

    def __init__(self, cache_manager: CacheManager | None = None):
        self.cache = cache_manager or CacheManager(
            config.data.yahoo_cache_dir or ".cache/yahoo"
        )
        self.timeout = config.data.yahoo_timeout
        self.max_retries = config.data.yahoo_max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    def fetch(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        period: str | None = None,
        interval: str = "1d",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """获取 Yahoo Finance 数据。

        Args:
            symbol: 股票代码
            start: 开始日期 (YYYY-MM-DD)
            end: 结束日期 (YYYY-MM-DD)
            period: 周期（如 "1y", "5d"），与 start/end 互斥
            interval: 数据间隔 (1d, 1h, etc.)
            use_cache: 是否使用缓存

        Returns:
            DataFrame with OHLCV data
        """
        import yfinance as yf

        request = DataRequest(symbol, start, end, interval)

        # 检查缓存
        if use_cache:
            cached = self.cache.get(request.cache_key())
            if cached is not None:
                return cached

        try:
            logger.info(f"从 Yahoo 下载数据: {symbol}")
            ticker = yf.Ticker(symbol)

            if period:
                data = ticker.history(
                    period=period,
                    interval=interval,
                    timeout=self.timeout,
                )
            else:
                data = ticker.history(
                    start=start,
                    end=end,
                    interval=interval,
                    timeout=self.timeout,
                )

            if data.empty:
                raise DataSourceError(f"Yahoo 返回空数据: {symbol}")

            # 标准化列名
            data.columns = [c.lower().replace(" ", "_") for c in data.columns]

            # 保存缓存
            if use_cache:
                self.cache.set(request.cache_key(), data)

            return data

        except Exception as e:
            logger.error(f"获取 Yahoo 数据失败 {symbol}: {e}")
            raise DataSourceError(f"获取 {symbol} 数据失败: {e}") from e


class QlibDataProvider:
    """Qlib 数据提供者"""

    def __init__(self):
        self._initialized = False
        self._init_qlib()

    def _init_qlib(self) -> None:
        """初始化 Qlib"""
        if self._initialized:
            return

        try:
            import qlib

            provider_uri = config.data.qlib_provider_uri
            region = config.data.qlib_region

            qlib.init(provider_uri=provider_uri, region=region)
            self._initialized = True
            logger.info(f"Qlib 初始化完成: {provider_uri}")
        except Exception as e:
            logger.error(f"Qlib 初始化失败: {e}")
            raise DataSourceError(f"Qlib 初始化失败: {e}") from e

    def fetch_features(
        self,
        symbols: list[str],
        features: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """获取 Qlib 特征数据。

        Args:
            symbols: 股票代码列表
            features: 特征列表（如 ["$close", "$volume"]）
            start: 开始日期
            end: 结束日期

        Returns:
            DataFrame with multi-index (datetime, instrument)
        """
        try:
            from qlib.data import D

            logger.info(f"从 Qlib 获取数据: {symbols}, 特征: {features}")
            data = D.features(symbols, features, start_time=start, end_time=end)

            if data.empty:
                raise DataSourceError("Qlib 返回空数据")

            return data

        except Exception as e:
            logger.error(f"获取 Qlib 数据失败: {e}")
            raise DataSourceError(f"获取 Qlib 数据失败: {e}") from e

    def get_close_price(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.Series:
        """获取收盘价序列。

        Args:
            symbol: 股票代码
            start: 开始日期
            end: 结束日期

        Returns:
            收盘价 Series
        """
        data = self.fetch_features([symbol], ["$close"], start, end)
        close = data["$close"].xs(symbol, level="instrument").sort_index()
        close.index = pd.to_datetime(close.index)
        return close


class DataManager:
    """数据管理器：统一管理多种数据源"""

    def __init__(self):
        self.yahoo = YahooDataProvider()
        self.qlib = QlibDataProvider()
        self._cache = CacheManager()

    def get_price_data(
        self,
        symbol: str,
        source: str = "yahoo",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.Series:
        """获取价格数据（统一接口）。

        Args:
            symbol: 股票代码
            source: 数据源 ("yahoo" 或 "qlib")
            start: 开始日期
            end: 结束日期

        Returns:
            收盘价 Series
        """
        if source.lower() == "yahoo":
            data = self.yahoo.fetch(symbol, start, end)
            return data["close"]
        elif source.lower() == "qlib":
            return self.qlib.get_close_price(symbol, start, end)
        else:
            raise ValueError(f"不支持的数据源: {source}")

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        self.yahoo.cache.clear()


# 全局数据管理器实例
_data_manager: DataManager | None = None


def get_data_manager() -> DataManager:
    """获取数据管理器单例"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager

"""工具函数模块。

包含常用技术指标计算、回测工具、风险控制函数等。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from us_quant.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """绩效指标数据类"""

    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    num_trades: int

    def to_dict(self) -> dict[str, float]:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "num_trades": self.num_trades,
        }

    def __str__(self) -> str:
        return (
            f"总收益率: {self.total_return:.2%}\n"
            f"年化收益率: {self.annualized_return:.2%}\n"
            f"波动率: {self.volatility:.2%}\n"
            f"夏普比率: {self.sharpe_ratio:.4f}\n"
            f"最大回撤: {self.max_drawdown:.2%}\n"
            f"胜率: {self.win_rate:.2%}\n"
            f"盈亏比: {self.profit_factor:.4f}\n"
            f"交易次数: {self.num_trades}"
        )


class TechnicalIndicators:
    """技术指标计算类"""

    @staticmethod
    def sma(series: pd.Series, window: int) -> pd.Series:
        """简单移动平均线"""
        return series.rolling(window=window, min_periods=window).mean()

    @staticmethod
    def ema(series: pd.Series, span: int) -> pd.Series:
        """指数移动平均线"""
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, window: int = 14) -> pd.Series:
        """相对强弱指数"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """MACD 指标

        Returns:
            (macd_line, signal_line, histogram)
        """
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(
        series: pd.Series, window: int = 20, num_std: float = 2.0
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """布林带

        Returns:
            (upper_band, middle_band, lower_band)
        """
        middle = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        return upper, middle, lower

    @staticmethod
    def atr(
        high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14
    ) -> pd.Series:
        """平均真实波幅"""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()


class BacktestUtils:
    """回测工具类"""

    @staticmethod
    def calculate_metrics(
        returns: pd.Series,
        positions: pd.Series | None = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> PerformanceMetrics:
        """计算绩效指标。

        Args:
            returns: 日收益率序列
            positions: 持仓序列（可选，用于计算交易次数）
            risk_free_rate: 无风险利率（年化）
            periods_per_year: 每年交易周期数

        Returns:
            PerformanceMetrics 对象
        """
        returns = returns.dropna()

        if returns.empty:
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0)

        # 基础指标
        total_return = (1 + returns).prod() - 1
        n_years = len(returns) / periods_per_year
        annualized_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
        volatility = returns.std() * np.sqrt(periods_per_year)

        # 夏普比率
        if volatility > 0:
            sharpe = (annualized_return - risk_free_rate) / volatility
        else:
            sharpe = 0.0

        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # 交易相关指标
        if positions is not None:
            # 检测交易信号变化
            trades = positions.diff().abs()
            num_trades = int((trades > 0).sum())

            # 计算每笔交易的盈亏
            trade_returns = []
            in_position = False
            entry_return = 0.0

            for i, (ret, pos) in enumerate(zip(returns, positions)):
                if not in_position and pos > 0:
                    in_position = True
                    entry_return = 0.0
                elif in_position and pos == 0:
                    in_position = False
                    trade_returns.append(entry_return)
                elif in_position:
                    entry_return += ret

            if trade_returns:
                wins = [r for r in trade_returns if r > 0]
                losses = [r for r in trade_returns if r <= 0]
                win_rate = len(wins) / len(trade_returns) if trade_returns else 0
                avg_win = np.mean(wins) if wins else 0
                avg_loss = abs(np.mean(losses)) if losses else 1e-10
                profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
            else:
                win_rate = 0.0
                profit_factor = 0.0
        else:
            num_trades = 0
            win_rate = 0.0
            profit_factor = 0.0

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            num_trades=num_trades,
        )

    @staticmethod
    def ma_crossover_strategy(
        close: pd.Series,
        fast: int = 10,
        slow: int = 30,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """双均线交叉策略。

        Args:
            close: 收盘价序列
            fast: 快均线周期
            slow: 慢均线周期

        Returns:
            (positions, fast_ma, slow_ma)
        """
        fast_ma = close.rolling(fast).mean()
        slow_ma = close.rolling(slow).mean()

        # 生成信号：快线上穿慢线做多，下穿平仓
        signal = (fast_ma > slow_ma).astype(float).shift(1).fillna(0.0)

        return signal, fast_ma, slow_ma

    @staticmethod
    def split_is_oos(
        data: pd.Series | pd.DataFrame,
        split_date: str | None = None,
        split_pct: float = 0.75,
    ) -> tuple[pd.Series | pd.DataFrame, pd.Series | pd.DataFrame, pd.Timestamp]:
        """分割样本内/样本外数据。

        Args:
            data: 数据序列或DataFrame
            split_date: 切分日期（优先使用）
            split_pct: 切分比例（当 split_date 为 None 时使用）

        Returns:
            (is_data, oos_data, split_timestamp)
        """
        if split_date:
            split_ts = pd.Timestamp(split_date)
        else:
            idx = data.index.sort_values()
            cut_i = int(len(idx) * split_pct)
            split_ts = idx[cut_i]

        is_mask = data.index < split_ts
        oos_mask = data.index >= split_ts

        return data[is_mask], data[oos_mask], split_ts


class RiskManager:
    """风险管理工具类"""

    @staticmethod
    def position_sizing(
        capital: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        """计算仓位大小（固定风险法）。

        Args:
            capital: 总资金
            risk_per_trade: 每笔交易风险比例（如 0.02 表示 2%）
            entry_price: 入场价格
            stop_loss: 止损价格

        Returns:
            建议股数
        """
        risk_amount = capital * risk_per_trade
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share <= 0:
            return 0

        shares = int(risk_amount / risk_per_share)
        return max(0, shares)

    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """凯利公式计算最优仓位比例。

        Args:
            win_rate: 胜率
            avg_win: 平均盈利比例
            avg_loss: 平均亏损比例（正数）

        Returns:
            建议仓位比例
        """
        if avg_loss <= 0:
            return 0.0

        b = avg_win / avg_loss
        q = 1 - win_rate
        kelly = (win_rate * b - q) / b

        return max(0.0, min(kelly, 1.0))  # 限制在 0-1 之间

    @staticmethod
    def calculate_var(
        returns: pd.Series, confidence: float = 0.95, method: str = "historical"
    ) -> float:
        """计算风险价值 (VaR)。

        Args:
            returns: 收益率序列
            confidence: 置信度
            method: 计算方法 ("historical" 或 "parametric")

        Returns:
            VaR 值（负数表示损失）
        """
        if method == "historical":
            return np.percentile(returns.dropna(), (1 - confidence) * 100)
        elif method == "parametric":
            mean = returns.mean()
            std = returns.std()
            z_score = np.abs(np.percentile(np.random.standard_normal(10000), (1 - confidence) * 100))
            return mean - z_score * std
        else:
            raise ValueError(f"Unknown VaR method: {method}")


def format_number(num: float, precision: int = 2) -> str:
    """格式化数字显示"""
    if abs(num) >= 1e9:
        return f"{num/1e9:.{precision}f}B"
    elif abs(num) >= 1e6:
        return f"{num/1e6:.{precision}f}M"
    elif abs(num) >= 1e3:
        return f"{num/1e3:.{precision}f}K"
    else:
        return f"{num:.{precision}f}"


def format_percent(num: float, precision: int = 2) -> str:
    """格式化百分比显示"""
    return f"{num*100:.{precision}f}%"

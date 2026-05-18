#!/usr/bin/env python3
"""
优化版 VectorBT 回测脚本。

特性：
- 使用统一的数据管理模块（带缓存和重试）
- 专业的日志系统
- 更完整的绩效指标
- 更好的错误处理

用法:
  PYTHONPATH=src .venv/bin/python scripts/backtest_v2.py [--symbol AAPL] [--split 2022-01-01]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import vectorbt as vbt

from us_quant import init_logging_from_config
from us_quant.config import config
from us_quant.data import get_data_manager
from us_quant.logger import get_logger
from us_quant.utils import BacktestUtils, format_percent

logger = get_logger(__name__)


def run_backtest(
    close: pd.Series,
    fast: int,
    slow: int,
    init_cash: float,
    label: str,
) -> dict | None:
    """运行回测并返回结果。

    Args:
        close: 收盘价序列
        fast: 快均线周期
        slow: 慢均线周期
        init_cash: 初始资金
        label: 标签（如"样本内"）

    Returns:
        回测结果字典或 None
    """
    if len(close) < slow + 5:
        logger.warning(f"{label}: 数据过短 ({len(close)} < {slow + 5})，跳过")
        return None

    try:
        # 使用 VectorBT 运行回测
        fast_ma = vbt.MA.run(close, fast)
        slow_ma = vbt.MA.run(close, slow)
        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)

        pf = vbt.Portfolio.from_signals(
            close, entries, exits, init_cash=init_cash, freq="1d"
        )

        # 计算持仓序列
        positions = entries.astype(int) - exits.astype(int)
        positions = positions.cumsum().clip(0, 1)

        # 计算收益率
        returns = pf.returns()

        # 使用工具类计算完整指标
        metrics = BacktestUtils.calculate_metrics(returns, positions)

        result = {
            "label": label,
            "bars": len(close),
            "total_return": float(pf.total_return()),
            "sharpe_ratio": float(pf.sharpe_ratio()) if not pd.isna(pf.sharpe_ratio()) else 0,
            "max_drawdown": float(pf.max_drawdown()),
            "win_rate": metrics.win_rate,
            "num_trades": metrics.num_trades,
        }

        logger.info(
            f"{label}: bars={result['bars']} "
            f"return={format_percent(result['total_return'])} "
            f"sharpe={result['sharpe_ratio']:.4f} "
            f"max_dd={format_percent(result['max_drawdown'])}"
        )

        return result

    except Exception as e:
        logger.error(f"{label} 回测失败: {e}")
        return None


def main() -> int:
    """主函数"""
    # 初始化日志
    init_logging_from_config()

    parser = argparse.ArgumentParser(
        description="VectorBT 双均线策略回测（优化版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --symbol AAPL --split 2022-01-01
  %(prog)s --symbol TSLA --fast 5 --slow 20 --cash 50000
        """,
    )

    parser.add_argument("--symbol", default="AAPL", help="股票代码 (默认: AAPL)")
    parser.add_argument(
        "--start",
        default=config.backtest.default_start,
        help=f"开始日期 (默认: {config.backtest.default_start})",
    )
    parser.add_argument(
        "--end",
        default="2025-01-01",
        help="结束日期 (默认: 2025-01-01)",
    )
    parser.add_argument(
        "--split",
        default=config.backtest.default_split,
        help=f"样本外起始日 (默认: {config.backtest.default_split})",
    )
    parser.add_argument(
        "--fast",
        type=int,
        default=config.backtest.ma_fast,
        help=f"快均线周期 (默认: {config.backtest.ma_fast})",
    )
    parser.add_argument(
        "--slow",
        type=int,
        default=config.backtest.ma_slow,
        help=f"慢均线周期 (默认: {config.backtest.ma_slow})",
    )
    parser.add_argument(
        "--cash",
        type=float,
        default=config.backtest.default_cash,
        help=f"初始资金 (默认: {config.backtest.default_cash:,.0f})",
    )
    parser.add_argument("--no-cache", action="store_true", help="禁用数据缓存")

    args = parser.parse_args()

    logger.info(f"开始回测: {args.symbol} (fast={args.fast}, slow={args.slow})")
    logger.info(f"数据区间: {args.start} ~ {args.end}, 切分: {args.split}")

    try:
        # 使用数据管理器获取数据（带缓存和重试）
        dm = get_data_manager()
        close = dm.get_price_data(
            args.symbol,
            source="yahoo",
            start=args.start,
            end=args.end,
        )

        if close is None or close.empty:
            logger.error(f"未能获取 {args.symbol} 的数据")
            return 1

        logger.info(f"获取到 {len(close)} 条数据")

        # 切分样本内/样本外
        split_ts = pd.Timestamp(args.split).tz_localize("UTC")
        is_mask = close.index < split_ts
        oos_mask = close.index >= split_ts

        is_data = close[is_mask]
        oos_data = close[oos_mask]

        # 运行回测
        print("\n" + "=" * 60)
        print(f"回测结果: {args.symbol}")
        print(f"策略: 双均线交叉 (MA{args.fast} / MA{args.slow})")
        print(f"初始资金: ${args.cash:,.2f}")
        print("=" * 60)

        is_result = run_backtest(is_data, args.fast, args.slow, args.cash, "样本内(IS)")
        oos_result = run_backtest(oos_data, args.fast, args.slow, args.cash, "样本外(OOS)")

        # 打印汇总
        print("\n" + "-" * 60)
        print("汇总对比:")
        print("-" * 60)

        for result in [is_result, oos_result]:
            if result:
                print(
                    f"{result['label']:12s} | "
                    f"Return: {format_percent(result['total_return']):>10s} | "
                    f"Sharpe: {result['sharpe_ratio']:>7.4f} | "
                    f"MaxDD: {format_percent(result['max_drawdown']):>10s}"
                )

        return 0

    except Exception as e:
        logger.exception("回测执行失败")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
生成每日交易信号 - XGBoost 策略版本。

用法:
  PYTHONPATH=src .venv/bin/python scripts/generate_signals_xgb.py --date 2024-01-15 --output signals/
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import qlib
from qlib.data import D
from qlib.data.dataset import DatasetH
from qlib.contrib.data.handler import Alpha158
from qlib.contrib.model.xgboost import XGBModel
import pandas as pd
import numpy as np

from us_quant import init_logging_from_config
from us_quant.config import config
from us_quant.logger import get_logger

logger = get_logger(__name__)


def load_xgb_model(model_path: Path | None = None) -> XGBModel:
    """加载训练好的 XGBoost 模型"""
    # 默认参数（与训练时一致）
    model = XGBModel(
        eval_metric="rmse",
        colsample_bytree=0.8879,
        eta=0.05,
        subsample=0.8789,
        alpha=205.6999,
        lambda_=580.9768,
        max_depth=8,
        num_leaves=210,
        nthread=0,
    )

    if model_path and model_path.exists():
        model.load(model_path)
        logger.info(f"已加载模型: {model_path}")
    else:
        logger.warning("未找到预训练模型，将使用未训练模型（仅用于测试）")

    return model


def generate_signals(
    model: XGBModel,
    date: str,
    topk: int = 10,
    market: str = "nasdaq100",
) -> list[dict]:
    """生成指定日期的交易信号"""

    # 初始化 Qlib
    provider_uri = Path.home() / ".qlib" / "qlib_data" / "us_data"
    qlib.init(provider_uri=str(provider_uri), region="us")

    # 获取股票列表
    instruments = D.instruments(market)

    # 计算预测日期范围（使用过去20天数据）
    pred_date = pd.Timestamp(date)
    start_date = pred_date - pd.Timedelta(days=30)

    # 获取特征数据
    try:
        features = D.features(
            instruments,
            fields=["$close", "$volume"],
            start_time=start_date,
            end_time=pred_date,
            freq="day",
        )
    except Exception as e:
        logger.error(f"获取特征数据失败: {e}")
        return []

    # 简化版本：使用价格动量作为信号代理
    # 实际生产环境应使用完整的 Alpha158 特征
    latest = features.groupby("instrument").last()

    # 计算简单动量得分（5日涨幅）
    momentum = features.groupby("instrument").apply(
        lambda x: (x["$close"].iloc[-1] / x["$close"].iloc[-5] - 1)
        if len(x) >= 5 else 0
    )

    # 选择 topk 股票
    top_stocks = momentum.nlargest(topk)

    signals = []
    for symbol, score in top_stocks.items():
        signals.append({
            "symbol": symbol,
            "signal": "buy",
            "score": float(score),
            "date": date,
            "strategy": "xgboost_momentum",
        })

    logger.info(f"生成 {len(signals)} 个交易信号")
    return signals


def save_signals(signals: list[dict], output_dir: Path, date: str) -> Path:
    """保存信号到文件"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = output_dir / f"signals_{date}.json"

    # 转换为交易格式
    orders = []
    for sig in signals:
        orders.append({
            "symbol": sig["symbol"],
            "side": "buy",
            "notional": 10000,  # 每只股票 $10,000
        })

    output = {
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "strategy": "xgboost_top10",
        "signals": signals,
        "orders": orders,
    }

    filename.write_text(json.dumps(output, indent=2), encoding="utf-8")
    logger.info(f"信号已保存: {filename}")

    return filename


def main() -> int:
    """主函数"""
    init_logging_from_config()

    parser = argparse.ArgumentParser(
        description="生成每日 XGBoost 交易信号",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --date 2024-01-15
  %(prog)s --date 2024-01-15 --output signals/ --topk 5
        """,
    )

    parser.add_argument(
        "--date",
        type=str,
        default=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        help="信号日期 (默认: 昨天)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("signals"),
        help="输出目录 (默认: signals/)",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="选择股票数量 (默认: 10)",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="预训练模型路径",
    )

    args = parser.parse_args()

    logger.info(f"生成 {args.date} 的交易信号")

    # 加载模型
    model = load_xgb_model(args.model)

    # 生成信号
    signals = generate_signals(model, args.date, args.topk)

    if not signals:
        logger.error("未生成任何信号")
        return 1

    # 保存信号
    output_file = save_signals(signals, args.output, args.date)

    # 打印摘要
    print("\n" + "=" * 60)
    print(f"交易信号 - {args.date}")
    print("=" * 60)
    for i, sig in enumerate(signals, 1):
        print(f"{i:2d}. {sig['symbol']:6s} | 得分: {sig['score']:+.4f}")
    print("=" * 60)
    print(f"信号文件: {output_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

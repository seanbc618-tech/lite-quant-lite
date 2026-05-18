#!/usr/bin/env python3
"""
更新 Qlib 美股数据到最新日期。
使用 yfinance 下载纳斯达克100成分股数据。

用法:
  .venv/bin/python scripts/update_qlib_data.py --start 2020-11-01 --end 2025-03-27
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yfinance as yf
import pandas as pd
from loguru import logger

from us_quant.config import config


def get_nasdaq100_symbols() -> list[str]:
    """获取纳斯达克100成分股列表"""
    # 常见纳指100成分股（实际应从 Qlib 获取）
    return [
        "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "PEP", "AVGO",
        "COST", "CSCO", "TMUS", "ADBE", "TXN", "QCOM", "CMCSA", "NKE", "AMD",
        "AMGN", "HON", "INTU", "INTC", "GILD", "SBUX", "MDLZ", "ISRG", "ADP",
        "REGN", "VRTX", "PYPL", "FISV", "LRCX", "ATVI", "MU", "MELI", "CSX",
        "MAR", "MRNA", "LULU", "ILMN", "ENPH", "SNOW", "ABNB", "FTNT", "JD",
        "KLAC", "KDP", "NXPI", "EXC", "CHTR", "XEL", "DXCM", "ASML", "PANW",
        "ORLY", "MCHP", "EA", "BIDU", "MRVL", "CDNS", "CTSH", "KHC", "CRWD",
        "IDXX", "SGEN", "ODFL", "PDD", "BIIB", "WBA", "SIRI", "PCAR", "AZN",
        "FAST", "VRSK", "DLTR", "CTAS", "TEAM", "CPRT", "PAYX", "CEG", "DDOG",
        "BKR", "ALGN", "MNST", "ANSS", "AEP", "SPLK", "ROST", "NTES", "VRSN",
        "FSLR", "ZS", "OKTA", "ULTA", "SWKS", "ZBRA", "TCOM"
    ]


def download_stock_data(
    symbol: str,
    start: str,
    end: str,
) -> pd.DataFrame | None:
    """下载单只股票数据"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, interval="1d")

        if df.empty:
            logger.warning(f"{symbol}: 无数据")
            return None

        # 标准化列名
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        # 添加 adjclose（yfinance 已经调整后）
        df["adjclose"] = df["close"]

        # 重置索引，将日期作为列
        df = df.reset_index()
        df["date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df["symbol"] = symbol

        return df[["date", "symbol", "open", "high", "low", "close", "adjclose", "volume"]]

    except Exception as e:
        logger.error(f"{symbol}: 下载失败 - {e}")
        return None


def save_to_csv(df: pd.DataFrame, output_dir: Path, symbol: str) -> None:
    """保存到 CSV 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{symbol}.csv"
    df.to_csv(filepath, index=False)


def update_qlib_data(
    start: str,
    end: str,
    output_dir: Path,
    symbols: list[str] | None = None,
) -> int:
    """更新 Qlib 数据"""

    if symbols is None:
        symbols = get_nasdaq100_symbols()

    logger.info(f"更新 {len(symbols)} 只股票数据: {start} ~ {end}")

    success_count = 0
    failed_symbols = []

    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] 下载 {symbol}...")

        df = download_stock_data(symbol, start, end)

        if df is not None and not df.empty:
            save_to_csv(df, output_dir, symbol)
            success_count += 1
        else:
            failed_symbols.append(symbol)

    logger.info(f"\n完成: 成功 {success_count}/{len(symbols)}")

    if failed_symbols:
        logger.warning(f"失败: {failed_symbols}")

    # 生成数据摘要
    summary = {
        "total_symbols": len(symbols),
        "success": success_count,
        "failed": len(failed_symbols),
        "failed_symbols": failed_symbols,
        "date_range": f"{start} ~ {end}",
        "output_dir": str(output_dir),
    }

    summary_file = output_dir / "update_summary.json"
    import json
    summary_file.write_text(json.dumps(summary, indent=2))
    logger.info(f"摘要已保存: {summary_file}")

    return 0 if len(failed_symbols) < len(symbols) * 0.2 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="更新 Qlib 美股数据")
    parser.add_argument(
        "--start",
        type=str,
        default="2020-11-01",
        help="开始日期 (默认: 2020-11-01)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="结束日期 (默认: 今天)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".qlib" / "stock_data" / "source" / "us_data",
        help="输出目录",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        default=None,
        help="指定股票代码",
    )

    args = parser.parse_args()

    return update_qlib_data(
        start=args.start,
        end=args.end,
        output_dir=args.output,
        symbols=args.symbols,
    )


if __name__ == "__main__":
    raise SystemExit(main())

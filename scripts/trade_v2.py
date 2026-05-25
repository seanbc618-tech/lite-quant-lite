#!/usr/bin/env python3
"""
优化版 Alpaca 纸面交易执行脚本。

特性：
- 专业的日志系统
- 更完善的风控
- 统一的配置管理
- 更好的错误处理和重试

用法:
  PYTHONPATH=src .venv/bin/python scripts/trade_v2.py --dry-run --signals signals/example_signals.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from us_quant import init_logging_from_config
from us_quant.config import config
from us_quant.logger import get_logger

logger = get_logger(__name__)


def load_credentials() -> tuple[str, str]:
    """加载 Alpaca API 密钥"""
    key = config.trading.alpaca_api_key
    secret = config.trading.alpaca_secret_key

    if not key or not secret:
        raise ValueError(
            "缺少 Alpaca API 密钥。请设置环境变量:\n"
            "  APCA_API_KEY_ID / APCA_API_SECRET_KEY\n"
            "  或 ALPACA_API_KEY / ALPACA_SECRET_KEY"
        )

    return key, secret


def kill_switch_active() -> bool:
    """检查是否启用了 kill switch"""
    kill_path = config.trading.kill_switch_path
    return kill_path.is_file() and kill_path.stat().st_size > 0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
def get_account_info(client: TradingClient) -> dict[str, Any]:
    """获取账户信息（带重试）"""
    acct = client.get_account()
    return {
        "equity": float(acct.equity),
        "last_equity": float(acct.last_equity),
        "buying_power": float(acct.buying_power),
        "cash": float(acct.cash),
        "trading_blocked": acct.trading_blocked,
        "account_blocked": acct.account_blocked,
    }


def risk_check_account(client: TradingClient | None) -> None:
    """账户级风控检查"""
    if kill_switch_active():
        raise SystemExit("🛑 Kill-switch 已激活，拒绝所有交易")

    if client is None:
        return

    try:
        info = get_account_info(client)

        # 检查日内损失
        max_loss = config.trading.max_daily_loss_pct
        if info["last_equity"] > 0:
            loss_pct = (info["equity"] - info["last_equity"]) / info["last_equity"]
            if loss_pct <= -max_loss:
                raise SystemExit(
                    f"🛑 日内损失超限: {loss_pct:.2%} (限制: {max_loss:.2%})"
                )

        # 检查账户状态
        if info["trading_blocked"] or info["account_blocked"]:
            raise SystemExit("🛑 账户已被禁用")

        logger.info(
            f"账户状态: Equity=${info['equity']:,.2f}, "
            f"Daily P&L={((info['equity']/info['last_equity']-1)*100):+.2f}%"
        )

    except Exception as e:
        logger.error(f"账户检查失败: {e}")
        raise


def risk_check_order(
    client: TradingClient | None,
    symbol: str,
    side: str,
    notional: float | None,
    qty: float | None,
    positions: list | None = None,
) -> None:
    """订单级风控检查"""
    max_notional = config.trading.max_order_notional
    max_positions = config.trading.max_open_positions

    if notional is not None and notional > max_notional:
        raise ValueError(
            f"{symbol}: 单笔金额 ${notional:,.2f} 超过限制 ${max_notional:,.2f}"
        )

    if qty is not None and qty <= 0:
        raise ValueError(f"{symbol}: 数量必须为正数")

    # 检查持仓限制
    if positions is None and client is not None:
        positions = client.get_all_positions()

    if positions is None:
        return

    sym_have = {p.symbol for p in positions}
    if side.lower() == "buy" and symbol not in sym_have and len(positions) >= max_positions:
        raise ValueError(
            f"持仓数量 {len(positions)} 已达上限 {max_positions}，无法新开仓"
        )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
)
def submit_order(
    client: TradingClient,
    symbol: str,
    side: str,
    notional: float | None,
    qty: float | None,
) -> Any:
    """提交订单（带重试）"""
    side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

    if notional is not None:
        req = MarketOrderRequest(
            symbol=symbol,
            notional=notional,
            side=side_enum,
            time_in_force=TimeInForce.DAY,
        )
    else:
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side_enum,
            time_in_force=TimeInForce.DAY,
        )

    return client.submit_order(req)


def process_signals(
    client: TradingClient | None,
    signals_path: Path,
    dry_run: bool = False,
) -> int:
    """处理交易信号"""
    logger.info(f"{'[模拟模式] ' if dry_run else ''}处理信号文件: {signals_path}")

    # 读取信号文件
    try:
        data = json.loads(signals_path.read_text(encoding="utf-8"))
        orders = data.get("orders", [])
        if not orders:
            logger.warning("信号文件中没有订单")
            return 0
        if data.get("dry_run_only") and not dry_run:
            logger.error("候选策略观察单仅允许 --dry-run，拒绝提交订单")
            return 1
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"读取信号文件失败: {e}")
        return 1

    # 风控检查
    try:
        risk_check_account(client)
    except SystemExit as e:
        logger.error(str(e))
        return 1

    # 获取当前持仓（用于风控）
    positions = None
    if client:
        positions = client.get_all_positions()
        logger.info(f"当前持仓: {len(positions)} 个标的")
    elif dry_run:
        target_symbols = {order.get("symbol", "") for order in orders if order.get("side", "").lower() == "buy"}
        if len(target_symbols) > config.trading.max_open_positions:
            logger.error(
                f"目标买入标的 {len(target_symbols)} 个超过持仓限制 {config.trading.max_open_positions}；"
                "dry-run 观察单无效"
            )
            return 1

    # 处理每个订单
    success_count = 0
    failed_count = 0

    for order in orders:
        symbol = order.get("symbol", "")
        side = order.get("side", "")
        notional = order.get("notional")
        qty = order.get("qty")

        logger.info(f"处理订单: {symbol} {side} notional={notional} qty={qty}")

        # 参数校验
        if notional is not None and qty is not None:
            logger.error(f"{symbol}: notional 和 qty 不能同时指定")
            failed_count += 1
            continue

        if notional is None and qty is None:
            logger.error(f"{symbol}: 必须指定 notional 或 qty")
            failed_count += 1
            continue

        # 风控检查
        try:
            risk_check_order(
                client, symbol, side,
                float(notional) if notional else None,
                float(qty) if qty else None,
                positions,
            )
        except ValueError as e:
            logger.error(f"风控拦截: {e}")
            failed_count += 1
            continue

        # 执行或模拟
        try:
            if dry_run or client is None:
                logger.info(f"[模拟] 下单: {side} {symbol} notional={notional} qty={qty}")
                success_count += 1
            else:
                result = submit_order(
                    client,
                    symbol,
                    side,
                    float(notional) if notional else None,
                    float(qty) if qty else None,
                )
                logger.info(f"✓ 下单成功: {symbol} ID={result.id} Status={result.status}")
                success_count += 1

        except Exception as e:
            logger.error(f"✗ 下单失败 {symbol}: {e}")
            failed_count += 1

    logger.info(f"处理完成: 成功 {success_count}, 失败 {failed_count}")
    return 0 if failed_count == 0 else 1


def main() -> int:
    """主函数"""
    init_logging_from_config()

    parser = argparse.ArgumentParser(
        description="Alpaca 纸面交易执行（优化版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --dry-run --signals signals/example_signals.json
  %(prog)s --signals signals/my_signals.json
        """,
    )

    parser.add_argument(
        "--signals",
        type=Path,
        default=Path("signals/example_signals.json"),
        help="信号文件路径 (默认: signals/example_signals.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="模拟模式，不实际下单")

    args = parser.parse_args()

    # 初始化客户端
    client: TradingClient | None = None
    if not args.dry_run:
        try:
            key, secret = load_credentials()
            client = TradingClient(api_key=key, secret_key=secret, paper=True)
            logger.info("✓ Alpaca 客户端连接成功 (Paper Trading)")
        except Exception as e:
            logger.error(f"连接 Alpaca 失败: {e}")
            return 1
    else:
        logger.info("运行模式: 模拟交易 (dry-run)")

    return process_signals(client, args.signals, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

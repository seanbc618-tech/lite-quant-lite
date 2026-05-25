"""专业日志模块。

基于 loguru 的日志系统，支持文件轮转、控制台输出和结构化日志。
"""
from __future__ import annotations

import sys
from functools import lru_cache
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path

# 移除默认的日志处理器
logger.remove()


def resolve_log_output(format_str: str | None) -> tuple[str | None, bool]:
    """Map the documented JSON mode to Loguru's structured serialization."""
    if format_str and format_str.strip().lower() == "json":
        return "{message}", True
    return format_str, False


def setup_logging(
    level: str = "INFO",
    log_dir: str | Path = "logs",
    format_str: str | None = None,
    rotation: str = "10 MB",
    retention: str = "30 days",
    console: bool = True,
    file: bool = True,
) -> None:
    """设置日志系统。

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件目录
        format_str: 自定义格式字符串
        rotation: 日志轮转条件 (如 "10 MB", "1 day")
        retention: 日志保留时间 (如 "30 days")
        console: 是否输出到控制台
        file: 是否输出到文件
    """
    from pathlib import Path

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    if format_str is None:
        format_str = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        )
    format_str, serialize = resolve_log_output(format_str)

    # 控制台输出
    if console:
        logger.add(
            sys.stdout,
            level=level,
            format=format_str,
            colorize=True,
            serialize=serialize,
            enqueue=True,
        )

    # 文件输出
    if file:
        log_file = log_dir / "app_{time:YYYY-MM-DD}.log"
        logger.add(
            str(log_file),
            level=level,
            format=format_str,
            serialize=serialize,
            rotation=rotation,
            retention=retention,
            compression="gz",
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

        # 错误日志单独文件
        error_file = log_dir / "error_{time:YYYY-MM-DD}.log"
        logger.add(
            str(error_file),
            level="ERROR",
            format=format_str,
            serialize=serialize,
            rotation=rotation,
            retention=retention,
            compression="gz",
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )


@lru_cache()
def get_logger(name: str | None = None):
    """获取配置好的 logger 实例。

    Args:
        name: 模块名称（可选）

    Returns:
        配置好的 logger
    """
    if name:
        return logger.bind(name=name)
    return logger


def init_logging_from_config() -> None:
    """从配置初始化日志系统"""
    from us_quant.config import config

    setup_logging(
        level=config.logging.level,
        log_dir=config.logs_dir,
        format_str=config.logging.format,
        rotation=config.logging.rotation_size,
        retention=f"{config.logging.retention_days} days",
    )


# 导出 logger 供直接使用
__all__ = ["logger", "get_logger", "setup_logging", "init_logging_from_config"]

from __future__ import annotations

from pathlib import Path

# 项目根目录（…/美股自动化交易）
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_qlib_us_uri() -> str:
    """与 scripts/download_qlib_us.py 默认输出一致，供文档或代码引用。"""
    return str(Path.home() / ".qlib" / "qlib_data" / "us_data")

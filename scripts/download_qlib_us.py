#!/usr/bin/env python3
"""
下载 Qlib 官方美股日线数据包到本地（与研究报告中的方案 C 一致）。
不替代任何现有脚本；为新建工具。

用法:
  .venv/bin/python scripts/download_qlib_us.py [--target_dir PATH]
默认目录: ~/.qlib/qlib_data/us_data
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Qlib US market data bundle.")
    parser.add_argument(
        "--target_dir",
        type=Path,
        default=Path.home() / ".qlib" / "qlib_data" / "us_data",
        help="Output directory for qlib US data",
    )
    args = parser.parse_args()
    target = args.target_dir.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "qlib.cli.data",
        "qlib_data",
        "--target_dir",
        str(target),
        "--region",
        "us",
    ]
    print("Running:", " ".join(cmd))
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())

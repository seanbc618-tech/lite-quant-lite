#!/usr/bin/env python3
"""快速冒烟：导入核心依赖并打印版本。不替代正式单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    import numpy as np
    import pandas as pd
    import qlib
    import vectorbt as vbt

    from us_quant import __version__, default_qlib_us_uri

    print("us_quant", __version__)
    print("qlib", getattr(qlib, "__version__", "?"), "vectorbt", vbt.__version__)
    print("numpy", np.__version__, "pandas", pd.__version__)
    print("default_qlib_us_uri", default_qlib_us_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

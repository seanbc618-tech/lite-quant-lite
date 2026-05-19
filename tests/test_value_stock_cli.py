from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_value_stock_cli_reads_json_fixture(tmp_path):
    fixture = tmp_path / "stock.json"
    fixture.write_text(
        json.dumps(
            {
                "ticker": "demo",
                "name": "Demo Compounder",
                "current_price": 100.0,
                "shares_outstanding": 1_000_000_000,
                "eps": 6.0,
                "bvps": 25.0,
                "revenue": 10_000_000_000,
                "net_income": 1_000_000_000,
                "fcf": 900_000_000,
                "total_assets": 8_000_000_000,
                "current_assets": 3_000_000_000,
                "total_liabilities": 2_000_000_000,
                "current_liabilities": 1_000_000_000,
                "net_debt": -500_000_000,
                "growth_rate": 8.0,
                "growth_rate_1_5": 8.0,
                "growth_rate_6_10": 4.0,
                "discount_rate": 10.0,
                "terminal_growth": 2.5,
                "currency": "USD",
                "exchange": "NASDAQ",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/value_stock.py"),
            "--source",
            "json",
            "--input-json",
            str(fixture),
            "--methods",
            "graham_number,dcf",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "DEMO" in result.stdout
    assert "graham_number" in result.stdout
    assert "dcf" in result.stdout


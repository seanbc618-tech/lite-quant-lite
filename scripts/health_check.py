#!/usr/bin/env python3
"""Local health report for the US quant research stack.

The default checks are local-only. Use --check-yahoo when you explicitly want to
probe the external Yahoo path; Yahoo failures are warnings because rate limits
and transient network failures should not block local Qlib research.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

Status = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    message: str


def check_import_versions() -> CheckResult:
    packages = {
        "us_quant": "us_quant",
        "qlib": "qlib",
        "vectorbt": "vectorbt",
        "numpy": "numpy",
        "pandas": "pandas",
    }
    versions: list[str] = []
    try:
        for label, module_name in packages.items():
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "?")
            versions.append(f"{label}={version}")
    except Exception as exc:
        return CheckResult("imports", "FAIL", str(exc))
    return CheckResult("imports", "PASS", ", ".join(versions))


def check_qlib_dir(us_data: Path) -> CheckResult:
    us_data = us_data.expanduser().resolve()
    if not us_data.is_dir():
        return CheckResult("qlib_dir", "FAIL", f"missing directory: {us_data}")

    required = ["calendars", "instruments", "features"]
    missing = [name for name in required if not (us_data / name).is_dir()]
    if missing:
        return CheckResult("qlib_dir", "FAIL", f"missing subdirectories: {', '.join(missing)}")

    return CheckResult("qlib_dir", "PASS", str(us_data))


def read_calendar_latest(provider_uri: Path) -> str | None:
    calendar_dir = provider_uri.expanduser().resolve() / "calendars"
    latest = None
    for calendar_file in sorted(calendar_dir.glob("*.txt")):
        try:
            lines = [
                line.strip()
                for line in calendar_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except OSError:
            continue
        if lines:
            candidate = lines[-1]
            latest = max(latest, candidate) if latest else candidate
    return latest


def check_provider_freshness(
    provider_uri: Path,
    label: str,
    *,
    warn_days: int = 4,
    fail_days: int = 7,
    today: date | None = None,
) -> CheckResult:
    provider_uri = provider_uri.expanduser().resolve()
    if not provider_uri.is_dir():
        return CheckResult(label, "WARN", f"missing provider directory: {provider_uri}")

    latest = read_calendar_latest(provider_uri)
    if not latest:
        return CheckResult(label, "WARN", f"calendar is empty under {provider_uri}")

    today_date = today or date.today()
    lag_days = (today_date - date.fromisoformat(latest)).days
    message = f"latest session {latest} is {lag_days} day(s) behind {today_date.isoformat()}"
    if lag_days > fail_days:
        return CheckResult(label, "FAIL", message)
    if lag_days > warn_days:
        return CheckResult(label, "WARN", message)
    return CheckResult(label, "PASS", message)


def check_qlib_calendar(us_data: Path) -> CheckResult:
    calendar_dir = us_data.expanduser().resolve() / "calendars"
    calendar_files = sorted(calendar_dir.glob("*.txt"))
    if not calendar_files:
        return CheckResult("qlib_calendar", "WARN", f"no calendar txt files in {calendar_dir}")

    latest = None
    for calendar_file in calendar_files:
        try:
            lines = [
                line.strip()
                for line in calendar_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except OSError as exc:
            return CheckResult("qlib_calendar", "WARN", f"cannot read {calendar_file}: {exc}")
        if lines:
            candidate = lines[-1]
            latest = max(latest, candidate) if latest else candidate

    if not latest:
        return CheckResult("qlib_calendar", "WARN", "calendar files are empty")
    return CheckResult("qlib_calendar", "PASS", f"latest calendar date: {latest}")


def check_signal_file(path: Path) -> CheckResult:
    if not path.is_file():
        return CheckResult("signal_file", "FAIL", f"missing file: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CheckResult("signal_file", "FAIL", f"invalid json: {exc}")

    orders = payload.get("orders")
    if not isinstance(orders, list) or not orders:
        return CheckResult("signal_file", "FAIL", "orders must be a non-empty list")

    for index, order in enumerate(orders, start=1):
        if not isinstance(order, dict):
            return CheckResult("signal_file", "FAIL", f"order #{index} must be an object")
        missing = [field for field in ("symbol", "side") if not order.get(field)]
        if missing:
            return CheckResult(
                "signal_file",
                "FAIL",
                f"order #{index} missing fields: {', '.join(missing)}",
            )
        if ("notional" in order) == ("qty" in order):
            return CheckResult(
                "signal_file",
                "FAIL",
                f"order #{index} must set exactly one of notional or qty",
            )

    return CheckResult("signal_file", "PASS", f"{len(orders)} order(s) in {path}")


def check_yahoo(symbol: str) -> CheckResult:
    try:
        import yfinance as yf

        df = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
    except Exception as exc:
        return CheckResult("yahoo", "WARN", str(exc))

    if df is None or df.empty:
        return CheckResult("yahoo", "WARN", f"no data returned for {symbol}")
    return CheckResult("yahoo", "PASS", f"{symbol}: {len(df)} recent daily bar(s)")


def exit_code(results: list[CheckResult]) -> int:
    return 1 if any(result.status == "FAIL" for result in results) else 0


def print_report(results: list[CheckResult]) -> None:
    width = max(len(result.name) for result in results)
    for result in results:
        print(f"{result.status:4s} {result.name:{width}s}  {result.message}")


def run_checks(args: argparse.Namespace) -> list[CheckResult]:
    qlib_us_dir = args.qlib_us_dir.expanduser()
    results = [
        check_import_versions(),
        check_qlib_dir(qlib_us_dir),
        check_qlib_calendar(qlib_us_dir),
        check_signal_file(args.signals),
    ]
    if args.modern_provider_uri:
        results.append(
            check_provider_freshness(
                args.modern_provider_uri,
                "modern_freshness",
                warn_days=args.warn_stale_days,
                fail_days=args.max_stale_days,
            )
        )
    if args.check_yahoo:
        results.append(check_yahoo(args.yahoo_symbol))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="本地研究平台健康检查")
    parser.add_argument(
        "--qlib-us-dir",
        type=Path,
        default=Path.home() / ".qlib" / "qlib_data" / "us_data",
        help="Qlib us_data 目录",
    )
    parser.add_argument(
        "--signals",
        type=Path,
        default=Path("signals/example_signals.json"),
        help="示例信号文件",
    )
    parser.add_argument(
        "--modern-provider-uri",
        type=Path,
        default=Path.home() / ".qlib" / "qlib_data" / "us_modern_liquid100",
        help="现代 provider 目录；默认启用新鲜度检查",
    )
    parser.add_argument(
        "--skip-modern-freshness",
        action="store_true",
        help="跳过现代 provider 新鲜度检查",
    )
    parser.add_argument(
        "--warn-stale-days",
        type=int,
        default=4,
        help="现代 provider 超过该天数记为 WARN",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=7,
        help="现代 provider 超过该天数记为 FAIL",
    )
    parser.add_argument("--check-yahoo", action="store_true", help="额外探测 Yahoo 外部数据源")
    parser.add_argument("--yahoo-symbol", default="AAPL", help="Yahoo 探测标的")
    args = parser.parse_args()
    if args.skip_modern_freshness:
        args.modern_provider_uri = None

    results = run_checks(args)
    print_report(results)
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())

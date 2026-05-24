#!/usr/bin/env python3
"""Generate and run Qlib workflow sweeps for modern liquid100 parameters."""
from __future__ import annotations

import argparse
import copy
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_BASE_CONFIG = Path("config/qlib/workflow_lgb_alpha158_liquid100_modern.yaml")
DEFAULT_OUTPUT_DIR = Path(".cache/qlib_sweeps/modern_liquid100")
DEFAULT_TOPKS = (10, 15, 20)
DEFAULT_N_DROPS = (1, 2, 3)
COST_SCENARIOS = {
    "base": {"open_cost": 0.0005, "close_cost": 0.0015, "min_cost": 5},
    "half": {"open_cost": 0.00025, "close_cost": 0.00075, "min_cost": 2.5},
    "zero": {"open_cost": 0.0, "close_cost": 0.0, "min_cost": 0},
}


@dataclass(frozen=True)
class SweepSpec:
    topk: int
    n_drop: int
    cost_scenario: str


def build_sweep_specs(
    topks: list[int],
    n_drops: list[int],
    cost_scenarios: list[str],
) -> list[SweepSpec]:
    unknown = [name for name in cost_scenarios if name not in COST_SCENARIOS]
    if unknown:
        raise ValueError(f"unknown cost scenarios: {', '.join(unknown)}")
    return [
        SweepSpec(topk=topk, n_drop=n_drop, cost_scenario=cost_scenario)
        for cost_scenario in cost_scenarios
        for topk in topks
        for n_drop in n_drops
    ]


def experiment_name(base_name: str, spec: SweepSpec) -> str:
    return f"{base_name}_topk{spec.topk}_drop{spec.n_drop}_cost_{spec.cost_scenario}"


def apply_sweep_config(base_config: dict, spec: SweepSpec) -> dict:
    config = copy.deepcopy(base_config)
    base_name = str(config.get("experiment_name") or "qlib_sweep")
    config["experiment_name"] = experiment_name(base_name, spec)

    strategy_kwargs = config["port_analysis_config"]["strategy"]["kwargs"]
    strategy_kwargs["topk"] = spec.topk
    strategy_kwargs["n_drop"] = spec.n_drop

    exchange_kwargs = config["port_analysis_config"]["backtest"]["exchange_kwargs"]
    exchange_kwargs.update(COST_SCENARIOS[spec.cost_scenario])
    return config


def workflow_path(output_dir: Path, spec: SweepSpec) -> Path:
    return output_dir / f"topk{spec.topk}_drop{spec.n_drop}_cost_{spec.cost_scenario}.yaml"


def write_workflow(base_config: dict, output_dir: Path, spec: SweepSpec) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = workflow_path(output_dir, spec)
    config = apply_sweep_config(base_config, spec)
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"workflow config must be a mapping: {path}")
    return payload


def run_workflow(path: Path) -> int:
    cmd = [sys.executable, "-m", "qlib.cli.run", str(path)]
    print("Running:", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


def parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_str_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行现代 liquid100 Qlib 参数矩阵")
    parser.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG, help="基础 workflow YAML")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="临时 sweep workflow 输出目录")
    parser.add_argument("--topks", default=",".join(str(item) for item in DEFAULT_TOPKS), help="逗号分隔 topk")
    parser.add_argument("--n-drops", default=",".join(str(item) for item in DEFAULT_N_DROPS), help="逗号分隔 n_drop")
    parser.add_argument("--cost-scenarios", default="base", help=f"逗号分隔成本场景: {', '.join(COST_SCENARIOS)}")
    parser.add_argument("--dry-run", action="store_true", help="只生成 workflow，不运行 qlib")
    parser.add_argument("--keep-going", action="store_true", help="某组失败后继续运行后续组合")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    specs = build_sweep_specs(
        topks=parse_int_list(args.topks),
        n_drops=parse_int_list(args.n_drops),
        cost_scenarios=parse_str_list(args.cost_scenarios),
    )
    base_config = load_yaml(args.base_config)
    failures: list[Path] = []

    print(f"Prepared {len(specs)} sweep workflow(s).", flush=True)
    for index, spec in enumerate(specs, start=1):
        path = write_workflow(base_config, args.output_dir, spec)
        print(f"[{index}/{len(specs)}] {path}", flush=True)
        if args.dry_run:
            continue
        code = run_workflow(path)
        if code != 0:
            failures.append(path)
            if not args.keep_going:
                return code

    if failures:
        print("Failed workflows:")
        for path in failures:
            print(f"- {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

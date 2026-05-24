from __future__ import annotations

import yaml

from scripts.run_modern_param_sweep import (
    COST_SCENARIOS,
    SweepSpec,
    apply_sweep_config,
    build_sweep_specs,
    experiment_name,
)


def test_build_sweep_specs_defaults_to_nine_base_cost_runs():
    specs = build_sweep_specs(topks=[10, 15, 20], n_drops=[1, 2, 3], cost_scenarios=["base"])

    assert len(specs) == 9
    assert specs[0] == SweepSpec(topk=10, n_drop=1, cost_scenario="base")
    assert specs[-1] == SweepSpec(topk=20, n_drop=3, cost_scenario="base")


def test_experiment_name_includes_parameters():
    spec = SweepSpec(topk=15, n_drop=2, cost_scenario="zero")

    assert experiment_name("lightgbm_alpha158_liquid100_modern", spec) == (
        "lightgbm_alpha158_liquid100_modern_topk15_drop2_cost_zero"
    )


def test_apply_sweep_config_updates_strategy_cost_and_experiment_name():
    base = yaml.safe_load(
        """
experiment_name: lightgbm_alpha158_liquid100_modern
port_analysis_config:
  strategy:
    kwargs:
      signal: <PRED>
      topk: 20
      n_drop: 1
  backtest:
    exchange_kwargs:
      open_cost: 0.0005
      close_cost: 0.0015
      min_cost: 5
task:
  dataset:
    kwargs:
      segments:
        train: [2020-01-01, 2021-01-01]
"""
    )
    spec = SweepSpec(topk=10, n_drop=3, cost_scenario="half")

    updated = apply_sweep_config(base, spec)

    assert updated["experiment_name"] == "lightgbm_alpha158_liquid100_modern_topk10_drop3_cost_half"
    kwargs = updated["port_analysis_config"]["strategy"]["kwargs"]
    assert kwargs["topk"] == 10
    assert kwargs["n_drop"] == 3
    exchange = updated["port_analysis_config"]["backtest"]["exchange_kwargs"]
    assert exchange["open_cost"] == COST_SCENARIOS["half"]["open_cost"]
    assert exchange["close_cost"] == COST_SCENARIOS["half"]["close_cost"]
    assert exchange["min_cost"] == COST_SCENARIOS["half"]["min_cost"]

    assert base["port_analysis_config"]["strategy"]["kwargs"]["topk"] == 20

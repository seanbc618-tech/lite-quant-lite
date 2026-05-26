from __future__ import annotations

from pathlib import Path

import yaml


MODERN_WORKFLOWS = {
    "workflow_lgb_alpha360_liquid100_modern.yaml": ("LGBModel", "Alpha360"),
    "workflow_xgb_alpha158_liquid100_modern.yaml": ("XGBModel", "Alpha158"),
    "workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml": ("LGBModel", "Alpha158"),
}
ALL_MODERN_WORKFLOWS = (
    "workflow_lgb_alpha158_liquid100_modern.yaml",
    *MODERN_WORKFLOWS.keys(),
)


def load_workflow(name: str) -> dict:
    path = Path("config/qlib") / name
    assert path.is_file(), f"missing workflow: {path}"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_modern_strategy_workflows_target_liquid100_provider():
    for name in MODERN_WORKFLOWS:
        workflow = load_workflow(name)

        assert workflow["qlib_init"]["provider_uri"] == "~/.qlib/qlib_data/us_modern_liquid100"
        assert workflow["market"] == "liquid100"
        assert workflow["benchmark"] == "SPY"


def test_modern_strategy_workflows_use_expected_model_and_handler():
    for name, (model_class, handler_class) in MODERN_WORKFLOWS.items():
        workflow = load_workflow(name)

        assert workflow["task"]["model"]["class"] == model_class
        assert workflow["task"]["dataset"]["kwargs"]["handler"]["class"] == handler_class


def test_modern_strategy_workflows_pin_model_random_seeds():
    for name in ALL_MODERN_WORKFLOWS:
        workflow = load_workflow(name)
        model = workflow["task"]["model"]
        kwargs = model["kwargs"]

        if model["class"] == "LGBModel":
            assert kwargs["seed"] == 20260525
            assert kwargs["feature_fraction_seed"] == 20260525
            assert kwargs["bagging_seed"] == 20260525
            assert kwargs["data_random_seed"] == 20260525
        elif model["class"] == "XGBModel":
            assert kwargs["seed"] == 20260525


def test_modern_strategy_workflows_use_deterministic_topk_strategy():
    for name in ALL_MODERN_WORKFLOWS:
        workflow = load_workflow(name)
        strategy = workflow["port_analysis_config"]["strategy"]

        assert strategy["class"] == "DeterministicTopkDropoutStrategy"
        assert strategy["module_path"] == "us_quant.qlib_strategies"


def test_modern_strategy_workflows_separate_deterministic_experiments():
    for name in ALL_MODERN_WORKFLOWS:
        workflow = load_workflow(name)

        assert workflow["experiment_name"].endswith("_deterministic")


def test_modern_strategy_workflows_use_modern_windows_and_costs():
    for name in MODERN_WORKFLOWS:
        workflow = load_workflow(name)
        handler = workflow["data_handler_config"]
        segments = workflow["task"]["dataset"]["kwargs"]["segments"]
        backtest = workflow["port_analysis_config"]["backtest"]
        exchange = backtest["exchange_kwargs"]

        assert handler["start_time"] == "2020-11-02"
        assert handler["end_time"] == "2026-05-15"
        assert segments["train"] == ["2020-11-02", "2023-12-29"]
        assert segments["valid"] == ["2024-01-02", "2024-12-31"]
        assert segments["test"] == ["2025-01-02", "2026-05-15"]
        assert backtest["start_time"] == "2025-01-02"
        assert backtest["end_time"] == "2026-05-15"
        assert exchange["open_cost"] == 0.0005
        assert exchange["close_cost"] == 0.0015
        assert exchange["min_cost"] == 5


def test_low_turnover_workflow_is_conservative():
    workflow = load_workflow("workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml")
    strategy = workflow["port_analysis_config"]["strategy"]["kwargs"]
    model = workflow["task"]["model"]["kwargs"]

    assert workflow["experiment_name"] == "lightgbm_alpha158_liquid100_modern_low_turnover_candidate_deterministic"
    assert strategy["topk"] == 15
    assert strategy["n_drop"] == 1
    assert strategy["hold_thresh"] == 3
    assert model["learning_rate"] == 0.03


def test_xgb_workflow_does_not_include_lgb_only_parameters():
    workflow = load_workflow("workflow_xgb_alpha158_liquid100_modern.yaml")
    model = workflow["task"]["model"]["kwargs"]

    assert "num_leaves" not in model


def test_makefile_exposes_monitor_and_guarded_paper_preview_commands():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "monitor-modern-low:" in makefile
    assert "scripts/run_modern_candidate_monitor.py --keep-going" in makefile
    assert "paper-dry-modern-low:" in makefile
    assert "scripts/generate_candidate_paper_signals.py" in makefile
    assert "scripts/trade_v2.py --dry-run --signals .cache/signals/modern_low_candidate_preview.json" in makefile
    assert "monitor-modern-core-satellite:" in makefile
    assert "scripts/evaluate_core_satellite_candidate.py" in makefile
    assert "paper-dry-modern-core-satellite:" in makefile
    assert "--core-symbol QQQ --core-weight 0.6" in makefile
    assert "scripts/trade_v2.py --dry-run --signals .cache/signals/modern_core_satellite_candidate_preview.json" in makefile
    assert "monitor-quality-satellite:" in makefile
    assert "$(MAKE) monitor-modern-low" in makefile
    assert "--report .cache/reports/quality_satellite_monitor_latest.md" in makefile
    assert "paper-dry-quality-satellite:" in makefile
    assert "scripts/generate_quality_paper_signals.py" in makefile
    assert ".cache/signals/quality_reported_only_candidate_preview.json" in makefile
    assert "scripts/trade_v2.py --dry-run --signals .cache/signals/quality_reported_only_candidate_preview.json" in makefile

# 美股自动化交易 — 常用命令（需在项目根目录执行）

VENV := .venv/bin
PY := $(VENV)/python
PIP := $(PY) -m pip
PYTHONPATH := PYTHONPATH=src
MODERN_PROVIDER := $(HOME)/.qlib/qlib_data/us_modern_liquid100
MODERN_MARKET := liquid100
CSV_SOURCE := $(HOME)/.qlib/stock_data/source/us_data
PAPER_PREVIEW_BUDGET ?= 1000

.PHONY: install install-new data modern-provider update-modern-csv-nasdaq modern-provider-from-csv modern-provider-from-all-csv fundamentals-sec quality-satellite monitor-quality-satellite verify smoke health data-report data-report-modern test test-v2 test-trade vbt vbt-v2 qlib-simple qrun-ndx qrun-sp500 qrun-ndx-low qrun-alpha360 qrun-xgb qrun-alstm qrun-modern qrun-modern-alpha360 qrun-modern-xgb qrun-modern-low sweep-modern monitor-modern-low monitor-modern-core-satellite value value-json value-validate report-runs generate-signals update-data paper-dry paper-dry-v2 paper-dry-modern-low paper-dry-modern-core-satellite paper-dry-quality-satellite

install:
	$(PIP) install -r requirements.txt

install-new: install  # 安装新增依赖

# 数据
data:
	$(PY) scripts/download_qlib_us.py

modern-provider:
	$(PYTHONPATH) $(PY) scripts/build_modern_qlib_provider.py --provider-uri $(MODERN_PROVIDER) --market $(MODERN_MARKET) $(ARGS)

update-modern-csv-nasdaq:
	$(PYTHONPATH) $(PY) scripts/update_nasdaq_csv.py --csv-dir $(CSV_SOURCE) --symbols-from-provider $(MODERN_PROVIDER)/build_summary.json --symbols SPY QQQ $(ARGS)

modern-provider-from-csv:
	$(PYTHONPATH) $(PY) scripts/build_modern_qlib_provider.py --provider-uri $(MODERN_PROVIDER) --market $(MODERN_MARKET) --csv-dir $(CSV_SOURCE) $(ARGS)

modern-provider-from-all-csv:
	$(PYTHONPATH) $(PY) scripts/build_modern_qlib_provider.py --provider-uri $(MODERN_PROVIDER) --market $(MODERN_MARKET) --csv-dir $(CSV_SOURCE) --symbols-from-csv $(ARGS)

fundamentals-sec:
	$(PYTHONPATH) $(PY) scripts/build_sec_fundamentals.py --provider-uri $(MODERN_PROVIDER) --market $(MODERN_MARKET) $(ARGS)

quality-satellite:
	$(PYTHONPATH) $(PY) scripts/run_quality_satellite_candidate.py --provider-uri $(MODERN_PROVIDER) $(ARGS)

monitor-quality-satellite:
	$(MAKE) monitor-modern-low
	$(PYTHONPATH) $(PY) scripts/run_quality_satellite_candidate.py --provider-uri $(MODERN_PROVIDER) --report .cache/reports/quality_satellite_monitor_latest.md $(ARGS)

verify:
	$(PY) scripts/verify_data_sources.py

smoke:
	$(PY) scripts/smoke_test.py

health:
	$(PYTHONPATH) $(PY) scripts/health_check.py

data-report:
	$(PYTHONPATH) $(PY) scripts/data_report.py

data-report-modern:
	$(PYTHONPATH) $(PY) scripts/data_report.py --provider-uri $(MODERN_PROVIDER) --markets all,$(MODERN_MARKET) --symbols AAPL,MSFT,NVDA,SPY,QQQ

test:
	$(PY) -m pytest -q

# 测试新版脚本
test-v2:
	@echo "测试新版回测脚本..."
	$(PYTHONPATH) $(PY) scripts/backtest_v2.py --symbol AAPL --split 2022-01-01

test-trade:
	@echo "测试新版交易脚本 (模拟模式)..."
	$(PYTHONPATH) $(PY) scripts/trade_v2.py --dry-run --signals signals/example_signals.json

# 回测（旧版）
vbt:
	$(PY) scripts/backtest_vectorbt_baseline.py --symbol AAPL

qlib-simple:
	$(PY) scripts/backtest_qlib_baseline.py --symbol AAPL

# 回测（新版 - 推荐）
vbt-v2:
	$(PYTHONPATH) $(PY) scripts/backtest_v2.py --symbol AAPL

# Qlib 工作流
qrun-ndx:
	$(PY) -m qlib.cli.run config/qlib/workflow_lightgbm_alpha158_us_nasdaq100.yaml

qrun-sp500:
	$(PY) -m qlib.cli.run config/qlib/workflow_lightgbm_alpha158_us.yaml

# 优化版工作流
qrun-ndx-low:
	$(PY) -m qlib.cli.run config/qlib/workflow_lgb_ndx_low_turnover.yaml

qrun-alpha360:
	$(PY) -m qlib.cli.run config/qlib/workflow_lgb_alpha360_ndx.yaml

qrun-xgb:
	$(PY) -m qlib.cli.run config/qlib/workflow_xgb_alpha158_ndx.yaml

qrun-alstm:
	$(PY) -m qlib.cli.run config/qlib/workflow_alstm_alpha158_ndx.yaml

qrun-modern:
	$(PYTHONPATH) $(PY) -m qlib.cli.run config/qlib/workflow_lgb_alpha158_liquid100_modern.yaml

qrun-modern-alpha360:
	$(PYTHONPATH) $(PY) -m qlib.cli.run config/qlib/workflow_lgb_alpha360_liquid100_modern.yaml

qrun-modern-xgb:
	$(PYTHONPATH) $(PY) -m qlib.cli.run config/qlib/workflow_xgb_alpha158_liquid100_modern.yaml

qrun-modern-low:
	$(PYTHONPATH) $(PY) -m qlib.cli.run config/qlib/workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml

sweep-modern:
	$(PYTHONPATH) $(PY) scripts/run_modern_param_sweep.py $(ARGS)

monitor-modern-low:
	$(PYTHONPATH) $(PY) scripts/run_modern_candidate_monitor.py --keep-going $(ARGS)

monitor-modern-core-satellite:
	$(PYTHONPATH) $(PY) scripts/run_modern_candidate_monitor.py --keep-going $(ARGS)
	$(PYTHONPATH) $(PY) scripts/evaluate_core_satellite_candidate.py

# 估值探针
value:
	$(PYTHONPATH) $(PY) scripts/value_stock.py $(SYMBOL)

value-json:
	$(PYTHONPATH) $(PY) scripts/value_stock.py --source json --input-json $(INPUT)

value-validate:
	$(PYTHONPATH) $(PY) scripts/value_stock.py --source json --input-json $(INPUT) --validate-only

report-runs:
	$(PYTHONPATH) $(PY) scripts/summarize_mlruns.py

# 生成交易信号
generate-signals:
	$(PYTHONPATH) $(PY) scripts/generate_signals_xgb.py --date $(DATE)

# 数据更新
update-data:
	$(PY) scripts/update_qlib_data.py --start 2020-11-01

# 纸面交易（旧版）
paper-dry:
	$(PY) scripts/alpaca_paper_executor.py --dry-run --signals signals/example_signals.json

# 纸面交易（新版 - 推荐）
paper-dry-v2:
	$(PYTHONPATH) $(PY) scripts/trade_v2.py --dry-run --signals signals/example_signals.json

# 低换手候选：刷新最新组合后，仅做 paper dry-run 观察
paper-dry-modern-low:
	$(PYTHONPATH) $(PY) scripts/run_modern_candidate_monitor.py --benchmarks SPY --windows full --report .cache/reports/modern_low_paper_snapshot.md
	$(PYTHONPATH) $(PY) scripts/generate_candidate_paper_signals.py --output .cache/signals/modern_low_candidate_preview.json --budget $(PAPER_PREVIEW_BUDGET) $(SIGNAL_ARGS)
	$(PYTHONPATH) $(PY) scripts/trade_v2.py --dry-run --signals .cache/signals/modern_low_candidate_preview.json

# QQQ 核心 + LightGBM 卫星候选：仅供 dry-run 持续观察
paper-dry-modern-core-satellite:
	$(MAKE) monitor-modern-core-satellite
	$(PYTHONPATH) $(PY) scripts/generate_candidate_paper_signals.py --output .cache/signals/modern_core_satellite_candidate_preview.json --budget $(PAPER_PREVIEW_BUDGET) --core-symbol QQQ --core-weight 0.6 $(SIGNAL_ARGS)
	$(PYTHONPATH) $(PY) scripts/trade_v2.py --dry-run --signals .cache/signals/modern_core_satellite_candidate_preview.json

# SEC reported-only 质量候选：隔离式持续观察，不改变现有 ML 候选
paper-dry-quality-satellite:
	$(MAKE) monitor-quality-satellite
	$(PYTHONPATH) $(PY) scripts/generate_quality_paper_signals.py --budget $(PAPER_PREVIEW_BUDGET) $(SIGNAL_ARGS)
	$(PYTHONPATH) $(PY) scripts/trade_v2.py --dry-run --signals .cache/signals/quality_reported_only_candidate_preview.json

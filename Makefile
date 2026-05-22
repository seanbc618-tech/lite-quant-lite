# 美股自动化交易 — 常用命令（需在项目根目录执行）

VENV := .venv/bin
PY := $(VENV)/python
PIP := $(PY) -m pip
PYTHONPATH := PYTHONPATH=src

.PHONY: install install-new data verify smoke health data-report test test-v2 test-trade vbt vbt-v2 qlib-simple qrun-ndx qrun-sp500 qrun-ndx-low qrun-alpha360 qrun-xgb qrun-alstm value value-json value-validate report-runs generate-signals update-data paper-dry paper-dry-v2

install:
	$(PIP) install -r requirements.txt

install-new: install  # 安装新增依赖

# 数据
data:
	$(PY) scripts/download_qlib_us.py

verify:
	$(PY) scripts/verify_data_sources.py

smoke:
	$(PY) scripts/smoke_test.py

health:
	$(PYTHONPATH) $(PY) scripts/health_check.py

data-report:
	$(PYTHONPATH) $(PY) scripts/data_report.py

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
	$(VENV)/qrun config/qlib/workflow_lightgbm_alpha158_us_nasdaq100.yaml

qrun-sp500:
	$(VENV)/qrun config/qlib/workflow_lightgbm_alpha158_us.yaml

# 优化版工作流
qrun-ndx-low:
	$(VENV)/qrun config/qlib/workflow_lgb_ndx_low_turnover.yaml

qrun-alpha360:
	$(VENV)/qrun config/qlib/workflow_lgb_alpha360_ndx.yaml

qrun-xgb:
	$(VENV)/qrun config/qlib/workflow_xgb_alpha158_ndx.yaml

qrun-alstm:
	$(VENV)/qrun config/qlib/workflow_alstm_alpha158_ndx.yaml

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

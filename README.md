# 美股量化本地栈

本地研究 / 回测 / Alpaca 纸面交易的骨架项目，依赖 **Qlib**、**VectorBT**、**Alpaca**。详细约定见 [LOCAL_STACK.md](LOCAL_STACK.md)。

**新手请先读**：[docs/快速开始.md](docs/快速开始.md)（说明：本仓库**不是**研究报告里各 GitHub 项目的 clone；`sp500` / `nasdaq100` 如何用；演示输出怎么读。）

## 快速开始

```bash
cd "/Volumes/数据分区/美股自动化交易"  # 或切到你本机的项目根目录
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/download_qlib_us.py
.venv/bin/python scripts/verify_data_sources.py
```

## 维护检查

| 命令 | 说明 |
|------|------|
| `make smoke` | 快速确认核心库可导入并打印版本 |
| `make health` | 本地健康检查：依赖、Qlib 数据目录、日历截止、示例信号；默认不依赖 Yahoo |
| `make data-report` | 本地 Qlib 数据可用性报告：日历、股票池数量、样本标的覆盖、workflow 日期窗口 |
| `make modern-provider ARGS=--overwrite` | 构建小规模现代 Qlib provider，默认输出到 `~/.qlib/qlib_data/us_modern_mega20` |
| `make modern-provider-from-csv ARGS=--overwrite` | 用本机 `~/.qlib/stock_data/source/us_data/*.csv` 构建现代 provider，适合 Yahoo 限流时使用 |
| `make data-report-modern` | 检查小规模现代 provider 的日历、股票池和样本覆盖 |
| `make test` | 运行项目维护测试 |
| `make paper-dry-v2` | 新版交易执行层 dry-run，不触发真实下单 |
| `make value-validate INPUT=examples/valuation/demo_stock.json` | 只校验估值 JSON 输入 |
| `make value-json INPUT=examples/valuation/demo_stock.json` | 离线估值探针，读取 JSON 基本面输入 |
| `make report-runs` | 汇总本地 `mlruns/` 中的 Qlib 实验指标 |

`make verify` 会额外探测 Yahoo Finance，可能受 DNS、网络或 Yahoo 限流影响；本地 Qlib 研究链路是否可用，以 `make health` 和 Qlib 回测命令为准。

## 回测怎么跑

| 方式 | 命令 | 说明 |
|------|------|------|
| **VectorBT + Yahoo** | `.venv/bin/python scripts/backtest_vectorbt_baseline.py` | 双均线，按 `--split` 切 IS/OOS |
| **Qlib 数据 + 规则基线** | `.venv/bin/python scripts/backtest_qlib_baseline.py` | 读本地 `us_data`，默认按比例切分 |
| **Qlib 完整 ML + 回测（官方风格）** | `.venv/bin/qrun config/qlib/workflow_lightgbm_alpha158_us_nasdaq100.yaml` | LightGBM + Alpha158 + TopK 组合回测；产物在 `mlruns/` |

较快迭代可用 **nasdaq100** 配置；全市场 SP500 用 `config/qlib/workflow_lightgbm_alpha158_us.yaml`（耗时更长）。

**注意**：官方 `us_data` 日线常止于约 **2020-11**；工作流中回测结束日已设为 **2020-10-30**，避免 Qlib 交易日历在末端的越界错误。

已有 Qlib/MLflow 实验可用本地汇总表查看：

```bash
make data-report
make report-runs
```

`make data-report` 只读本地 Qlib provider 和 workflow YAML，不下载数据、不写入 `mlruns/`。`mlruns/` 仍然被 `.gitignore` 忽略；`make report-runs` 只读取本机实验产物，不会提交或上传实验文件。

若要先做近年数据的小范围试验，可构建独立的现代 provider：

```bash
make modern-provider ARGS=--overwrite
make data-report-modern
```

第一版默认使用 Yahoo Finance 下载 20 个大型流动性标的，写入独立目录 `~/.qlib/qlib_data/us_modern_mega20`，不会覆盖官方 `us_data`。

如果本机已有 `scripts/update_qlib_data.py` 生成过的 CSV，或 Yahoo 暂时限流，可改用：

```bash
make modern-provider-from-csv ARGS=--overwrite
make data-report-modern
```

## 其他脚本

- `scripts/alpaca_paper_executor.py`：读取 `signals/*.json` 下纸面单（需环境变量中的 Alpaca Paper Key）
- `scripts/trade_v2.py`：新版纸面执行入口，支持 dry-run、kill-switch 和统一配置
- `make smoke` / `make health` / `make test`：维护检查（见 Makefile）

## 目录结构（摘要）

```
config/qlib/          # qrun 工作流 YAML
scripts/              # 数据下载、回测、纸面执行
signals/              # 示例信号 JSON
src/us_quant/         # 共享常量（路径等）
```

## 选股（股票池 / 因子 / 规则）

概念与扩展方式见 [docs/选股指南.md](docs/选股指南.md)。快速示例：按流动性粗筛（Qlib 本地数据）：

```bash
.venv/bin/python scripts/screen_liquidity_qlib.py --market nasdaq100 --top 20
```

## 估值探针

估值层使用 `valueinvest` 做轻量计算，但默认推荐先走 JSON/手工输入，避免 Yahoo Finance 限流影响研究流程：

```bash
make value-validate INPUT=examples/valuation/demo_stock.json
make value-json INPUT=examples/valuation/demo_stock.json
make value-json INPUT=examples/valuation/googl_valueinvest_preset.json
```

`examples/valuation/googl_valueinvest_preset.json` 来自 ValueInvest 包内置的 Google 风格 preset 快照，只用于校准字段和流程，不代表实时估值数据。

也可以尝试在线 Yahoo 输入：

```bash
make value SYMBOL=AAPL
```

Yahoo 模式是 best-effort；遇到 DNS 或 rate limit 时会清楚失败，不影响 Qlib 本地研究链路。

## 研究报告

仓库内 Markdown 为调研笔记，不构成投资建议。

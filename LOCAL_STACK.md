# 美股量化本地栈说明

本目录实现《美股量化本地部署整合计划》中的交付物：**Python 虚拟环境 + Qlib 美股数据 + VectorBT/Qlib 基线回测 + Alpaca 纸面执行层 + 数据/时区约定**。

仓库**并未 clone** 研究报告中的 freqtrade / FinRL / Qlib 源码等；研究报告为笔记，依赖通过 `pip` 安装。入门与「演示输出」释义见 [docs/快速开始.md](docs/快速开始.md)。

## 1. 环境与依赖

- **Python**：建议 3.10–3.11（当前已在 3.11 验证）。
- **虚拟环境**：项目根目录 `.venv/`。
- **安装**：

```bash
cd "/Volumes/数据分区/美股自动化交易"  # 或切到你本机的项目根目录
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

- **主要包**：`pyqlib`、`vectorbt`、`yfinance`、`lightgbm`、`alpaca-py`（见 `requirements.txt`）。

## 2. 数据目录与时区约定

| 用途 | 路径/来源 | 说明 |
|------|-----------|------|
| Qlib 美股日线 | `~/.qlib/qlib_data/us_data` | 官方示例包，来源为 Yahoo，质量以 Qlib 说明为准 |
| Yahoo 备用 | `yfinance` / VectorBT `YFData` | 与研究报告一致，用于快速回测；注意时区多为 UTC |
| 信号文件 | `signals/*.json` | 供纸面执行层读取 |
| 估值 JSON | `examples/valuation/*.json` | 供离线估值探针读取，避免 Yahoo 限流 |

**单一数据源原则**：同一研究任务内不要混用「未对齐复权/未对齐时区」的序列。建议：**结构化因子与 Qlib 工作流用 `us_data`**；**快速原型与参数扫描用 Yahoo + VectorBT**。

**已知限制**：当前下载的 Qlib `us_data` 日线包在部分环境下**止于约 2020-11**；样本外切分请用 `scripts/backtest_qlib_baseline.py` 默认的 `--split_pct`，或自行更新数据包。

## 3. 命令速查

```bash
# 下载/更新 Qlib 美股数据
.venv/bin/python scripts/download_qlib_us.py

# 构建小规模现代 Qlib provider（默认 20 个大型流动性标的）
make modern-provider ARGS=--overwrite

# 若 Yahoo 限流，使用本机已有 CSV 构建
make modern-provider-from-csv ARGS=--overwrite

# 用 Nasdaq 接口更新 CSV 源，并补 SPY/QQQ benchmark
make update-modern-csv-nasdaq ARGS="--start 2025-03-27 --end 2026-05-24"

# 使用本机 CSV 目录中全部可用标的构建
make modern-provider-from-all-csv ARGS=--overwrite

# 校验 Qlib 目录 + Yahoo
.venv/bin/python scripts/verify_data_sources.py

# 本地健康检查（默认不依赖 Yahoo，适合日常维护）
make health

# 本地 Qlib 数据报告：日历、股票池、样本覆盖、workflow 日期窗口
make data-report

# 检查小规模现代 provider
make data-report-modern

# 现代 liquid100 参数矩阵
make sweep-modern ARGS="--cost-scenarios base"

# 运行维护测试
make test

# 汇总本地 Qlib/MLflow 实验
make report-runs

# 离线估值探针（不依赖 Yahoo）
make value-validate INPUT=examples/valuation/demo_stock.json
make value-json INPUT=examples/valuation/demo_stock.json

# VectorBT：Yahoo 行情，双均线，按日期切分 IS/OOS
.venv/bin/python scripts/backtest_vectorbt_baseline.py --symbol AAPL --split 2022-01-01

# Qlib：本地 us_data，双均线规则 + 按比例 IS/OOS（默认 75%/25%）
.venv/bin/python scripts/backtest_qlib_baseline.py --symbol AAPL

# Alpaca 纸面：仅打印不下单
.venv/bin/python scripts/alpaca_paper_executor.py --dry-run --signals signals/example_signals.json
```

### Qlib `qrun` 完整工作流（LightGBM + Alpha158 + 组合回测）

与 [Microsoft Qlib 官方 benchmarks](https://github.com/microsoft/qlib/tree/main/examples/benchmarks) 结构一致，已适配 **美股**（`region: us`、`sp500` / `nasdaq100`、基准 `SPY`、美股 `limit_threshold: null`）。

```bash
# 较快：nasdaq100（推荐先跑通）
.venv/bin/qrun config/qlib/workflow_lightgbm_alpha158_us_nasdaq100.yaml

# 全量：sp500（更耗时）
.venv/bin/qrun config/qlib/workflow_lightgbm_alpha158_us.yaml
```

也可用 Makefile：`make qrun-ndx` / `make qrun-sp500`。

现代 provider 可用 `make qrun-modern` 做链路验证。当前现代 workflow 使用 SPY 作为 benchmark；它适合确认近年数据能跑通 Qlib，再逐步做策略参数对比。现代策略对照组为 `make qrun-modern-alpha360`、`make qrun-modern-xgb`、`make qrun-modern-low`，分别覆盖 Alpha360、XGBoost 和经筛选的低换手 LightGBM 候选（`topk=15`、`n_drop=1`、`hold_thresh=3`）。该候选用于 paper/research 跟踪，不能替代滚动验证和实盘风控。

参数对比用 `make sweep-modern`，默认矩阵是 `topk=10/15/20` x `n_drop=1/2/3`，成本场景默认 `base`。它也支持 `--cost-scenarios base,half,zero`、`--benchmarks SPY,QQQ`、`--time-slices full,2025h1,2025h2,2026ytd`。临时 workflow 会写入 `.cache/qlib_sweeps/modern_liquid100/`，实验指标继续进入 `mlruns/`，用 `make report-runs` 汇总。

**产物**：实验与指标默认写入项目根目录 **`mlruns/`**（MLflow 文件存储），已加入 `.gitignore`。

**实验汇总**：`make report-runs` 会读取本机 `mlruns/` 并输出 Markdown 表，包含 IC、Rank IC、含成本年化超额收益、最大回撤、IR 等关键字段。该命令只读本地文件，不会把 `mlruns/` 纳入 Git。

**数据报告**：`make data-report` 会读取本地 Qlib provider、`instruments/*.txt` 和 `config/qlib/*.yaml`，并抽样检查 AAPL/MSFT/NVDA/SPY 的本地 `$close` 覆盖。该命令不下载数据、不写入 `mlruns/`，用于判断当前数据年代是否限制后续策略优化。

**现代 provider**：`make modern-provider ARGS=--overwrite` 会通过 Yahoo Finance 构建独立 provider：`~/.qlib/qlib_data/us_modern_liquid100`。默认目标股票池接近 100 个大型流动性标的（含 SPY/QQQ/AAPL/MSFT/NVDA 等），字段包含 `open/high/low/close/volume/vwap/factor/change`，适合验证现代数据能否支撑 Qlib 工作流。该命令不会覆盖官方 `us_data`。若 Yahoo 限流，且本机已有 `~/.qlib/stock_data/source/us_data/*.csv`，可用 `make update-modern-csv-nasdaq` 从 Nasdaq 补近年 CSV，再用 `make modern-provider-from-all-csv ARGS=--overwrite` 纳入全部本地 CSV。

**日历边界**：若回测 `end_time` 取数据最后一天，部分环境下 Qlib 会在 `TopkDropoutStrategy` 回测末步触发 `IndexError` 。当前配置将 **handler / 回测 / test 段** 统一收束到 **`2020-10-30`**，请与本地数据包截止日期一致调整。

**Yahoo 可用性**：`scripts/verify_data_sources.py` 会探测 Yahoo Finance；该路径可能因为 DNS、网络或 Yahoo rate limit 暂时失败。日常维护先看 `make health`，它默认只检查本地可控的 Qlib 数据和项目入口。

**非 git 仓库**：若项目未 `git init`，Qlib 录制器会尝试 `git diff` 记录代码差异并打印警告，**不影响训练与回测**；需要静默可执行 `git init` 仅初始化空仓库。

## 4. Alpaca 纸面交易

1. 在 [Alpaca Paper](https://app.alpaca.markets/paper/dashboard/overview) 创建 API Key。
2. 复制 `.env.example` 为 `.env`，填入 `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY`（或使用 `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`）。
3. 加载环境变量后执行（**勿**将 `.env` 提交到版本库）。

```bash
set -a && source .env && set +a   # bash/zsh 示例
.venv/bin/python scripts/alpaca_paper_executor.py --signals signals/example_signals.json
```

**Kill-switch**：

- 创建非空文件 `signals/KILL_SWITCH`（或设置 `KILL_SWITCH_PATH`）将拒绝一切真实下单。
- 环境变量：`MAX_DAILY_LOSS_PCT`（相对 `last_equity`）、`MAX_ORDER_NOTIONAL`、`MAX_OPEN_POSITIONS`。新版配置也接受 `TRADE_` 前缀形式。

脚本**强制 `paper=True`**，仅连接纸面 API URL；请仍使用 **Paper 专用密钥**。

## 5. 选股能力扩展

三层：**股票池（universe）**、**因子/模型横截面打分**、**规则初筛**。说明与示例命令见 [docs/选股指南.md](docs/选股指南.md)；规则层可参考 `scripts/screen_liquidity_qlib.py`（流动性排名）。

## 6. 估值能力扩展

`scripts/value_stock.py` 是小范围估值探针：使用 `valueinvest` 的 Graham、DCF、Reverse DCF、Owner Earnings、Altman Z、Piotroski F 等方法，但把数据获取和估值计算分开。稳定路径是 JSON 输入：

```bash
make value-validate INPUT=examples/valuation/demo_stock.json
make value-json INPUT=examples/valuation/demo_stock.json
make value-json INPUT=examples/valuation/googl_valueinvest_preset.json
```

`examples/valuation/googl_valueinvest_preset.json` 是 ValueInvest 包内置 Google 风格 preset 的快照，用于校准字段和流程；它不是实时财务数据。

在线路径可用：

```bash
make value SYMBOL=AAPL
```

该路径依赖 Yahoo Finance，可能受 DNS 或 rate limit 影响；失败时只代表在线数据源不可用，不代表估值引擎不可用。

## 7. 与仓库内研究报告的关系

- [量化交易模型研究报告.md](量化交易模型研究报告.md)：框架选型、风险提示；本栈避开已停更的 Zipline 作主路径。
- [AI美股程序化交易研究报告.md](AI美股程序化交易研究报告.md)：Qlib / VectorBT / Alpaca 路径与本目录脚本一致。

## 8. 免责声明

仅供研究与技术验证，不构成投资建议。程序化交易存在亏损与合规风险，实盘前请充分回测与纸面验证。

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
| `make modern-provider ARGS=--overwrite` | 构建现代 Qlib provider，默认输出到 `~/.qlib/qlib_data/us_modern_liquid100` |
| `make update-modern-csv-nasdaq ARGS="--start 2025-03-27 --end 2026-05-24"` | 用 Nasdaq 历史行情接口更新现代 provider 的 CSV 源，并补 SPY/QQQ |
| `make modern-provider-from-csv ARGS=--overwrite` | 用本机 `~/.qlib/stock_data/source/us_data/*.csv` 构建现代 provider，适合 Yahoo 限流时使用 |
| `make modern-provider-from-all-csv ARGS=--overwrite` | 用本机 CSV 目录中全部可用标的构建现代 provider |
| `make data-report-modern` | 检查小规模现代 provider 的日历、股票池和样本覆盖 |
| `make fundamentals-sec ARGS="--symbols AAPL,MSFT,NVDA"` | 从 SEC 缓存/接口构建 point-in-time 基本面与质量覆盖报告 |
| `make sweep-modern ARGS="--cost-scenarios base"` | 跑现代 liquid100 参数矩阵，默认 `topk=10/15/20`、`n_drop=1/2/3` |
| `make qrun-modern-alpha360` | 跑现代 liquid100 的 LightGBM + Alpha360 对照 |
| `make qrun-modern-xgb` | 跑现代 liquid100 的 XGBoost + Alpha158 对照 |
| `make qrun-modern-low` | 跑现代 liquid100 的低换手候选（Alpha158，`topk=15/n_drop=1/hold_thresh=3`） |
| `make monitor-modern-low` | 按最新可评估交易日运行低换手候选的 `SPY/QQQ` 滚动压力报告 |
| `make test` | 运行项目维护测试 |
| `make paper-dry-v2` | 新版交易执行层 dry-run，不触发真实下单 |
| `make paper-dry-modern-low` | 刷新低换手候选最新组合并仅做受保护的 dry-run 观察 |
| `make value-validate INPUT=examples/valuation/demo_stock.json` | 只校验估值 JSON 输入 |
| `make value-json INPUT=examples/valuation/demo_stock.json` | 离线估值探针，读取 JSON 基本面输入 |
| `make report-runs` | 汇总本地 `mlruns/` 中的 Qlib 实验指标 |

`make verify` 会额外探测 Yahoo Finance，可能受 DNS、网络或 Yahoo 限流影响；本地 Qlib 研究链路是否可用，以 `make health` 和 Qlib 回测命令为准。

## 回测怎么跑

| 方式 | 命令 | 说明 |
|------|------|------|
| **VectorBT + Yahoo** | `.venv/bin/python scripts/backtest_vectorbt_baseline.py` | 双均线，按 `--split` 切 IS/OOS |
| **Qlib 数据 + 规则基线** | `.venv/bin/python scripts/backtest_qlib_baseline.py` | 读本地 `us_data`，默认按比例切分 |
| **Qlib 完整 ML + 回测（官方风格）** | `make qrun-ndx` | LightGBM + Alpha158 + TopK 组合回测；产物在 `mlruns/` |
| **Qlib 现代样本验证** | `make qrun-modern` | 读取 `~/.qlib/qlib_data/us_modern_liquid100`，用于验证现代数据链路 |

较快迭代可用 **nasdaq100** 配置；全市场 SP500 用 `config/qlib/workflow_lightgbm_alpha158_us.yaml`（耗时更长）。现代样本验证用 `config/qlib/workflow_lgb_alpha158_liquid100_modern.yaml`。

现代策略对照组可用 `make qrun-modern-alpha360`、`make qrun-modern-xgb`、`make qrun-modern-low`。这些命令使用同一个 modern liquid100 provider 和日期窗口，方便用 `make report-runs` 横向比较。`qrun-modern-low` 是经确定性扫参筛出的 paper/research 候选，仍需持续滚动验证，不能视为实盘结论。

候选跟踪入口为 `make monitor-modern-low`：它根据现代 provider 最新交易日自动建立 `full/63d/126d/252d` 窗口，同时以 `SPY`、`QQQ` 为 benchmark，报告写到 `.cache/reports/modern_low_monitor_latest.md`。由于 Qlib 组合执行需要保留下一交易日，报告会同时列出 provider 最新日期和落后一交易日的安全评估截止日。需要查看最新目标组合的纸面预览时执行 `make paper-dry-modern-low`，它会把 Qlib 最终组合导出到 `.cache/signals/modern_low_candidate_preview.json` 并只以 `--dry-run` 读取；该文件带有 `dry_run_only` 防护，不能用于提交订单。

**注意**：官方 `us_data` 日线常止于约 **2020-11**；工作流中回测结束日已设为 **2020-10-30**，避免 Qlib 交易日历在末端的越界错误。

已有 Qlib/MLflow 实验可用本地汇总表查看：

```bash
make data-report
make report-runs
```

`make data-report` 只读本地 Qlib provider 和 workflow YAML，不下载数据、不写入 `mlruns/`。`mlruns/` 仍然被 `.gitignore` 忽略；`make report-runs` 只读取本机实验产物，不会提交或上传实验文件。

现代参数矩阵先跑持仓/换手组合，再用汇总表看结果：

```bash
make sweep-modern ARGS="--cost-scenarios base"
make report-runs
```

成本敏感性可在筛出较好的 topk/n_drop 后再跑，例如：

```bash
make sweep-modern ARGS="--topks 10,15 --n-drops 1,2 --cost-scenarios half,zero"
```

也可以切时间段或换 benchmark：

```bash
make sweep-modern ARGS="--topks 20 --n-drops 1 --cost-scenarios base --time-slices 2025h1,2025h2,2026ytd --benchmarks SPY,QQQ"
```

对已选出的候选策略持续进行最新窗口压力测试：

```bash
make monitor-modern-low
make paper-dry-modern-low
```

若要先做近年数据的小范围试验，可构建独立的现代 provider：

```bash
make modern-provider ARGS=--overwrite
make data-report-modern
```

默认使用 Yahoo Finance 下载一组接近 100 个大型流动性标的，写入独立目录 `~/.qlib/qlib_data/us_modern_liquid100`，不会覆盖官方 `us_data`。

如果本机已有 `scripts/update_qlib_data.py` 生成过的 CSV，或 Yahoo 暂时限流，可改用：

```bash
make modern-provider-from-csv ARGS=--overwrite
make data-report-modern
```

如果本机 CSV 目录已经有一批历史文件，可直接全部纳入：

```bash
make modern-provider-from-all-csv ARGS=--overwrite
make data-report-modern
```

若要把现代数据推进到近年，先更新 CSV，再重建 provider：

```bash
make update-modern-csv-nasdaq ARGS="--start 2025-03-27 --end 2026-05-24"
make modern-provider-from-all-csv ARGS=--overwrite
make data-report-modern
```

## SEC 基本面数据仓

真正的质量策略需要在每个历史决策日可见的财报事实，而不是把今天的
fundamentals 回填到过去。本项目现在以 SEC EDGAR 的 `companyfacts` 与
`submissions` 为首期来源，按 `filed_date` 构建 point-in-time 快照。

第一次联网小范围验证需要设置包含联系邮箱的 SEC `User-Agent`：

```bash
SEC_USER_AGENT="lite-quant-lite research contact@example.com" \
  make fundamentals-sec ARGS="--symbols AAPL,MSFT,NVDA"
```

原始响应缓存到 `.cache/sec/raw/`，标准化事实和日频质量快照写入
`.cache/fundamentals/`，覆盖率报告写入
`.cache/reports/fundamentals_quality_latest.md`。这些本地数据产物均不提交
到 Git。首期股票池使用当前 modern `liquid100` 中除 benchmark ETF 外的
股票，因此仍带有当前成分股的 survivorship bias；完成覆盖率验收后，才会
接入低波动质量策略回测与 paper 压力测试。

日频质量快照同时保留申报期原始比率和可审计的 TTM 质量层。年度申报直接
提供 TTM；季度申报仅在同一申报披露了当期累计值和上年同期累计值、且此前
完整财年已在当日可见时，使用 `FY + current YTD - prior-year YTD` 桥接。
`ttm_source` 记录桥接来源。`debt_to_assets_source` 则区分已申报负债与
缺失负债时使用 `(assets - equity) / assets` 的推导值。

在当前 92 只股票的本地缓存验证中，最新截面有 91 只具备 `roe_ttm`、90 只
具备 `cash_conversion_ttm`，杠杆覆盖由申报负债可得的 69 只扩展为 91 只，
其中 22 只清楚标记为推导值。本阶段只完善数据层和覆盖报告，不直接将质量
因子接入策略或 paper 监控。

同一完整股票池的日常报告刷新会复用已经生成的
`.cache/fundamentals/sec_facts.parquet`。解析规则变化后可从原始 SEC
缓存重新标准化而不重新联网：

```bash
make fundamentals-sec ARGS="--rebuild-facts"
```

需要向 SEC 刷新原始申报数据时，再设置 `SEC_USER_AGENT` 并使用
`ARGS="--refresh"`。

## 其他脚本

- `scripts/alpaca_paper_executor.py`：读取 `signals/*.json` 下纸面单（需环境变量中的 Alpaca Paper Key）
- `scripts/trade_v2.py`：新版纸面执行入口，支持 dry-run、kill-switch 和统一配置
- `scripts/build_sec_fundamentals.py`：缓存 SEC filings facts，生成 point-in-time 质量研究数据
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

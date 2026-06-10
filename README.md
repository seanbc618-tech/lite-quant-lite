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
| `make quality-satellite` | 用 TTM 质量层运行独立月度九仓卫星研究报告（不进入 paper） |
| `make monitor-quality-satellite` | 刷新 LightGBM 同期基线并运行质量候选双 benchmark 压力报告 |
| `make quality-trend-defense` | 为 `reported_only` 运行 SPY/QQQ 长期趋势现金防守研究，并输出 LightGBM 只读对照 |
| `make sweep-modern ARGS="--cost-scenarios base"` | 跑现代 liquid100 参数矩阵，默认 `topk=10/15/20`、`n_drop=1/2/3` |
| `make qrun-modern-alpha360` | 跑现代 liquid100 的 LightGBM + Alpha360 对照 |
| `make qrun-modern-xgb` | 跑现代 liquid100 的 XGBoost + Alpha158 对照 |
| `make qrun-modern-low` | 跑现代 liquid100 的低换手候选（Alpha158，`topk=15/n_drop=1/hold_thresh=3`） |
| `make monitor-modern-low` | 按最新可评估交易日运行低换手候选的 `SPY/QQQ` 滚动压力报告 |
| `make test` | 运行项目维护测试 |
| `make daily-pipeline` | 刷新 modern CSV/provider 并执行带新鲜度告警的健康检查 |
| `make install-launchd` | 安装工作日 18:30 自动跑 `daily-pipeline` 的 launchd 任务 |
| `make paper-dry-v2` | 新版交易执行层 dry-run，不触发真实下单 |
| `make paper-dry-modern-low` | 刷新低换手候选最新组合并仅做受保护的 dry-run 观察 |
| `make paper-dry-quality-satellite` | 仅将 `reported_only` 质量候选导出为受保护的 dry-run 观察单 |
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

完成 TTM 覆盖验收后，可运行独立的质量卫星研究试验：

```bash
make quality-satellite
```

该试验每月仅使用前一交易日已可见的 SEC 快照，按 `roe_ttm`、TTM 现金
转换率和杠杆排名选择最多 9 只等权股票，并分别评估含推导杠杆和仅申报
杠杆两种版本。报告写入
`.cache/reports/quality_satellite_candidate_latest.md`，最新持仓审计表写入
`.cache/quality_satellite/latest_holdings.parquet`。它是独立研究报告，
不会生成 paper 订单或改变现有 LightGBM 监控。报告的比较窗口会读取现有
LightGBM monitor 的安全截止日，并明确列出 provider 中 benchmark 缺价
及与 Qlib 一致的处理口径。

当前通过压力门槛的两种质量变体中，持续观察主候选为
`reported_only`：它只使用 SEC 直接申报的杠杆来源，不依赖推导负债值。
运行 `make monitor-quality-satellite` 会先刷新同一 modern provider 截止
日上的 LightGBM 对照，再将质量报告写入
`.cache/reports/quality_satellite_monitor_latest.md`；该流程不会联网刷新
SEC 数据。需要纳入新申报时，应先显式运行 `make fundamentals-sec`。

运行 `make paper-dry-quality-satellite` 时，系统只在最新质量报告仍为
`PASS`、`reported_only` 持仓不超过 9 只且杠杆来源全部为直接申报时，
生成 `.cache/signals/quality_reported_only_candidate_preview.json`，随后
交由 `trade_v2.py --dry-run` 读取。该预览带有 `dry_run_only` 防护，不会
更改 LightGBM 候选输出，也不能用于下单。完整的策略解释与停止观察条件见
`docs/superpowers/specs/2026-05-26-quality-satellite-observation-design.md`。

质量候选的防守层研究入口为 `make quality-trend-defense`。它使用前一已
完成交易日的 `SPY` 与 `QQQ` 相对 200 日均线状态，将
`reported_only` 风险暴露映射为 `100% / 50% / 0%`，其余资金按现金
处理；输出写入 `.cache/reports/quality_trend_defense_latest.md` 和
`.cache/quality_trend_defense/daily_states.parquet`。该命令也报告同一
防守规则对 LightGBM 历史收益的研究对照，但不会创建新的 paper 预览，
也不会覆盖已有质量观察单。

为检查硬现金防守是否过度压低相对收益，可显式运行温和研究 profile：
`make quality-trend-defense DEFENSE_ARGS="--profile gentle --report .cache/reports/quality_trend_defense_gentle_latest.md --states-output .cache/quality_trend_defense/gentle_daily_states.parquet"`。
该 profile 将可计算的正常市场状态映射为 `100% / 75% / 50%`，但缺失
趋势信号时仍失败关闭为 `0%` 暴露；温和版报告同样不生成 paper 输出。

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
- `scripts/trade_v2.py`：新版纸面执行入口，支持 dry-run、kill-switch、再平衡（`rebalance` + `target_weights`）和统一配置
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

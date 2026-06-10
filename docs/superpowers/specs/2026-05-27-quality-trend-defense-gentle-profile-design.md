# Quality Trend Defense Gentle Profile Design

## 决策

上一轮 `SPY` / `QQQ` SMA(200) 防守覆盖层已经证明能够降低
`reported_only` 的绝对最大回撤，但 `100% / 50% / 0%` 的仓位收缩导致
QQQ 超额收益与相对回撤门槛失败。本轮只调整风险暴露幅度，不改变趋势
信号、质量选股、交易成本、晋级门槛或 paper 隔离边界。

采用一个新增的 `gentle` 研究 profile：

| 趋势状态 | 原 `hard` profile | 新 `gentle` profile |
| --- | ---: | ---: |
| risk_on: 两指数均在均线之上 | 100% | 100% |
| defensive: 仅一个指数通过 | 50% | 75% |
| cash: 两指数均未通过 | 0% | 50% |

若用于生成信号的历史窗口或前一日 ETF 收盘价缺失，无论 profile 为何，
仍强制暴露为 `0%` 并写入审计记录。这是数据失败关闭，不属于正常的
`cash` 市场状态减仓。

## 试验边界

- 原 `hard` 行为保持为默认值，以便历史报告可以复现。
- 新 `gentle` 通过命令参数选择，报告明确记录 profile 和暴露映射。
- 温和版写入独立的报告与日状态产物，不覆盖原硬防守报告。
- 报告仍仅保护 `reported_only`；LightGBM 仍为只读研究对照。
- 温和版仍使用原有晋级门槛，通过也仅代表可以设计独立的 paper-dry
  观察步骤，不会在本轮创建信号文件或订单路径。
- 本轮不同时加入连续确认天数、不同均线窗口或参数搜索，避免无法判断
  改善来源。

## 接口与产物

研究脚本增加 `--profile {hard,gentle}`，默认 `hard`。温和试验运行：

```bash
make quality-trend-defense DEFENSE_ARGS="--profile gentle --report .cache/reports/quality_trend_defense_gentle_latest.md --states-output .cache/quality_trend_defense/gentle_daily_states.parquet"
```

温和版产物：

```text
.cache/reports/quality_trend_defense_gentle_latest.md
.cache/quality_trend_defense/gentle_daily_states.parquet
```

## 验证

自动化测试应证明：

- `hard` profile 继续得到现有 `100% / 50% / 0%` 行为；
- `gentle` 只把可计算趋势状态映射成 `100% / 75% / 50%`；
- `gentle` 中的缺价日期仍强制为 `0%` 并保留原因；
- 报告显示实际 profile 及对应映射；
- CLI 可运行温和 profile，而 Make 入口仍不创建防守版 paper 目标。

完成后运行全量测试与一次真实 `gentle` 链路。只有温和版在同一数据截止
日通过既有门槛，才能进入下一轮独立 paper 观察设计。

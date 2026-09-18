# 融合模型容量调参：2022—2024 开发窗口

用户在覆盖诊断之后授权有限调参、模拟流程、提交和推送；确认没有券商，仅用原 2022—2024 开发验证窗口。本轮不使用 2025—2026 评价模型，不产生真实订单。

使用 EA/PDD 修复后的质量输入，价格表达式、同样本消融、前一交易日匹配、标签和边界过滤不变。预先固定三个容量设置：depth4/leaves15、depth3/leaves7、depth2/leaves3；均为 100 树、min_child_samples=100、学习率 0.03、L1=1、L2=10。随机种子 20260525。每组比较价格与融合，合计 18 次拟合；不看结果继续扩搜。

| 参数组 | 融合 IC 2022 | 融合 IC 2023 | 融合 IC 2024 | 原门槛 |
| --- | ---: | ---: | ---: | --- |
| depth4/leaves15 | 0.02757 | -0.05044 | -0.02679 | FAIL |
| depth3/leaves7 | 0.02908 | -0.05307 | -0.01433 | FAIL |
| depth2/leaves3 | 0.02493 | -0.04569 | -0.04195 | FAIL |

全部 18 项模型/年度 MSE 都高于零预测基线。减小容量没有让任何配置通过原标准；没有选出获准进入模拟策略的配置。首折仍只有 2,304 行、36 个交易日。本轮是已看过开发区间的探索，不是独立 OOS 验证。

本地模拟流程使用仓库既有默认预览预算 1,000 美元、空持仓、不连接券商。因全部 FAIL，输出 `BLOCKED_RESEARCH_GATE` 和空订单数组；现有 `process_signals(client=None, dry_run=True)` 拒绝空订单，返回 1，符合其“信号文件中没有订单”约束。**策略订单零笔、券商提交零笔、成交零笔**；这不是一次已成交的模拟交易，不虚构买卖标的，也不修改执行器把拒绝包装为成功。

复现（已有目录会拒绝覆盖，重跑需指定新的输出目录）：

```sh
MPLCONFIGDIR=/private/tmp/mplcache PYTHONPATH=src /Volumes/数据分区/美股自动化交易/.venv/bin/python scripts/screen_fusion_capacity.py --output .cache/reports/fusion_capacity_20260919
```

依赖前一诊断的 `eligibility.parquet`、`corrected_eligibility.parquet` 和 manifest。新输出目录保存运行前协议、输入哈希、18 项指标与保留无效 null 的验证预测。原研究文件不覆盖，生产参数不修改。小型结果副本保存于 `docs/fusion-capacity-results-20260919.json`；本地空订单及执行状态在 `.cache/reports/fusion_capacity_20260919/`。

验证：18 项指标齐全；预测键唯一；有效预测的标签端点均在各自年度内；无效格保留 null。SEC 与交易执行器相关现有测试共 31 项通过，`git diff --check` 通过。仅有既有 websockets 弃用警告。前一诊断文档中的“未调参/未提交”描述的是前一轮交付时点；本轮授权与运行以本文为准。

# Point-in-Time Data & Portfolio Lab

[English](README.md) · 中文

**离线财务数据、研究边界验证与组合会计**

## 项目问题

研究结果之前，如何核实每个样本当时真的可用、标签没有越过训练边界、缺口
没有被隐藏？这个候选从现有美股研究代码中复用数据处理与会计模块，提供
合成输入、完整输出和可独立执行的检查。它不包含私人选股策略或真实行情。

## 设计选择

| 层次 | 实现及复用 | 可检查的证据 |
|---|---|---|
| 数据结构 | 原样复用财报规范化、TTM 与 as-of 快照模块 | 标签优先级、披露/修订来源、字段级缺项 |
| 数据覆盖 | 选取原日历/股票池诊断函数 | 完整 2 × 12 网格，区分未披露与缺口 |
| 研究验证 | 从原诊断抽取通用标签终点规则 | 边界 purge、未来修订前缀不变性、故意泄漏负对照 |
| 组合会计 | 原再平衡函数与冻结 v1 示例 | 成本、现金恒等式、亏损及 null 场景 |

不增加模型训练框架。研究演示复用已有 NumPy/pandas；原组合演示继续仅需
标准库。两个案例各有运行前写下的协议：[研究协议](RESEARCH_PROTOCOL.md)、
[组合协议](PROTOCOL.md)。两者不拼接成声称有效的投资策略。

## 可核验的工程证据

- [完整研究报告](reports/RESEARCH_REPORT.md)：25 条规范事实、24 个信息单元、20 个边界审计单元，保留所有缺项和排除理由。
- [完整组合报告](reports/REPORT.md)：保留平价计费亏损、下跌亏损、整组缺失，不选择好看的结果。
- [验证记录](reports/VALIDATION.md)：22 个继承/选取测试、重复输出、独立环境和白名单检查。
- [历史研究审阅](reports/HISTORICAL_REVIEW.md)：模型筛选失败与历史数据限制仍直接可见。
- [展示复审](reports/PORTFOLIO_REVIEW.md)：为什么补充这些模块、哪些能力没有纳入，以及仍然不足之处。

## 复现方法

完整研究演示验证环境为 Python 3.11.8。只运行组合演示可跳过安装步骤。
首次安装依赖需联网或自行提供合法离线 wheel；所有演示运行均不联网。

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-research.txt -r requirements-dev.txt
.venv/bin/python -B research_demo.py
.venv/bin/python -B verify_research.py
.venv/bin/python -B verify.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p no:cacheprovider -q
.venv/bin/python -B release_check.py
```

从候选目录运行。报告命令只向 stdout 输出，不覆盖冻结 JSON。`verify_research.py`
禁用 Python 用户环境路径，并阻止 Python 审计钩子能观察到的网络调用；这不是
操作系统沙箱。依赖留在自己的虚拟环境中，不加载父仓库代码。

按明确白名单导出到一个不存在的新目录，不复制 Git 历史：

```bash
python3 -B release_check.py --export /tmp/financial-lab-review
```

## 实证结论与限制

这是研究工程案例，**没有市场预测有效性结论**。最终只有 4 个单元同时满足
合成财务数据可用性与边界条件；没有为增加样本而缩宇宙或填补缺项。原数据层
不等于完整历史修订审计，财报日级时间戳不证明盘中可用性，purge 也不等于
完整 walk-forward 或 embargo。详见完整报告中的限制。

原再平衡函数亦有输入校验和全现金目标限制；模拟即时成交不证明可执行性。
历史市场实验不在此包中重现，其失败与缺口不因工程测试通过而消失。

## 来源和开发方式

[来源清单](SOURCES.md)区分原样复用、按定义选取、适配代码与新增教学代码；
[公开白名单](PUBLIC_FILES.txt)定义发布候选范围。代码采用 [MIT](LICENSE)，
第三方包保留各自许可，不打包；合成材料是新写示例，没有从外部数据许可推导权限。

本次候选整理、演示和文档由 Codex 辅助完成。未核实历史开发中的个人职责、
独立开发比例或原创性，不代申请人作这些声明。当前工作树按公开白名单整理；仓库通过普通提交保留旧历史。历史文件仍可访问，
不声称已经脱敏；本轮检查只覆盖当前白名单文件。

# Portfolio scope review / 展示复审

## Assessment

The original reconciliation-only candidate was reproducible but narrow. The
extension makes existing financial-data semantics and validation methods
executable: normalization, filing-aware snapshots, TTM provenance, complete-grid
coverage, and label-boundary auditing. This is stronger evidence of engineering
judgment than adding models or selecting favorable performance charts.

The reuse boundary is explicit: unchanged financial-data module/tests; selected
unchanged provider helpers/tests; an adapted generic endpoint audit. Training,
strategy configurations, data downloads and execution remain excluded. The
candidate demonstrates methods on synthetic inputs, not predictive validity,
statistical significance, production readiness or admissions outcomes.

---

## 判断

上一版诚实且容易复现，但只展示一个再平衡函数，容易被理解为小型编程练习。
它没有把原工程真正有价值的两部分呈现出来：财务数据的时间语义，以及研究
样本的可用性与边界审计。历史失败报告有方法意识，但仅有叙述不足以让读者
亲手核验方法。本轮补充可执行证据，而不以模型数量或收益数字填充首页。

这是对作品表达与证据密度的判断，不是院校录取概率或招生偏好的事实声明。

## 安全复用选择

| 原有能力 | 选择 | 公开范围与理由 |
|---|---|---|
| 财报规范化及 as-of 快照 | 原样复用 fundamentals.py、15 个既有测试 | 标准字段/单位、披露日期、TTM 算术与来源标记；没有选股门槛、模型参数或数据缓存 |
| 日历和股票池诊断 | 原样选取 6 个定义、2 个测试正文 | 只读本地合成 provider 文本；不包含 Qlib 初始化、YAML 配置或默认私人路径 |
| 标签终点 purge | 将已有诊断循环改为通用函数 | 去除模型、数据路径与调参；新增输入校验和逐单元状态，明确不是原样复制 |
| 再平衡与成本会计 | 保留 v1 | 原规则、协议、结果冻结不动，避免为了新展示重选样本 |
| 数据下载、模型训练、扫参、执行 | 不纳入 | 依赖受限/未经许可复用的数据，或会携带策略参数与账户接口；对当前离线证据不是必要项 |

## 更值得展示的具体能力

1. 把 SEC-shaped 原始事实变成带 tag、单位、申报编号和披露日期的规范表。
2. 区分报告期、披露日、信息日、信号日；保留修订，防止向过去回填。
3. 解释 TTM 桥接及不完整输入，区分已申报比率与推导值，而不是默默补齐。
4. 以完整股票池/日期网格报告可用性，区分尚未披露、已声明合成缺口和跨界标签。
5. 用前缀不变性和故意泄漏的负对照核验时间规则，再用边界审计决定研究资格。
6. 用独立环境、固定输出和来源哈希把上述陈述变成可审阅证据。

## 仍需克制

这是一个数据工程与研究验证作品，不是完整量化研究论文。合成案例不能证明
金融预测能力、统计显著性或现实数据适用性。未新增机器学习排行榜、收益宣传、
生产化框架或外部数据包。申请人可展示代码与方法，但个人实际职责和理解程度
仍需本人真实说明；没有代写未经核实的个人贡献结论。

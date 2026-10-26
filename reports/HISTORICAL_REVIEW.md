# Historical research review / 历史研究审阅

This is the complete public-safe review prepared for this candidate. It is a new
narrative, not a reproduction of private reports, model parameters, market data,
predictions or trading records. The original reports remain unchanged locally.
Source-file hashes and exact local evidence locations are in the maintainer's
local audit, outside the public export. These conclusions were checked against
existing code and JSON artifacts, not independently rerun market experiments.

## Observed capability versus evidence

The source repository contains data-provider construction, SEC filing-date-aware
normalization, model workflows, boundary-purged diagnostics, rolling evaluation,
portfolio previews and broker-connected execution code. Their existence does
not establish correct operation in all environments or production readiness.
The public candidate now exposes generic reconciliation, filing-data
transformations, selected provider helpers and an adapted label-boundary audit,
with synthetic examples and inherited tests. No claim is made to have invented Qlib or its models.

## Negative findings retained

1. A historical Alpha360 candidate was rejected for paper progression. Recorded
   concerns included coarse/tied scores, unfavorable benchmark-relative results,
   and a requested position count not being a hard holdings cap. Those are
   model and execution-design limitations, not evidence of reliable excess returns.
2. Subsequent purged expanding-window screening compared two learners over three
   development years. Neither met its recorded advancement rule. Inspection of
   all six saved diagnostics confirms that the final-round errors did not beat
   the zero-prediction baseline in any of those folds. Mixed rank-correlation
   signs prevent presenting the screening as stable predictive evidence.
3. Price/quality fusion screening recorded FAIL. Inspection of all nine saved
   model/year rows confirms error above the zero baseline; fusion did not
   consistently repair the price-only model. Simultaneous feature and filing
   coverage left limited early training data. This does not establish that
   fundamental modeling in general is ineffective.

历史候选被拒绝；后续两个学习器的筛选也未通过；价格与财务信息融合未通过。
这些失败保留在首页链接的报告中，不以展示合成示例取代或隐藏。没有在本轮
重跑模型、挑选更好区间或替换失败结果。

## Research limitations

- Previously inspected market test windows are not untouched future holdouts.
- Current-universe construction can introduce survivorship/selection bias.
- Filing-date checks are not a complete audit of vendor revisions or intraday
  availability. Boundary purging is present in diagnostic code, not universally
  proven across all historical workflows.
- Complete-case model comparisons are conditional on coverage. Historical missing
  inputs were not all traced to source absence; they must not be retrospectively
  renamed INVALID_DECLARED_GAP. The frozen panel and its statuses remain intact.
- Overlapping return labels are not independent observations. Screening rules do
  not substitute for uncertainty estimates, independent OOS validation or costs.
- Pre-existing documents describe rules as declared before screening; this review
  cannot independently authenticate that chronology. They are historical
  development records, not externally registered prospective experiments.
- Historical plans and README claims are not acceptance evidence. A configured
  workflow or an existing CI file does not prove a successful scheduled run.
- No broker receipts, actual fills, economic capacity, live PnL or operational
  safety were verified in this preparation.

The standalone package therefore makes a narrow reproducibility claim about
its own synthetic engineering demonstration. It makes no historical market
replication, profitability, prospective validation or personal contribution claim.

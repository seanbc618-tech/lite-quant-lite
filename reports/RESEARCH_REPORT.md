# Financial-data and validation demonstration / 财务数据与验证演示

[Protocol declared before this demo](../RESEARCH_PROTOCOL.md) ·
[Full machine-readable report](research-results.json) ·
[Authored inputs](../examples/research-fixture.json) ·
[Reuse provenance](../SOURCES.md)

## Question and design

Can inherited data transformations and research-boundary logic be inspected
without market data, private strategy settings or accounts? The demo connects
synthetic provider metadata → canonical filing facts → filing-visible snapshots
→ prior-session information panel → segment eligibility audit. It deliberately
does not turn the financial metrics into a trading strategy. The independent
[portfolio accounting exercise](REPORT.md) remains unchanged.

```mermaid
flowchart LR
  A[Synthetic filings and session list] --> B[Normalize tags and units]
  B --> C[As-of snapshots and TTM provenance]
  C --> D[Prior-session availability on full grid]
  A --> E[Label endpoint and split audit]
  D --> F[Retained cells with eligibility and reasons]
  E --> F
```

## Complete result

| Evidence | Observed result |
|---|---|
| Provider | 12 authored sessions, 2 fictional issuers |
| Normalized facts | 25 rows, including original and amended disclosures |
| Full issuer/session panel | 24 cells retained |
| Available complete cells | 10 |
| Not yet disclosed | 4, status NOT_YET_AVAILABLE |
| Declared synthetic source-gap cells | 10, status INVALID_DECLARED_GAP, usable metrics null |
| Train + validation audit | 20 cells retained; 8 cross-boundary cells, 12 within boundary |
| Combined eligible cells | 4; no model fitted or scored |
| Reserved sessions | Last 2, no label scores or economic evaluation |
| Deliberately leaky control | Latest value 120 incorrectly assigned to an early date whose expected value is 100; detected |

Status counts refer to different tables and should not be added together. A
boundary-valid cell can still lack financial data. All original cells, observed
partial values and separate reasons are retained in JSON; invalid cells have null
usable metrics/eligibility. No overall performance average is calculated.

中文解读：标签未跨界不代表数据可用。两个维度分别记录，最终只有 4 个单元
符合本演示的数据与边界条件；样本少不会通过缩减股票池或填补数据来隐藏。
这是预设案例的正确结果，不是模型训练成果。

## Temporal evidence

- The first complete issuer's FY income is 100. The quarter bridges to
  `100 + 70 - 60 = 110`; its amendment bridges to `100 + 80 - 60 = 120`.
- A signal uses the previous authored session's snapshot. An amendment filed on
  2025-08-13 therefore first appears for a signal on 2025-08-14.
- Removing that amendment leaves all earlier signal rows byte-equivalent as
  Python data structures. A deliberately wrong latest-filing join fails the
  independently specified early-date expectation.
- The conflicting revenue fallback tag does not overwrite the primary FY value.
- For t+1 entry / t+2 exit, the last two signal dates per segment cross its
  boundary. Eight issuer/date cells are retained but ineligible. Unknown sample
  dates and duplicate/out-of-order calendars raise errors; missing calendar
  endpoints get INVALID_CALENDAR_COVERAGE, not a source-gap declaration.

## Limitations and negative findings

The inherited module's docstring describes leakage avoidance; that is not proof
against all leakage. Its filed-date semantics are daily, not exact release-time
semantics. The wrapper's next-session policy is conservative on this fixture,
but does not audit time zones, vendor revision history or fiscal-period anomalies.
The source TTM bridge is heuristic: a later amendment to an old period can require
more careful period selection than this case tests. Its aggregate `ttm_source`
can exist when individual fields are absent; always inspect field-level nulls.

The generic calendar parser assumes sorted, valid provider text. The new endpoint
audit validates its own calendar, which does not make the original parser a
complete data-quality validator. Provider metadata alone cannot establish actual
price coverage, delisting coverage or survivorship freedom.

Synthetic SEC-shaped records are not downloaded SEC data. The session list is
not an exchange calendar. Selected tests include public-style issuer identifiers
with artificial values; they are not filings or account records. No source-gap
claim is made about a real provider. No embargo, fitted estimator, significance
test, empirical OOS result, capacity estimate or live execution is supplied.
The reserved dates are a demonstration of partition boundaries, not a claim of
an independently untouched market holdout.

**Engineering validation is separate from economic effectiveness.** Historical
negative research remains visible in [HISTORICAL_REVIEW.md](HISTORICAL_REVIEW.md).

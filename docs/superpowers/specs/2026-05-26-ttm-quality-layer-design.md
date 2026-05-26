# TTM Quality Layer Design

## Approved Direction

Extend the SEC-first fundamentals warehouse with comparable quality
measurements before adding a quality trading workflow. The user approved the
auditable bridge method:

```text
TTM = previous full fiscal year + current year-to-date - prior-year comparable year-to-date
```

The first implementation operates on the existing current `liquid100`
investable universe of 92 equities and continues to keep all derived data
under ignored `.cache/` paths.

## Why This Layer Is Required

The SEC warehouse now covers all 92 equities, but the latest visible filings
do not share the same reported period: the current snapshot contains `Q1`,
`Q2`, `Q3`, and `FY` facts. Raw reported net-income and cash-flow ratios are
therefore audit measurements, not fair cross-sectional strategy inputs.

Direct `Liabilities / Assets` also has lower coverage than the other quality
components. Some issuers disclose `Assets` and `StockholdersEquity` in the
canonical facts while omitting the preferred liabilities tag.

## TTM Calculation Rules

The warehouse adds TTM fields for `revenue`, `net_income`, and
`operating_cash_flow`:

- A visible `FY` filing uses its reported annual value directly and records
  source `reported_fy`.
- A visible `Q1`, `Q2`, or `Q3` filing bridges to TTM only when all of the
  following are visible no later than that filing date:
  - the current cumulative YTD value selected for that filing period;
  - the latest prior full-year value;
  - the prior-year comparable YTD value for the same fiscal period.
- For comparative rows within a filing, the longest duration ending on the
  required period end wins, preventing a standalone quarter from being mixed
  with cumulative cash flow.
- A missing bridge component produces a null value for that TTM field; when
  any TTM field is produced, `ttm_source` still records the construction
  method. Source `missing` means no TTM duration metric could be produced.
  The layer does not borrow future filings or silently substitute raw
  quarterly data.

TTM output fields:

- `revenue_ttm`
- `net_income_ttm`
- `operating_cash_flow_ttm`
- `roe_ttm = net_income_ttm / stockholders_equity`
- `cash_conversion_ttm = operating_cash_flow_ttm / net_income_ttm`
- `ttm_source`

## Leverage Fallback Rules

The daily snapshot keeps `debt_to_assets`, but records exactly how it was
obtained:

1. If the selected reporting period contains `total_liabilities` and
   `total_assets`, compute the ratio directly with source `reported`.
2. Otherwise, if it contains `total_assets` and `stockholders_equity`, compute
   `(total_assets - stockholders_equity) / total_assets` with source
   `derived_assets_minus_equity`.
3. Otherwise, retain a null ratio with source `missing`.

The derived value is an explicit research fallback rather than an invisible
rewrite of SEC facts.

## Output And Reporting

The existing `.cache/fundamentals/quality_daily.parquet` gains the TTM and
leverage-source fields. The Markdown report gains:

- TTM metric coverage by symbol;
- reported versus derived leverage coverage;
- missing TTM or leverage symbols;
- a clear statement that strategy promotion remains blocked until coverage is
  accepted.

Routine rebuilds continue to reuse normalized `sec_facts.parquet`; raw SEC
cache remains the auditable source for `--rebuild-facts`.

## Validation Gates

1. Synthetic tests cover FY-direct TTM, quarterly bridge TTM, missing bridge
   components, no future leakage, and reported/derived/missing leverage
   sources.
2. Existing SEC normalization, foreign issuer, and cache-reuse tests remain
   green.
3. A cache-only full-universe rebuild reports real TTM and leverage coverage
   for all 92 stocks.
4. No Qlib or paper workflow consumes TTM data in this milestone; the report
   informs the subsequent strategy design.

# SEC Fundamentals Warehouse Design

## Approved Direction

Build a point-in-time fundamentals layer before attempting a true quality
strategy. The initial scope is the current modern `liquid100` investable
equity universe, excluding the `SPY` and `QQQ` benchmark ETFs. With the
current provider this is approximately 92 ordinary equities.

The first milestone is data engineering and data-quality visibility. It does
not promote a new trading workflow or alter existing paper monitoring.

## Why SEC First

The modern Qlib provider currently contains price and volume fields only.
A strategy labelled as quality needs historical financial statements that
were available at each decision date, rather than today's fundamentals
backfilled into older dates.

SEC EDGAR provides public filing data with filing dates, accession numbers,
forms, and XBRL company facts. The warehouse therefore uses SEC submissions
and company facts as its primary historical source. The existing ValueInvest
probe remains useful for calculation experiments, but its Yahoo-backed fetcher
is not treated as point-in-time strategy data.

## Data Flow

```text
liquid100 instruments - SPY/QQQ
        |
        v
ticker -> CIK mapping
        |
        v
SEC submissions + companyfacts raw JSON cache
        |
        v
canonical facts with tag fallback and filing dates
        |
        v
point-in-time daily quality snapshots
        |
        v
coverage report and later quality-strategy research
```

## Stored Outputs

All downloaded and derived data stays under ignored `.cache/` paths:

- `.cache/sec/raw/<cik>/companyfacts.json`
- `.cache/sec/raw/<cik>/submissions.json`
- `.cache/fundamentals/sec_facts.parquet`
- `.cache/fundamentals/quality_daily.parquet`
- `.cache/reports/fundamentals_quality_latest.md`

Only code, tests, command wiring, and this design record belong in Git.

## Canonical Fields

The first normalizer retains both the canonical field name and selected SEC
taxonomy tag so missing/fallback coverage can be audited.

| Canonical field | Preferred XBRL tags |
| --- | --- |
| `revenue` | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` |
| `net_income` | `NetIncomeLoss`, `ProfitLoss` |
| `operating_cash_flow` | `NetCashProvidedByUsedInOperatingActivities` |
| `total_assets` | `Assets` |
| `total_liabilities` | `Liabilities` |
| `stockholders_equity` | `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` |
| `shares_outstanding` | `EntityCommonStockSharesOutstanding`, `CommonStockSharesOutstanding` |

Each normalized observation retains:
`ticker`, `cik`, `field`, `value`, `unit`, `form`, `fiscal_period`,
`period_end`, `filed_date`, `accession_number`, and `tag`.

## Point-In-Time Rules

1. A `10-Q`, `10-K`, `10-Q/A`, or `10-K/A` fact becomes visible only on its
   SEC `filed_date`.
2. An amendment or restatement does not rewrite history. It affects daily
   snapshots only from its later filing date forward.
3. When multiple accepted tags represent the same canonical field and filing,
   the documented priority order wins and the selected tag remains visible in
   the facts table.
4. A quality snapshot selects the latest visible filing-level measurement for
   each stock and trading day. It does not silently mix future facts into an
   earlier session.
5. The first universe is today's maintained `liquid100` equity set. Research
   using it has survivorship bias until historical membership is later added.

## First Quality Measurements

The first daily snapshot exposes transparent measurements instead of a
premature stock-ranking model:

- `roe = net_income / stockholders_equity`
- `cash_conversion = operating_cash_flow / net_income`
- `debt_to_assets = total_liabilities / total_assets`
- completeness flags and selected filing metadata

Reported income and operating-cash-flow periods can differ across issuers at a
shared trading date (`Q1`, `Q2`, or `Q3`). These ratios therefore remain
coverage/audit measurements in this milestone, not directly comparable
cross-sectional quality ranks. Revenue growth stability, trailing-twelve-month
normalization, and a combined low-volatility quality selection belong to the
next milestone after actual SEC coverage is measured.

## Retrieval And Safety

- SEC HTTP requests must carry a configured contact-bearing `User-Agent`.
  The CLI accepts `SEC_USER_AGENT` or an explicit command argument.
- Raw responses are cached and reused by default; refreshing is explicit.
- An unchanged complete universe reuses normalized `sec_facts.parquet` for
  routine snapshot/report refreshes; `--rebuild-facts` deliberately reparses
  cached raw filings after normalization logic changes.
- A failed issuer is reported as missing coverage rather than corrupting or
  blocking all successfully downloaded issuers.
- A small-symbol run is the live validation gate before downloading the full
  approximate 92-name universe.

## Acceptance Criteria

1. Unit tests prove ticker-to-CIK conversion, tag fallback, filed-date
   visibility, amendment handling, and quality-ratio calculation.
2. A script can build Parquet fact/snapshot files and a Markdown coverage
   report from cached fixture-shaped SEC responses.
3. A Make target and README command expose the workflow without committing raw
   filings or outputs.
4. A live three-symbol smoke fetch is run only after a compliant SEC
   `User-Agent` contact string is supplied.

## Full-Universe Validation Outcome

- The current investable universe contains `92` equities after excluding
  `SPY` and `QQQ`.
- Initial coverage omitted seven foreign issuers. Root cause was schema/form
  coverage, not failed downloads: `ASML`, `BIDU`, `JD`, `NTES`, `PDD`, and
  `TCOM` report through `20-F` / `6-K`, while `AZN` uses `ifrs-full`.
- Adding foreign-issuer forms, IFRS tag mappings, and a single-currency
  selection rule brought normalized coverage to `92/92`: `101232` fact rows
  and `127704` daily snapshot rows.
- Routine cache-only report rebuild was reduced from approximately `239s` to
  `1.20s` by reusing normalized facts and using vectorized as-of snapshots.
- Coverage is sufficient to begin a TTM-quality layer, but not to rank raw
  quarterly ratios directly. At the latest sample date, fiscal periods span
  `Q1`, `Q2`, `Q3`, and `FY`; direct debt-to-assets coverage also needs a
  documented derived fallback for issuers that publish assets and equity
  without a standalone liabilities fact.

# Independent Quality Satellite Candidate Design

## Decision

Implement a new, independent quality satellite research candidate before
attempting to blend fundamentals with the existing LightGBM workflow. The
candidate measures whether point-in-time SEC quality data contributes a useful
signal on its own.

It is a research candidate only. This milestone does not place orders or add
the candidate to continuous paper monitoring.

## Objective And Boundaries

The current verified candidate is a low-turnover LightGBM Alpha158 satellite.
It has useful SPY behavior but weaker recent QQQ behavior. The new candidate
is intentionally slower-moving: it uses audited TTM fundamental fields and
monthly portfolio formation rather than daily model predictions.

The experiment uses:

- the current `liquid100` investable equity universe, excluding `SPY` and
  `QQQ`, currently covering 92 equities;
- `.cache/fundamentals/quality_daily.parquet` as the point-in-time quality
  snapshot source;
- the modern Qlib provider for daily stock and benchmark closing prices;
- `SPY` and `QQQ` as evaluation benchmarks, never as satellite selections.

The first experiment must not modify the LightGBM monitor, paper-preview
targets, or Qlib feature store.

## Portfolio Construction

The quality satellite holds at most nine equities. This reserves one future
slot for a possible passive `QQQ` core while respecting the existing
ten-position execution limit.

Portfolio rules:

1. Rebalance monthly on the first available trading session of each month.
2. For a rebalance on session `t`, rank only quality snapshots visible by the
   preceding trading session. Facts becoming visible on `t` cannot affect a
   position traded on `t`.
3. Eligible securities require non-null `roe_ttm`, `cash_conversion_ttm`, and
   `debt_to_assets`, plus strictly positive `net_income_ttm`.
4. Select the nine highest-scoring eligible equities, or fewer when fewer are
   eligible.
5. Weight selected equities equally. Any unallocated portion remains cash.
6. Ties are broken by ticker in ascending order for deterministic results.

Monthly rebalancing is part of the strategy definition, not merely a speed
optimization: the intended quality signal should respond slowly to filing
changes and limit turnover.

## Quality Score

The base score is computed independently for each rebalance cross-section:

1. Winsorize `roe_ttm`, `cash_conversion_ttm`, and `debt_to_assets` at the
   5th and 95th percentiles among eligible securities.
2. Convert each winsorized metric to a cross-sectional percentile rank:
   higher `roe_ttm` and `cash_conversion_ttm` rank higher; lower
   `debt_to_assets` ranks higher.
3. Average the three ranks with equal weights.

The output retains the raw TTM values, leverage source, transformed ranks, and
final score for each selected holding so every selection can be audited.

## Leverage Provenance Sensitivity

The base portfolio accepts both leverage provenance values currently present
in the warehouse:

- `reported`;
- `derived_assets_minus_equity`.

A required companion run applies the identical strategy while excluding
`derived_assets_minus_equity`. The report must compare the base and
`reported-only` variants in every benchmark/window combination. Both variants
must satisfy the quantitative promotion tests below.

## Return And Cost Model

The independent research runner calculates close-to-close daily portfolio
returns using prices from the same modern provider used by existing Qlib
experiments.

- A new target portfolio takes effect on its rebalance session and earns the
  following close-to-close return, avoiding a same-close lookahead.
- Holdings drift between monthly rebalances; they are not forcibly equalized
  every day.
- Turnover is calculated from pre-trade drifted weights to new target weights.
- Transaction cost uses the established workflow rates: `0.0005` on buys and
  `0.0015` on sells. The report includes net returns after costs.
- Cash earns zero return.

This is a deterministic research backtest, not a Qlib ML run. Its output must
use clearly named local `.cache/` reports and holding artifacts rather than
mixing with the existing MLflow experiment namespace.

## Report And Comparison

The runner produces one Markdown report for:

- variants: `base` and `reported_only`;
- benchmarks: `SPY` and `QQQ`;
- windows: `full`, `63d`, `126d`, and `252d`.

For each combination, the report includes cost-adjusted annualized excess
return, maximum drawdown of excess returns, information ratio, turnover/cost
summary, latest holding count, and the percentage of latest base holdings
whose leverage was derived. It also includes an auditable latest-holdings
table with scores and provenance.

The `full` window starts at the first executable quality portfolio generated
by the runner; fixed trailing windows end on the latest safely return-bearing
provider session.

## Promotion Gate

The candidate remains research-only unless all of the following hold:

- it satisfies the nine-equity holding limit in every portfolio formation;
- against a contemporaneous LightGBM monitor, its `QQQ / 63d` after-cost
  annualized excess return improves by at least ten percentage points;
- its `QQQ / 126d` after-cost annualized excess return is no more than five
  percentage points below the LightGBM comparison;
- its full-window after-cost annualized excess return is positive against both
  `SPY` and `QQQ`, and each full-window excess-return drawdown is no more than
  five percentage points deeper than the LightGBM comparison;
- the `reported_only` variant meets those same return and drawdown tests, so
  the conclusion does not depend on derived leverage;
- all preview or later paper integrations continue to fail closed at the
  repository's position limit.

For the locally available LightGBM report dated `2026-05-22`, these rules
translate to an initial quality-candidate screen of: `QQQ / 63d` after-cost
annualized excess above `-18.72%`, `QQQ / 126d` at least `9.54%`, positive
full-window excess against both benchmarks, full-window SPY drawdown no
deeper than `-23.72%`, and full-window QQQ drawdown no deeper than `-31.27%`.
Later promotion decisions must refresh the LightGBM monitor rather than rely
on these snapshot thresholds.

Passing this gate authorizes only a later design for paper monitoring or a
`QQQ` core combination. It does not authorize order submission.

## Components And Testing

The implementation should add a focused quality-candidate module or script
alongside tests and a Make target. It should reuse existing fundamental output
and provider inputs without altering the SEC warehouse or current ML
candidate.

Tests must cover:

- preceding-session information visibility;
- score construction and deterministic top-nine selection;
- monthly rebalancing and no daily reshuffle;
- drift-aware turnover and cost deduction;
- reported-only sensitivity exclusion;
- report rendering and CLI entrypoint.

Validation then runs the real cached fundamentals and modern provider data,
generates all sixteen variant/benchmark/window result rows, and compares the
base quality satellite with the existing LightGBM evidence before any
promotion decision.

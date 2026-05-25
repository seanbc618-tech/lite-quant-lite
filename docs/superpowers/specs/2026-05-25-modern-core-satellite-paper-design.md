# Modern Core-Satellite Paper Design

## Decision

`DoubleEnsemble + Alpha158` is rejected as a replacement candidate. It
improved the recent `QQQ / 63d` weakness but lost positive medium-window
performance. The next paper-only candidate keeps the verified LightGBM
low-turnover alpha sleeve and adds a passive `QQQ` core sleeve.

## Candidate

- Core: `60%` buy-and-hold `QQQ`.
- Satellite: `40%` of the existing
  `lightgbm_alpha158_liquid100_modern_low_turnover_candidate_deterministic`
  portfolio.
- Report windows: `full`, `63d`, `126d`, `252d` against both `SPY` and
  `QQQ`.
- Return model: core and satellite begin at the configured weights and grow
  independently without daily rebalancing; each sleeve includes its modeled
  transaction costs.
- Scope: dry-run observation only. This candidate is not approved for order
  submission.

## Components

1. `scripts/evaluate_core_satellite_candidate.py` reads the newest completed
   LightGBM monitor artifacts, combines them with the `QQQ` benchmark return
   series, computes Qlib-compatible risk statistics, and writes a Markdown
   report.
2. `scripts/generate_candidate_paper_signals.py` gains optional core-sleeve
   arguments. Without those arguments it preserves the current satellite-only
   output; with them it emits one core order plus proportionally scaled
   satellite orders and allocation metadata.
3. `scripts/trade_v2.py` validates order shape and maximum notional in
   `--dry-run` mode as well as submit mode. Position-count validation remains
   connected to an actual account snapshot; dry-run logs when target symbol
   count exceeds the configured limit.
4. `Makefile` exposes monitoring and paper-dry commands for the
   core-satellite candidate. Preview budget defaults to `$1,000` so static
   default order limits can be exercised without proposing a large order.

## Promotion Gate

This candidate may remain in continuous paper observation when:

- reports continue to show positive cost-adjusted excess return in all windows
  except the known `QQQ / 63d` stress window;
- the `QQQ / 63d` loss remains materially smaller than the satellite-only
  candidate; and
- generated previews pass offline/static dry-run validation.

It must not become executable paper trading until an operator chooses live
position-count and order-size constraints using an actual Alpaca paper
account snapshot.

## Testing

- Unit-test independent sleeve aggregation and report rendering.
- Unit-test core/satellite signal generation, budget scaling, and invalid
  weights.
- Regression-test that dry-run rejects an order exceeding configured maximum
  notional.
- Run the full test suite, current monitor refresh, core-satellite report, and
  the new dry-run target.

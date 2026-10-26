# Protocol v1 — recorded before the first demo execution

Question: does the inherited reconciliation function support deterministic,
cost-aware offline accounting while retaining an explicitly missing scenario?
This is an engineering exercise, not an empirical strategy test.

Universe: SYN_A and SYN_B (fictional identifiers). Eight ordinal observations
0–7 per scenario; these are not exchange dates. Include every scenario:
flat prices, falling prices, and a declared missing cell. No downloads or random
sampling. All cells are authored for this exercise, not reconstructed market data.

Teaching rule: rebalance at each observation 0–6 to 40% per asset and 20% cash,
using current marked equity. Hold to the next observation; liquidate at observation
7. No fitting, search, training or holdout split applies. Target weights are fixed
before results; the original strategy parameters are not used.

Start equity: 1000 synthetic USD. Minimum trade notional: 1.00, using the inherited
strict greater-than comparison. Evaluate both 0 and 10 basis points per side on
actual synthetic traded notional, including final liquidation. No minimum fee,
spread, tax, slippage, lot constraint, settlement delay or interest. Fractional
units and immediate complete fills are assumptions, never broker evidence.

Compare ending equity with a cash baseline of 1000. Report total return, total
traded notional and costs, plus the full ledger. Do not annualize eight points or
calculate statistical significance. Flat prices must lose money after costs;
falling prices need not beat cash. Neither result estimates market performance.

If any required cell is absent, retain the entire scenario with status
INVALID_DECLARED_GAP, exact missing coordinates, null return/NAV/cost/turnover,
and no partial simulation. The missing scenario is an intentionally authored
fixture, not a claim about a real vendor gap. Untraced real missing data must not
be called a declared source gap. Do not reduce the universe or fill missing cells.

Acceptance: repeated output is byte-identical; accounting reconciles; sell
previews precede buys; net cash stays non-negative; inherited tests pass; all
scenario/cost combinations are present; the explicit gap remains null. Report
negative outcomes unchanged. Protocol and input hashes travel with the report.

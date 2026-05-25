# Executable Core-Satellite Position-Cap Design

## Approved Direction

The operator approved continuing with the recommended execution constraint:
keep `config.trading.max_open_positions=10` and reduce the paper candidate to
one passive `QQQ` core holding plus at most nine LightGBM satellite holdings.

## Considered Approaches

1. Truncate satellite orders only during preview export. This would satisfy the
   order-count check, but reports would still evaluate a different fifteen-name
   satellite and would therefore overstate what is actually previewed.
2. Raise `max_open_positions` above fifteen. This avoids implementation work,
   but weakens a configured execution guard before account-backed paper
   validation exists.
3. Run an explicit `topk=9` satellite workflow and use its artifacts in both
   the core-satellite report and dry-run preview. This keeps research output and
   proposed execution aligned, while retaining the current ten-position limit.

Approach 3 is selected.

## Candidate

- Core: `60%` buy-and-hold `QQQ`.
- Satellite: `40%` LightGBM + Alpha158 low-turnover workflow configured with
  `topk=9`, `n_drop=1`, and `hold_thresh=3`.
- Total target holdings: at most `10`.
- Validation windows: `full`, `63d`, `126d`, and `252d` against both `SPY`
  and `QQQ`.
- Scope: paper dry-run observation only; this does not approve order
  submission.

## Implementation

1. Add a separate Qlib workflow for the capped satellite, preserving the model,
   features, provider, costs, and deterministic strategy while giving its
   experiment a distinct name.
2. Point `monitor-modern-core-satellite` at the capped workflow and use its
   experiment base when combining returns with the passive `QQQ` core.
3. Point `paper-dry-modern-core-satellite` at the capped full-window artifact;
   its output must contain no more than ten buy targets and must retain
   `dry_run_only: true`.
4. Preserve `monitor-modern-low` and `paper-dry-modern-low` as the existing
   satellite-only observation surface.

## Acceptance

- Configuration tests prove the capped workflow uses deterministic
  `topk=9/n_drop=1/hold_thresh=3`.
- Command tests prove the core-satellite monitor and preview use the capped
  workflow and its experiment artifacts.
- A refreshed eight-window core-satellite report is produced from the capped
  satellite.
- The generated paper preview contains no more than ten buy symbols and runs
  under `trade_v2.py --dry-run` without the position-target warning.
- Full automated tests pass before commit.

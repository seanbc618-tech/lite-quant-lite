# Executable Core-Satellite Position-Cap Design

## Approved Constraint

The operator approved continuing with the recommended execution constraint:
keep `config.trading.max_open_positions=10` and reduce the paper candidate to
one passive `QQQ` core holding plus at most nine LightGBM satellite holdings.

## Validation Outcome

The proposed LightGBM core-satellite promotion is rejected for now. A normal
Qlib `topk=9` workflow is not a hard nine-position constraint: the
`topk=9/n_drop=2/hold_thresh=3` full-window artifact held up to `11`
satellite names and exported `11` total orders after adding `QQQ`. A
position-capped test workflow held the satellite sleeve to nine names, but
lost its useful benchmark behavior.

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

Approach 3 was tested and rejected as a promoted paper workflow. It remains a
useful research direction only if a later model or allocation passes both the
position limit and benchmark gates.

## Candidates Tested

- Core: `60%` buy-and-hold `QQQ`.
- Uncapped `topk=9/n_drop=1/hold_thresh=3`: executable count passed once, but
  five of eight composite stress windows were negative.
- Uncapped `topk=9/n_drop=2/hold_thresh=3`: stronger performance, but full
  artifact satellite count reached `11`, violating the ten-position total
  limit once the `QQQ` core is included.
- Hard-capped `topk=9/n_drop=2/hold_thresh=3`: satellite count stayed at nine;
  composite QQQ excess was negative in all four windows.
- Hard-capped `topk=9/n_drop=2/hold_thresh=1`: stopped after full-window probe;
  satellite excess after cost was `-13.54%` vs SPY and `-20.46%` vs QQQ.

## Implementation Outcome

1. Do not wire either capped experiment into ongoing paper monitoring.
2. Preserve the current core-satellite monitor as research-only; it is not an
   execution-approved strategy under the ten-position constraint.
3. Tighten `trade_v2.py --dry-run`: a generated target list above
   `max_open_positions` is an error, not a warning.
4. Use that failure as the gate for future capped candidate searches.

## Evidence

- The uncapped `n_drop=2` artifact contained `9` holdings on `144` sessions,
  `10` on `150`, and `11` on `51`; latest evaluable day contained `10`.
- The hard-capped `hold_thresh=3` artifact contained at most `9` holdings, but
  core-satellite QQQ annual excess after cost was `-5.82%` full,
  `-15.22%` 63d, `-3.35%` 126d, and `-3.78%` 252d.
- The preview overflow was reproduced as `11` buy orders with
  `max_open_positions=10`.

# Modern Candidate Monitoring Design

## Purpose

Promote the selected deterministic low-turnover Qlib workflow into a paper-only
observation loop. The loop must keep testing the strategy against fresh modern
provider data and both `SPY` and `QQQ`, while making its latest portfolio easy
to inspect through the existing paper dry-run executor.

## Scope

This work adds two operational entry points around
`workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml`:

1. A rolling stress report that detects the provider's latest available
   trading session and builds Qlib runs ending on the newest safely evaluable
   session for full, 63-session, 126-session, and 252-session windows, against
   both `SPY` and `QQQ`.
2. A paper dry-run preview that refreshes the candidate through that newest
   safely evaluable session, exports the latest Qlib target holdings as
   budget-scaled preview buy orders, and sends them only through
   `trade_v2.py --dry-run`.

It does not place live or paper orders and it does not interpret the candidate
as approved for execution.

## Architecture

`scripts/run_modern_candidate_monitor.py` reads the local Qlib calendar,
clones the approved candidate YAML into generated workflow files under
`.cache/`, updates only the current evaluation window and benchmark, launches
Qlib, then writes a Markdown report containing only the newest run for each
requested scenario. The canonical candidate parameters remain in the checked
in workflow. Qlib's daily simulator needs one following calendar step to
execute its final decision, so reports explicitly show both the newest
provider session and the one-session-earlier portfolio evaluation cutoff.

`scripts/generate_candidate_paper_signals.py` locates the newest completed
full-window `SPY` monitor artifact (or accepts an explicit artifact in tests),
reads `positions_normal_1day.pkl`, and converts the final target portfolio into
a JSON preview file. Its notional values are normalized to a configurable
paper budget and the output is marked `dry_run_only`.

`scripts/trade_v2.py` rejects `dry_run_only` signal files unless `--dry-run`
is active. This makes the new signal export deliberately unsuitable for
accidental order submission.

## Data Flow

1. Update/rebuild the modern provider using existing commands when fresh input
   data is available.
2. `make monitor-modern-low` derives scenarios from the newest provider
   calendar date, holds back the final date as Qlib's execution-calendar
   buffer, runs the candidate, and writes the rolling report under
   `.cache/reports/`.
3. `make paper-dry-modern-low` refreshes a full-window `SPY` snapshot, exports
   its latest target holdings to `.cache/signals/`, then invokes the existing
   executor in dry-run mode.
4. `make report-runs` remains available for the full MLflow experiment history.

## Safety And Failure Handling

- The monitor exits non-zero if a generated workflow fails unless explicitly
  asked to continue; a partial report may still show completed scenarios.
- Missing calendars, completed artifacts, or portfolio holdings fail with a
  clear message instead of writing empty trade previews.
- Candidate preview files are dry-run-only and are rejected by non-dry
  execution.
- Generated workflows, reports, MLflow artifacts, and preview signals stay in
  ignored `.cache/` or `mlruns/` paths.

## Verification

Automated tests cover dynamic rolling-window construction, benchmark-specific
workflow mutation, newest-scenario reporting, target-portfolio JSON export,
and refusal to submit dry-run-only signals outside dry-run mode. End-to-end
verification runs the unit suite, a dry-run signal preview against a completed
candidate artifact, the dynamic report workflow on current local data, and
the normal project health checks.

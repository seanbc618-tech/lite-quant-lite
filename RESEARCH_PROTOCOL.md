# Research engineering protocol v2

Written before running the new demonstration. Preserve the original PROTOCOL.md
and demo-results.json unchanged. No market model is fitted or selected here.

Question: can existing normalization, availability and label-boundary code produce
an inspectable offline research dataset without quietly using future information
or dropping incomplete symbols? This is an engineering case, not a market study.

Use only authored fixtures: two fictional issuers SYN_A and SYN_GAP; twelve
synthetic session dates; a fiscal-year filing, a quarterly YTD filing with its
prior-year comparison, and a later amendment. Introduce a conflicting fallback
revenue tag to exercise deterministic tag precedence. SYN_GAP has only income;
its absent required fields are explicitly declared synthetic source omissions.
The full 2 x 12 issuer/session grid must remain in the output, including dates
before any filing. These dates are NOT a validated exchange calendar.

Normalize facts with the inherited module. Build snapshots with its filed-date
as-of join, but make a snapshot usable for a signal only on the following
fixture session. Do not backfill an amendment into earlier signals. TTM bridge
must use FY + current YTD - prior YTD with a previously available FY filing.
No model thresholds, rankings or private portfolio rules are imported.

The inherited data layer can derive leverage from assets minus equity. Preserve
that behavior as source metadata, but do not treat derived values as reported
facts. Missing required inputs declared in SYN_GAP remain null and the entire
research cell stays INVALID_DECLARED_GAP. Pre-filing cells are NOT_YET_AVAILABLE,
not source gaps. Do not shorten the universe.

Extract the diagnostic's calendar-index endpoint rule: signal at t, entry t+1,
exit t+2 (one-session label). Train uses sessions 0–5, validation 6–9; sessions
10–11 are held aside and never scored. Preserve every train/validation cell;
label endpoints beyond the segment are INVALID_BOUNDARY with null eligibility.
An unavailable endpoint is INVALID_CALENDAR_COVERAGE, not a declared vendor gap.
Run endpoint auditing alone and combine it with availability status separately.
This is purging, not a full embargo, walk-forward model or prospective holdout.

Acceptance, fixed now: source module and selected definitions remain identical;
all inherited selected tests pass; twelve sessions/two symbols remain; future
amendment removal leaves pre-availability snapshots identical; deliberately using
the latest filing for every date is detected by an independent early-date
expected value; incomplete issuer metrics remain null; two boundary dates per
segment per issuer are excluded. Reject duplicate/out-of-order calendars and
sample dates outside the calendar. Repeated reports must be byte-identical.

Outputs: canonical facts, complete information panel, every segment cell, all
statuses, checks, protocol/input hashes. Retain all failures/limitations. Costs
are not applicable to this data-validation example; the unchanged portfolio
exercise remains the cost-accounting evidence. No economic inference, new
market data, tuning or real-world gap declaration is permitted.

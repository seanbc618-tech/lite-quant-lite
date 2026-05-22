# Modern Qlib Provider Implementation Plan

**Goal:** Add a small, independent modern US daily Qlib provider path before attempting a full universe rebuild.

**Scope:** Build `~/.qlib/qlib_data/us_modern_mega20` from Yahoo Finance daily OHLCV for a default 20-symbol liquid universe. Do not mutate the existing official `us_data` provider.

**Implementation checklist**

- [x] Add offline-tested OHLCV normalization.
- [x] Write Qlib-compatible `calendars/day.txt`, `instruments/*.txt`, and `features/<symbol>/*.day.bin`.
- [x] Include fields needed by basic Qlib handlers: `open`, `high`, `low`, `close`, `volume`, `factor`, `change`.
- [x] Add CLI target `make modern-provider`.
- [x] Add local CSV fallback target `make modern-provider-from-csv`.
- [x] Add report target `make data-report-modern`.
- [x] Document the workflow and its limitation as a small modern trial provider.

**Verification checklist**

- [x] Unit tests cover normalization and provider layout.
- [x] Manual Qlib read check confirms `D.features(..., ["$close"])` works against a generated temp provider.

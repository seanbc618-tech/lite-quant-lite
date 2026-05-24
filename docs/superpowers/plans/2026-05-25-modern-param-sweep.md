# Modern Parameter Sweep Plan

**Goal:** Run a reproducible parameter comparison for the modern liquid100 Qlib workflow.

**Scope**

- Base workflow: `config/qlib/workflow_lgb_alpha158_liquid100_modern.yaml`
- First matrix: `topk=10,15,20` x `n_drop=1,2,3` with base costs.
- Cost scenarios are supported for `base`, `half`, and `zero`.
- Benchmark scenarios are supported for SPY/QQQ comparison.
- Time slices are supported for `full`, `2025h1`, `2025h2`, and `2026ytd`.

**Implementation checklist**

- [x] Add a sweep runner that generates temporary workflow YAMLs under `.cache/qlib_sweeps/modern_liquid100/`.
- [x] Encode experiment names with `topk`, `n_drop`, and cost scenario.
- [x] Support `base`, `half`, and `zero` cost scenarios.
- [x] Support benchmark and time-slice scenarios.
- [x] Add `make sweep-modern`.
- [x] Keep MLflow output in the existing `mlruns/` store so `make report-runs` can compare results.

**Verification checklist**

- [x] Unit tests cover matrix generation and workflow mutation.
- [x] Run the first 9-run base-cost matrix.
- [x] Run focused cost sensitivity for `topk=15/20`, `n_drop=1/2`, and `half/zero`.
- [x] Run SPY/QQQ benchmark comparison over 2025H1, 2025H2, and 2026YTD.
- [x] Rebuild the provider from all local CSVs to test whether the universe can expand.
- [x] Summarize results with `make report-runs`.

**First base-cost matrix result**

- Best cost-adjusted run in the 9-run matrix: `topk=20`, `n_drop=1`, `cost=base`.
- Result from `make report-runs`: annualized excess with cost `-0.75%`, max drawdown with cost `-10.83%`, IR with cost `-0.0738`.
- Higher `n_drop` values were more sensitive to transaction cost in this data slice, so cost sensitivity should start from `topk=20,n_drop=1` and compare against one or two nearby challengers.

**Expanded validation result**

- Cost sensitivity confirms the alpha is thin: `topk20/drop1` is `+1.71%` at zero cost, `+0.48%` at half cost, and `-0.75%` at base cost.
- Time stability is weak: SPY benchmark `topk20/drop1/base` is `+6.02%` in 2025H1, `-23.67%` in 2025H2, and `-21.42%` in 2026YTD.
- QQQ is a harder benchmark for this universe: full-period `topk20/drop1/base` drops to `-7.53%`, and 2026YTD drops to `-35.96%`.
- Rebuilding from all local CSV data still produces 94 symbols, so expanding beyond liquid100 requires adding new CSV source data first.

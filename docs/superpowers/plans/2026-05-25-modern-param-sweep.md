# Modern Parameter Sweep Plan

**Goal:** Run a reproducible parameter comparison for the modern liquid100 Qlib workflow.

**Scope**

- Base workflow: `config/qlib/workflow_lgb_alpha158_liquid100_modern.yaml`
- First matrix: `topk=10,15,20` x `n_drop=1,2,3` with base costs.
- Cost scenarios are supported but should be run after the first matrix identifies promising topk/n_drop values.

**Implementation checklist**

- [x] Add a sweep runner that generates temporary workflow YAMLs under `.cache/qlib_sweeps/modern_liquid100/`.
- [x] Encode experiment names with `topk`, `n_drop`, and cost scenario.
- [x] Support `base`, `half`, and `zero` cost scenarios.
- [x] Add `make sweep-modern`.
- [x] Keep MLflow output in the existing `mlruns/` store so `make report-runs` can compare results.

**Verification checklist**

- [x] Unit tests cover matrix generation and workflow mutation.
- [x] Run the first 9-run base-cost matrix.
- [x] Summarize results with `make report-runs`.

**First base-cost matrix result**

- Best cost-adjusted run in the 9-run matrix: `topk=20`, `n_drop=1`, `cost=base`.
- Result from `make report-runs`: annualized excess with cost `-0.75%`, max drawdown with cost `-10.83%`, IR with cost `-0.0738`.
- Higher `n_drop` values were more sensitive to transaction cost in this data slice, so cost sensitivity should start from `topk=20,n_drop=1` and compare against one or two nearby challengers.

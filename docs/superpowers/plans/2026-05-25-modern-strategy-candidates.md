# Modern Strategy Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and evaluate modern liquid100 strategy candidates that can outperform the current Alpha158 baseline more consistently.

**Architecture:** Reuse the existing Qlib workflow YAML style and modern provider. Add three comparable workflows: LightGBM + Alpha360, XGBoost + Alpha158, and a low-turnover LightGBM + Alpha158 variant. Pin model seeds and use deterministic TopK tie breaking before using the existing sweep/report tooling for cost, benchmark, and time-slice validation.

**Tech Stack:** Qlib, LightGBM, XGBoost, pytest, Makefile, local MLflow file store.

---

### Task 1: Modern Candidate Workflows

**Files:**
- Create: `config/qlib/workflow_lgb_alpha360_liquid100_modern.yaml`
- Create: `config/qlib/workflow_xgb_alpha158_liquid100_modern.yaml`
- Create: `config/qlib/workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml`
- Test: `tests/test_modern_strategy_workflows.py`

- [x] Write failing tests for workflow existence, provider, model/handler, windows, costs, and low-turnover settings.
- [x] Run `pytest tests/test_modern_strategy_workflows.py -q` and confirm the tests fail because workflow files are missing.
- [x] Add the three workflow YAML files using the modern liquid100 provider and 2020-11-02..2026-05-15 windows.
- [x] Add a failing reproducibility test, then implement fixed seeds and deterministic tie breaking for identical model scores.
- [x] Run `pytest tests/test_modern_strategy_workflows.py -q` and confirm the tests pass.

### Task 2: Command Surface

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `LOCAL_STACK.md`

- [x] Add `qrun-modern-alpha360`, `qrun-modern-xgb`, and `qrun-modern-low` targets.
- [x] Document the new modern candidate commands.

### Task 3: Candidate Evaluation

**Commands:**
- `make qrun-modern-alpha360`
- `make qrun-modern-xgb`
- `make qrun-modern-low`
- `make sweep-modern ARGS="--base-config config/qlib/workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml --output-dir .cache/qlib_sweeps/modern_low_deterministic --topks 10,15,20,25,30 --n-drops 1,2,3 --cost-scenarios base --benchmarks SPY --time-slices full --keep-going"`
- `make sweep-modern ARGS="--base-config config/qlib/workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml --output-dir .cache/qlib_sweeps/modern_low_candidate15 --topks 15 --n-drops 1 --cost-scenarios base,half,zero --benchmarks SPY --time-slices full --keep-going"`
- `make sweep-modern ARGS="--base-config config/qlib/workflow_lgb_alpha158_liquid100_modern_low_turnover.yaml --output-dir .cache/qlib_sweeps/modern_low_candidate15_slices --topks 15 --n-drops 1 --cost-scenarios base --benchmarks SPY,QQQ --time-slices full,2025h1,2025h2,2026ytd --keep-going"`

- [x] Run the three full-period candidate workflows.
- [x] Run parameter, cost, time-slice, and benchmark sweeps for the viable low-turnover family.
- [x] Summarize with `make report-runs` and identify a research/paper-tracking candidate.

**Evaluation Result (2026-05-25):**

- Baseline deterministic Alpha158, Alpha360, and XGBoost were rejected on full-period SPY after costs (`-2.92%`, `-1.36%`, and `-10.63%` annualized excess return).
- Direct low-turnover `topk=25/n_drop=1` was reproducible but rejected at `-0.80%` annualized excess return after costs in two identical runs.
- The promoted candidate is low-turnover Alpha158 with `topk=15`, `n_drop=1`, `hold_thresh=3`: SPY full-period after-cost annualized excess return was `+10.69%` in repeated runs, with `-18.72%` maximum drawdown and `0.6404` information ratio.
- Deterministic runs use separate experiment namespaces so results are not mixed with the earlier non-deterministic portfolio selection.
- Cost sensitivity for the promoted candidate was monotonic: base `+10.69%`, half `+12.31%`, zero `+13.94%`.
- SPY time slices were `2025H1 +13.42%`, `2025H2 -4.64%`, and `2026YTD +5.81%`; QQQ full period was `+3.91%`, while `2026YTD` was `-8.74%`.
- Decision: keep this as a deterministic paper/research candidate, not an execution-ready strategy. It needs rolling-window and paper-trading monitoring because it underperformed during `2025H2` and versus QQQ in `2026YTD`.

### Task 4: Final Verification

**Commands:**
- `make test`
- `make health`
- `.venv/bin/python -m compileall scripts src tests`
- `make data-report-modern`
- `git diff --check`

- [x] Run verification commands.

Commit and push are recorded by repository history after this validation snapshot.

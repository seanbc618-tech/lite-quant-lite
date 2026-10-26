# Point-in-Time Data & Portfolio Lab

**Offline financial-data processing, temporal research validation, and portfolio accounting.**

English · [简体中文](README.zh-CN.md)

## Problem

Before interpreting a financial research result, can we establish what information
was available at the time, whether labels cross a training boundary, and whether
missing observations were silently removed?

This project makes those questions inspectable using **authored synthetic data**
and modules reused from a US-equity research codebase. It includes no private
selection strategy, market dataset, account credentials, or broker connection.

## Design choices

| Layer | Implementation | Inspectable evidence |
|---|---|---|
| Financial data | Reused filing normalization, as-of snapshots and trailing-twelve-month (TTM) calculations | Tag precedence, disclosure/amendment provenance, field-level nulls |
| Coverage | Selected existing calendar and instrument helpers | Full 2 × 12 issuer/session grid; unavailable observations remain visible |
| Research validation | Adapted label-endpoint audit | Boundary purging, unchanged early snapshots after removing a future amendment, deliberately leaky negative control |
| Portfolio accounting | Existing reconciliation helper and fixed teaching rule | Cash/cost identities, losses and missing scenarios |

The financial-data module and its tests are retained unchanged. Provider helpers
are selected by definition; the endpoint audit is explicitly documented as an
adaptation. [Reuse provenance](REUSE_MANIFEST.json) distinguishes these from newly
written demonstration code. No model-training framework is added.

Separate protocols were written before executing the respective examples:
[research protocol](RESEARCH_PROTOCOL.md) and [accounting protocol](PROTOCOL.md).
The examples do not combine into a claimed investment strategy.

## Verifiable engineering evidence

- [Complete research report](reports/RESEARCH_REPORT.md): 25 normalized facts,
  24 information cells and 20 split-audit cells, including every exclusion reason.
- [Complete accounting report](reports/REPORT.md): flat-price losses after fees,
  falling-price losses and explicitly invalid missing scenarios.
- [Validation record](reports/VALIDATION.md): 22 inherited/selected tests,
  independent-environment reproduction and byte-identical frozen outputs.
- [Historical research review](reports/HISTORICAL_REVIEW.md): unsuccessful model
  screening, limited coverage and reused historical test windows remain disclosed.
- [Scope review](reports/PORTFOLIO_REVIEW.md): why these components were selected,
  and what the project still does not demonstrate.

Full outputs are available as [research JSON](reports/research-results.json) and
[accounting JSON](reports/demo-results.json). Input and protocol hashes accompany
the outputs; [SHA256SUMS.json](SHA256SUMS.json) inventories the public files.

## Reproduce

The full example was verified with **Python 3.11.8**, NumPy 2.0.2 and pandas 2.3.3.
Dependency installation needs internet or locally supplied wheels. Execution
needs no network, account, key or private directory.

```bash
git clone https://github.com/seanbc618-tech/lite-quant-lite.git
cd lite-quant-lite
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-research.txt -r requirements-dev.txt
.venv/bin/python -B research_demo.py
.venv/bin/python -B verify_research.py
.venv/bin/python -B verify.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p no:cacheprovider -q
.venv/bin/python -B release_check.py
```

For the portfolio example alone, Python's standard library is sufficient:

```bash
python3 -B demo.py
python3 -B verify.py
```

Report commands print to stdout without replacing frozen JSON files.
`verify_research.py` runs isolated Python processes and rejects network events
observable through Python audit hooks; this is not an operating-system sandbox.
[Recorded package versions](reports/environment.txt) document the tested setup.

To export the explicit public file set, without Git history:

```bash
python3 -B release_check.py --export /tmp/financial-lab-review
```

The destination must not already exist. See [PUBLIC_FILES.txt](PUBLIC_FILES.txt).

## Findings and limitations

**Engineering acceptance is not evidence of economic effectiveness.** Only four
synthetic cells satisfy both information availability and split eligibility.
No universe reduction or imputation is used to hide the remaining cells. No model
is fitted or scored in this demonstration.

Daily filing dates do not establish intraday availability. The inherited TTM
logic is not a universal restatement audit. Boundary purging is not a complete
embargo, walk-forward experiment or empirical out-of-sample validation. Reserved
synthetic dates are not an independently untouched market holdout.

The reconciliation helper has input-validation and all-cash-target limitations.
Instant, complete synthetic fills do not establish real-world executability.
Historical market experiments are not independently reproduced by this package;
their unsuccessful results and coverage limitations remain visible in the
linked report. No profitability or production-readiness claim is made.

## Sources and development

Project code is distributed under [MIT](LICENSE), retaining the original
copyright notice. [Sources and material-specific rights](SOURCES.md) distinguish
code, authored fixtures and third-party dependencies. Dependencies retain their
own licenses and are not bundled. Synthetic records are not downloaded SEC or
market data; code licensing does not imply rights to external datasets.

Codex assisted this preparation, the teaching examples and documentation.
Historical individual responsibilities, independent development shares and
originality have not been established; this repository does not assert them.
The current working tree contains the reviewed public file set. This repository
retains its earlier research history through a normal commit; historical files
are still accessible and are not claimed sanitized. The allowlist and current
validation apply to the current tree, not all historical revisions.

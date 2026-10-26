# Sources, changes and rights / 来源、改动与许可

Source repository: https://github.com/seanbc618-tech/lite-quant-lite

Inspected source commit: `35ba1594134101351b429b9d1f14844bff293235`. The endpoint audit additionally adapts a bounded loop from a pre-existing
uncommitted diagnostic; its original file is not bundled. See REUSE_MANIFEST.json. The allowlist export contains no Git history. The GitHub repository retains
its original history; earlier revisions are not covered by the current scan.

| Candidate file | Source file | Change | SHA-256 |
|---|---|---|---|
| `us_quant/rebalance.py` | `src/us_quant/rebalance.py` | Unchanged | `2cab06727d6a0a3cdf1d2d790a3287f5d60c0246f2cacf3c33f41e76d4e0dcf2` |
| `tests/test_rebalance.py` | `tests/test_rebalance.py` | Unchanged | `bfaa8bbe570ea1a64fd39f3f98b0e536c14937b2d05984e303b0b73f89f7c608` |
| `LICENSE` | `LICENSE` | Unchanged | `0c075a85af00dcb2433eb2f2075f2705a3eb88473b6c8cb2c69daf01e096657d` |

Additional v2 reuse: the complete `src/us_quant/fundamentals.py` and its 15-test
file are unchanged. Six generic definitions from `scripts/data_report.py` and
two test bodies are selected verbatim, with imports reduced/redirected. The
label-endpoint loop is adapted with guards and retained statuses. Exact file
hashes, definition hashes and adaptation details are in [REUSE_MANIFEST.json](REUSE_MANIFEST.json).
No financial selector, rank threshold, optimized model setting or cached fact
is included. Standard accounting ratios are data transformations, not an exported
selection strategy. Existing test identifiers resemble public issuers but use
artificial observations, not actual financial data or personal/account records.

`us_quant/__init__.py` is newly reduced to a docstring; the original initializer
loads configuration and unrelated libraries. `demo.py`, `verify.py`, fixtures,
release checker and documentation are newly written with Codex assistance.
No strategy weights, selected model hyperparameters, broker clients, deployment
settings or market datasets were copied. The teaching allocation and fee examples
are new, fixed educational choices, not research parameters from the source.

## Material-specific rights

- Project code: MIT, retaining the original repository copyright notice
  in LICENSE. No claim is made to have audited every historical contributor or
  established individual authorship. The reused modules/tests contain no
  separate third-party copyright headers or vendored library code.
- New synthetic JSON inputs and outputs: authored for this demonstration, no
  external data provider. They are offered under the included MIT terms as
  example materials; their rights derive from their authorship, not from the
  license of a downloaded dataset. They are not market data or derived prices.
- New documentation: offered with this candidate under MIT. The historical
  review is a newly written qualitative assessment; original reports, private
  parameter tables, market metrics, predictions and datasets are not bundled.
- Portfolio runtime: Python standard library only. Research runtime: existing
  NumPy 2.0.2 and pandas 2.3.3, separately installed, not bundled. Python remains under its own license;
  no interpreter is bundled. See https://docs.python.org/3/license.html .
- Optional test dependency: pytest (Holger Krekel and others), MIT, installed
  separately rather than vendored. Its dependencies retain their own licenses.
  See https://docs.pytest.org/en/stable/license.html .
- Qlib, model libraries, Nasdaq/Yahoo data, SEC caches, valueinvest and related
  artifacts are NOT distributed in this candidate. Code licensing does not
  establish redistribution permission for their data or derived results.
  No external dataset license has been asserted or applied. A later market-data
  extension requires a separate source-specific rights review.

MIT reference checked during preparation: https://opensource.org/license/mit .
This provenance statement is scoped to the allowlist; it does not clear the
parent repository or its existing public history for republication.

## Research dependency licenses

Version-specific upstream notices checked during this extension:
- [NumPy 2.0.2 license](https://github.com/numpy/numpy/blob/v2.0.2/LICENSE.txt):
  NumPy Developers, BSD 3-Clause; distributions can include additional notices.
- [pandas 2.3.3 license](https://github.com/pandas-dev/pandas/blob/v2.3.3/LICENSE):
  pandas contributors and credited organizations, BSD 3-Clause.

These are separately installed existing dependencies, not relicensed project
code. Their wheels and transitive dependencies retain upstream notices; none is
bundled in the export. Authored SEC-shaped JSON, synthetic provider text and the
new generated results are offered as MIT example materials. No SEC response,
market archive or third-party derived dataset was downloaded or redistributed.

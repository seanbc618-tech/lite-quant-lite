# Validation record / 验证记录

Prepared 2026-10-27 (Asia/Shanghai). Pre-publication validation record. The extension supersedes the earlier
20-file, reconciliation-only scope. The original portfolio protocol and JSON
results remain unchanged.

## Current evidence

| Check | Result |
|---|---|
| Inherited reconciliation tests | 5 pass, unchanged source |
| Inherited financial-data tests | 15 pass, unchanged source |
| Selected provider tests | 2 pass, original bodies with redirected imports |
| Research demo controls | All pass: source tag precedence, TTM bridge, next-session amendment availability, prefix invariance, negative control, full grid, gap nulls, boundary/invalid-calendar guards |
| Research reproduction | Two isolated-process outputs byte-identical to frozen research-results.json |
| Portfolio reproduction | Unchanged six scenarios match the v1 frozen result |
| Fresh environment | Python 3.11.8 virtual environment created from scratch with only research/test requirements and their dependencies |
| Independent export | Exact 37-file research candidate allowlist (before the English-first publication edit) outside the source tree; no Git history; empty HOME unchanged |
| Source reuse | Exact file and selected-definition hashes checked against original local files |
| Sensitive-content check | All 37 research-candidate text files scanned; no configured pattern findings; manual scope review |

The full research case is verified on Python 3.11.8, NumPy 2.0.2 and pandas 2.3.3;
pytest is 9.0.3. Installed transitive package versions are recorded in
[environment.txt](environment.txt). The stdlib portfolio example was also verified
on Python 3.13.7 in the prior round; that is not a claim of research dependency
compatibility on 3.13. No package was installed into the parent project's environment.

## Reproduction and isolation

The commands in README were run against the standalone export using the newly
created virtual environment, minimal environment variables and an empty HOME.
Plugin autoload and bytecode/cache writes were disabled for tests. Only installed
dependencies, standard-library files and exported candidate files are required.
No source package path or original configuration is added to the process.

`verify.py` runs the original portfolio demo with `-I -S -B` (no site packages).
`verify_research.py` runs twice with `-I -B`, keeping installed numerical packages
but ignoring Python environment paths/user site. Its Python audit hook rejects
observable socket/urllib network events. This is not an OS-level network or
filesystem sandbox; native-extension behavior is not certified. Dependency
installation was online; demo execution makes no network calls.

All figures and cases are engineering fixtures, not market evidence. The reserved
synthetic dates are not a prospective OOS experiment. Full parent tests, historical
model retraining, data download, production jobs and broker access were not run.

## Public-scope and sensitive review

[PUBLIC_FILES.txt](../PUBLIC_FILES.txt) is explicit, not a recursive export rule.
It includes code, inherited tests, configuration, fixtures, provenance, reports
and environment metadata. The checker rejects symlink paths and non-matching
hashes; it exports only ordinary allowlisted files into a nonexistent directory.

Patterns check common service tokens, private keys, credential assignments,
personal absolute paths, emails and network/broker imports. Manual review verifies
that financial records are authored, original tests contain artificial examples,
only generic transformations/endpoint logic are reused, and no private strategy
settings, account data, actual trade records, production logs or deployment
credentials are included. Standard financial ratios are not marketed as an
original strategy. `REUSE_MANIFEST.json` discloses adaptations rather than
misrepresenting them as unchanged code.

Scanning is not proof of the absence of every possible secret. Hashes detect
changes, not independent scientific provenance; SHA256SUMS.json does not hash
itself. Original repository history is neither exported nor claimed sanitized.
No GitHub mutation occurred during that validation round. Publication was
subsequently authorized; the English-first release adds README.zh-CN.md to the
allowlist (38 files), with unchanged executable code, fixtures and frozen results.
The release is rechecked before upload; this record does not claim GitHub CI.

## Existing-repository publication

The reviewed working tree is published to `seanbc618-tech/lite-quant-lite` by a
normal descendant commit. Earlier Git history remains accessible and is not
claimed sanitized. Only the current allowlisted files are covered by these
checks; standalone file exports still omit history.

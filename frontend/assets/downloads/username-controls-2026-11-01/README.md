# Dated username-control study — 1 November 2026

35 platform-specific controls, eight platforms, three tools. Published upstream
test fixtures are not accounts owned by MyRecon or the user. Every fixture stays
on its original platform; no personal social-media handles or customer history.
All outcomes are dated observations, including exclusions and unknowns.

## Reproduce with Python 3.12

1. Clone https://github.com/4ryanwalia/Myrecon.git and check out
   `9491be6683cfd329a33e6c38682a7bc83a81032f`.
2. Create and activate an isolated Python 3.12 environment.
3. Copy `reproduction/expanded_username_study.py` into `backend/tools/` in that
   checkout. Other helpers are also included for inspection.
4. Run `python -m pip install requests -r backend/tools/requirements-benchmark.txt`.
   Both third-party tool source revisions are immutable pins.
5. Copy controls.json to the checkout root, then run from the checkout root:

   python backend/tools/expanded_username_study.py --manifest controls.json --output output/new-study.json

The manifest is fixed before predictions. Reference observations run first;
then the MyRecon web engine, Sherlock and Maigret run sequentially. Fixture
expectations and random-looking handles never determine reference truth.
One connection at a time, no retries, supplied authentication or block bypass.
Sherlock's current upstream exclusion list is captured per run; it can change.
Reproduce an observation, not an identical historical result: provider state,
network conditions and exclusions may differ. This is not a speed comparison.

## Inspect the retained evidence

study.json: reference identifiers, status, timing, response SHA-256/length,
all tool outcomes, native statuses, selected upstream rule snapshots, exclusions,
versions and source hashes. Complete profile bodies and credentials are omitted.
controls.json: exact predeclared manifest; its byte hash is manifest_sha256.
checks.csv: 105 rows (35 controls x 3 tools), including excluded/unknown cases.

Summary scoring: TP/TN/FP/FN need definitive reference AND prediction. The union
of unknown references/predictions is unresolved_checks, with no double counting.
Coverage = scored / 35. False-positive denominator = FP + TN. Native CLAIMED
outcomes remain visible even when HTTP-error normalization quarantines them.
No false positives were observed on definitive controls in this run. This does
not prove zero population error. Public fixtures, API overlap with MyRecon,
selection bias and eleven unresolved references limit the conclusion.

SHA256SUMS.txt covers the ZIP and loose downloads. The ZIP's CONTENTS.sha256
covers every included payload file (excluding the checksum file itself).
Upstream source-rule license notices are included under licenses/.

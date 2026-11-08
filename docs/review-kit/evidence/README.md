# Supplied first-party evidence

Collected by the MyRecon developer's agent on 1 November 2026. This is not an
independent review. No reviewer observations are represented by these files.

- Tested source: `9491be6683cfd329a33e6c38682a7bc83a81032f` (lookup engine and harness unchanged; documentation edits were present).
- Start: `2026-11-01T16:41:41Z`; finish: `2026-11-01T16:42:55Z`.
- Runtime: Windows, Python 3.13.14,
  requests 2.34.2. Exact installed
  packages are in [requirements-observed.txt](requirements-observed.txt).
- No GitHub token or other lookup credentials were supplied to the run.
- Command: `python backend/tools/daily_benchmark.py --output docs/review-kit/evidence/2026-11-01-benchmark.json`.
- Sample: 10 fixed public/synthetic usernames x 3 platforms = 30 pairs.
- MyRecon: 11 true positives, 19 true negatives, 0 false positives, 0 false
  negatives, 0 unknown predictions and 0 unknown references in this sample.
  The negative denominator is 19; the accuracy and coverage denominators are 30.
- HTTP-200 heuristic: 8 TP, 5 TN, 1 FP, 0 FN, 16 unknowns; 14/30 pairs scored.
  Its definitive-negative denominator is 6. This heuristic is not a competitor.
- Sherlock and Maigret: unavailable because the pinned packages were not installed.
  Their null accuracy/timing fields and zero scored pairs are not measured comparisons.
- Benchmark scoring/normalization tests: 21 passed. See
  [test output](2026-11-01-scoring-tests.txt).
- [Offline output](2026-11-01-synthetic-demo.json) contains explicitly synthetic
  examples, separate from the live artifact. It does not measure accuracy.

The sample is small, fixed, developer/community-oriented and shares API evidence
with its reference. It does not measure full-catalogue accuracy, reviewer-chosen
platforms, Android behavior, a privacy audit or independent identity attribution.
Unknowns observed elsewhere must remain unknown. The favorable MyRecon result
here cannot establish zero error rates outside this run. Network/provider drift
can change repeated results. Do not use sequential, unequal-work timings to rank
whole tools.

The live JSON uses the existing daily benchmark schema. It is a one-off artifact;
its inherited schedule/next-update fields do not schedule or promise a new review.
No homepage benchmark data were overwritten by this run.

[SHA-256 manifest](SHA256SUMS.txt) covers the evidence files other than itself.
The source commit, harness fingerprint and normalized dataset fingerprint are
also recorded inside the raw artifact. To check a file in PowerShell, use
`Get-FileHash -Algorithm SHA256 <file>`; on Linux use `sha256sum -c SHA256SUMS.txt`
from this evidence directory.

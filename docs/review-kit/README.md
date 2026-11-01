# MyRecon independent review kit

Prepared 1 November 2026. Publisher: Aryan Walia / BugSnaps, the developer of
MyRecon. This kit and its supplied measurements are first-party material, not
independent coverage. The documentation and outreach were prepared with AI assistance.

## Review request and disclosure

Please test whether MyRecon gives useful public-profile leads while making failed
and ambiguous checks visible. Report false positives, false negatives, unknowns,
setup friction and privacy concerns. Choose your own cases and comparators.
You control your conclusions, wording and decision to publish. This outreach
offers no compensation and requests no positive review, backlink or endorsement.

The MIT-licensed repository includes a Python CLI, Flask API and web frontend.
Hosted web access has guest, signed-in and paid limits. Android is maintained
separately; its source is not included here. Coverage and access differ between
interfaces. Check [current web plans](https://www.myrecon.xyz/pricing) and
[Android details](https://www.myrecon.xyz/app.html) before describing access.

## Version to reproduce

The supplied live measurement uses source commit
`9491be6683cfd329a33e6c38682a7bc83a81032f`. Start in a fresh clone:

```sh
git clone https://github.com/4ryanwalia/Myrecon.git
cd Myrecon
git checkout 9491be6683cfd329a33e6c38682a7bc83a81032f
python --version
git rev-parse HEAD
```

Use Python 3.10 or newer. The supplied run used Python 3.13 on Windows.
Live verdicts and timings can change with platform and network conditions.

## Two-minute offline introduction

```sh
python examples/offline_demo.py
python examples/offline_demo.py --json
```

No dependencies, account, key or network are needed. Four explicitly synthetic
examples demonstrate `found`, `not_found`, and `unknown`, including a login wall
and a timeout. This demonstrates output semantics, not accuracy. The
[sample data](../../examples/sample_verdicts.json) are not real account observations.

## Reproduce the small live regression sample

```sh
python -m venv .venv-review
# macOS/Linux: source .venv-review/bin/activate
# Windows PowerShell: .\.venv-review\Scripts\Activate.ps1
python -m pip install requests==2.34.2 pytest==9.2.0
python -m pytest backend/tests/test_daily_benchmark.py -q
python backend/tools/daily_benchmark.py --output review-benchmark.json
```

Use the environment's Python for every command. This makes live requests for the
[fixed public/synthetic controls](../../backend/data/benchmark-usernames.json):
ten usernames on GitHub, GitLab and Hacker News, or 30 username/platform pairs.
It also runs a simple HTTP-200 baseline. Sherlock and Maigret are `unavailable`
unless their pinned packages are installed; their unavailable rows provide no
comparative evidence. For actual named-tool measurements, follow the
[separate methodology](../NAMED-TOOL-BENCHMARKS.md) in its documented Python 3.12
environment and run with `--require-named-tools`.

Do not set credentials for the minimal reproduction. It needs no account or key.
The optional `GITHUB_TOKEN` changes reference requests; disclose that difference
if you use it, without publishing its value.

The supplied [raw artifact](evidence/2026-11-01-benchmark.json) includes UTC times,
tested source commit, dataset/harness fingerprints, individual verdicts, status
codes and timings. Read the [run notes](evidence/README.md) before quoting it.
This file is a one-off snapshot; inherited schedule metadata does not create a
new scheduled review.

The reference labels use official APIs and share some evidence with MyRecon.
This small regression sample is not independent ground truth or a full-catalogue
accuracy estimate. The HTTP baseline uses different request work and is not a
named competitor. The timings cannot rank whole tools.

## Add independently checked cases

Use accounts you control or have permission to test. Establish expected results
at the source before running MyRecon and retain dated evidence. A random handle
is only a candidate negative until the platform confirms absence.

1. Include known present and known absent accounts on the same platforms, plus
   reviewer-chosen platforms beyond the supplied developer/community sample.
2. Record naturally observed challenges, login walls, timeouts and rate limits
   as inconclusive. Do not bypass provider restrictions to complete a score.
3. Run your selected interface and record its settings. For full CLI installation
   and JSON output use the [quick start](../../README.md#quick-start). CLI `--deep`
   is a wider sweep, distinct from hosted Deep Search.
4. Keep the tool verdict and reason separate from your reference observation.
   A tool's own verdict is not reference truth. Retain mismatches and unknowns.
5. For comparisons use identical accounts/platforms and disclose versions,
   endpoints, concurrency, timeouts, caches, network and credentials differences.
6. Use the [review worksheet](review-worksheet.md). Redact personal information
   and credentials before sharing reports.

Report TP, TN, FP and FN with denominators. Also report unknown predictions and
unknown references. Accuracy is `(TP + TN) / (TP + TN + FP + FN)` and excludes
unknowns; report coverage as definitive scored pairs divided by all attempted
pairs alongside it. False-positive rate is `FP / (FP + TN)`; a zero denominator
means unavailable. Describe your independent reference procedure and any
disagreements with the harness.

## Privacy and interpretation

CLI lookups contact upstream providers from your network; running locally does
not provide anonymity. Hosted lookups transmit inputs to MyRecon and configured
providers. The frontend includes Google Analytics and optional Firebase sign-in.
Examine browser storage and cookies. See the
[privacy policy](https://www.myrecon.xyz/privacy.html) and
[cookie information](https://www.myrecon.xyz/cookies.html); this kit does not
certify their implementation. No privacy audit or Android device test is claimed.

Matching handles are leads. They establish neither a person's identity nor that
a handle is available to register. A breach check returning no result does not
establish that an address was never exposed.

## Findings and publication

Public reproducible bugs can be filed in [GitHub issues](https://github.com/4ryanwalia/Myrecon/issues).
Use the [security reporting policy](../../SECURITY.md) for confidential concerns.
Do not expose private identifiers in an outreach thread.

Disclose any relationship, payment or review access in your publication. No
special paid access is provided by this kit. If access is later supplied, record
what was provided and whether it differed from ordinary access.

A pending submission, self-written directory description or first-party kit is
not independent testing. A published listing should be described as a listing;
a review exists only once its publisher publishes it. Corrections can be linked
without conditioning or editing the reviewer's conclusions.

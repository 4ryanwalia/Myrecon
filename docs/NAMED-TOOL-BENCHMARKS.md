# Public MyRecon, Sherlock and Maigret benchmark

The homepage lets readers compare MyRecon with actual Sherlock and Maigret
engines, or the optional HTTP 200 heuristic. This is a small regression sample:
10 fixed public/synthetic usernames on GitHub, GitLab and Hacker News. It does
not estimate full-catalogue accuracy, establish identity or rank all OSINT tools.

## Reproduce a run

Use an isolated Python 3.12 environment, from the repository root:

```sh
python -m venv .venv-benchmark
# Activate that environment using the command for your operating system.
python -m pip install requests pytest -r backend/tools/requirements-benchmark.txt
python -m pytest backend/tests/test_daily_benchmark.py -q
python backend/tools/daily_benchmark.py --require-named-tools
```

Alternatively, use `--tool-python /path/to/environment/python` to keep the
third-party tools separate from the main Python environment. They are never
imported by the website/API server. `--output /path/to/benchmarks.json` writes a
separate artifact. The scheduled workflow runs daily and publishes only the
public benchmark JSON.

## What is held constant, and what differs

- All tools receive the same ten usernames and three named platforms on the same
  machine/network. They run in sequence, with up to three platform checks in
  parallel. The HTTP 200 heuristic is sequential.
- Sherlock and Maigret use unmodified detection rules from their bundled site
  databases. Their source commits are pinned in `benchmark-tools.json` and the
  install requirements. Database fingerprints and package/runtime versions are
  published with each run. An unexpected installation is unavailable, not a score.
- Native endpoints, headers, request counts and validation differ. MyRecon uses a
  six-second connect/eight-second read timeout and a 45-second sweep deadline;
  the named tools use an eight-second timeout. Per-username timing excludes
  package imports, process startup and reference lookups. These are observed
  timings, not an equal-request-work or whole-catalogue performance ranking.
- MyRecon and Maigret share some official API evidence with the reference. The
  reference is not an independent ground-truth audit. Provider availability and
  elapsed time between sequential checks can change the outcomes.
- No retries, recursive enrichment, cookies supplied by the harness, proxies,
  authentication supplied to tool engines, impersonation or block bypass. The
  optional GitHub token goes only to the independent reference request.

## Scoring and exclusions

Native `CLAIMED` maps to `found`; `AVAILABLE` maps to `not_found`. Preserve the
native status in raw checks. Native errors, illegal handles, missing results,
unsupported/disabled/protected sites and HTTP 401/403/429/5xx are `unknown`.
Reference failures are `unscored`. Failed batches have no measured timing.

Accuracy uses only definitive scored outcomes. False-positive rate uses only
definitive reference negatives. Coverage and unknown counts must accompany those
numbers. A tool with unavailable measurements has a graph gap, including its
coverage series; a completed tool with unknown verdicts has measured low coverage.

Older runs without named tools remain in history with gaps. They are never
backfilled or relabeled as Sherlock/Maigret results. The selected run displays
the tool version and commit, and the exact graph table includes UTC timestamps.

Raw artifacts retain verdicts, timing, public control names and provenance, not
profile bodies, authentication tokens or customer search history.

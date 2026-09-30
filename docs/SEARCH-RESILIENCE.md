# Privacy UI and resilient lookup changes

The production website is the static `frontend/` site and uses the Flask API in `backend/`. Both services must be deployed together for the full result and error contract.

The privacy disclosure sits beside the lookup controls on the homepage and Deep Search. It describes the current account records, username history, browser storage, temporary caching, provider sharing, analytics and IP-based abuse controls. The existing system cannot truthfully promise zero retention, email-only signup or no third-party processing. Email API results now bypass the application cache and are never written to account history. Search-related diagnostics omit exception details and Instagram handles. Hosting and provider logging is outside this application change.

The homepage renders real measurements from `frontend/data/benchmarks.json`, including false-positive counts and denominators, accuracy, definitive coverage, unknown/unscored counts, median and p95 duration, UTC dates and raw per-platform evidence. The graph offers false-positive, accuracy and timing views and an accessible data table. Outages create missing graph points, never zero-error claims. It labels measurements stale after 30 hours.

`backend/tools/daily_benchmark.py` uses the production `Sweep` on ten fixed handles from `backend/data/benchmark-usernames.json`, across GitHub, GitLab and Hacker News. Typed official API responses establish per-run reference labels; blocks, errors and malformed responses produce unknown references. The reference shares some API evidence with the engine: this is a small regression sample, not an independent accuracy audit, an identity check or a whole-catalogue estimate. Customer search history is never used. A separately labeled HTTP 200 heuristic provides a minimal baseline, not a result for a named OSINT competitor. Its serial timing and Sweep's parallel validation are descriptive, not an equal-configuration ranking.

The `Daily public benchmarks` GitHub Actions workflow runs daily at 03:17 UTC (08:47 IST), and supports manual dispatch. Scheduled runs can be delayed by GitHub. It reuses the existing reviewed main-branch publisher deploy key and commits only the generated benchmark JSON, which triggers Vercel. Repository review protections remain unchanged. The file keeps the last 90 daily samples; manual reruns replace the same UTC day. An artifact also retains the raw evidence. Run locally with `python backend/tools/daily_benchmark.py`; source failures remain visible and script-wide failures leave the previous JSON intact.

## Append a changelog entry

Edit `frontend/data/changelog.json` and add an object to `entries`:

```json
{
  "date": "2026-10-01",
  "version": "2026.10.01",
  "title": "Platform verification update",
  "changes": ["Describe the tested change and affected platform here."]
}
```

The homepage loads this file without caching and sorts entries by date. Date, title and a string array of changes are required. Version is optional. JSON fetch/parsing errors show a retry control and do not affect the lookup tool. Changelog content is rendered as text, never executable HTML.

## Google search limits

Set environment variables on the backend if tuning is needed:

| Setting | Default | Bound |
| --- | --- | --- |
| `DORK_CONCURRENCY` | 3 | 1 to 8 in-flight requests per process, shared across scans |
| `DORK_MIN_INTERVAL` | 0.35 seconds | 0.1 to 5 seconds between scheduled starts, plus 0.05 to 0.15 seconds jitter |
| `DORK_QUERY_TIMEOUT` | 8 seconds | 0.1 to 15 seconds for each connect/read timeout, shortened near deadline |
| `DORK_DEADLINE_SECONDS` | 45 seconds | 1 to 120 seconds for the Google stage |

Existing fast/deep query budgets remain. Transient transport and 5xx failures get at most one retry. HTTP 429 opens a cooldown of at least 60 seconds; HTTP 403 opens one of at least an hour. A longer numeric Retry-After is respected. Missing keys produce no simulated findings. Running HTTP calls retain their shared slots until they finish; the response returns at the scan deadline without waiting for executor shutdown. Limits and cooldowns are per process. Divide concurrency and query budgets across Gunicorn workers sharing a key; a distributed quota manager would be needed for a cross-instance guarantee. No pacing scheme guarantees that a provider will accept a request.

Responses retain `status: "ok"` for backward compatibility and add `partial` plus `errors` when a source fails. Each error has a source, code, safe message and retryable flag, with optional query index or retry_after. Partial responses are not cached. Google errors are carried through both username and investigation responses; email failures retain successful fallback and profile findings. Browser streams have time limits and interrupted username streams keep already received live cards. Rendering failures offer a usable recovery state.

## Files for review

| Files | Change |
| --- | --- |
| `backend/modules/google_dork.py` | Shared concurrency and pacing, jitter, retries, cooldowns, scan deadline and structured query failures |
| `backend/modules/email_lookup.py`, `backend/services/search.py`, `backend/services/investigation.py` | Preserve successful findings while reporting provider failures |
| `backend/app.py`, `backend/modules/enrichment.py` | Bypass email result caching, avoid caching partial scans, sanitize search-related diagnostics |
| `frontend/index.html`, `frontend/deep-search.html`, `frontend/privacy.html` | Privacy disclosure, benchmark comparison, public changelog and accurate retention copy |
| `frontend/assets/js/app.js`, `frontend/assets/js/deep-search.js`, `frontend/assets/js/partial-results.js` | Partial-result warnings, stream deadlines, render recovery, report warnings and Deep Search URL-validator scope fix |
| `frontend/assets/js/trust.js`, `frontend/assets/css/trust.css` | Responsive trust sections and safe changelog loading with retry fallback |
| `frontend/data/changelog.json`, `frontend/data/benchmarks.json` | Editable public updates and timestamped measured benchmark history |
| `frontend/scripts/version-site-assets.js`, generated HTML asset references | Version the new assets and refresh changed script URLs across the static site |
| `backend/tests/test_search_resilience.py`, `backend/tests/test_breach_sources.py`, `frontend/tests/search-resilience.test.cjs` | Outage, timeout, concurrency, retry, privacy, rendering and source-status regressions |

## Verification

```powershell
python -m pytest backend/tests -q -k 'not live'
node --test frontend/tests/*.test.cjs
```

Before production, run the existing frontend build so asset versions are refreshed, deploy the frontend and backend together, and verify real provider behavior with configured credentials. The offline suite uses mocked outages, retries, rate limits, timeouts and successful responses; it does not establish benchmark accuracy or production availability.

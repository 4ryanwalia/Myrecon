# MyRecon Extended Username Scan

Implement or finish the extended username-scan tier in this existing repository. Do not replace the current standard or full scan contracts.

## Current catalogue

- Standard web scan: 100 platforms.
- Full scan: 560 platforms from `backend/data/platforms_full.json`.
- Extended scan: 3,166 platforms total.
  - It includes the existing 560 full-scan platforms.
  - It adds 2,606 unique platforms from `backend/data/platforms_extra.json`.
  - The extra entries do not duplicate the original 560.

## Existing implementation points

- `backend/modules/sweep.py`
  - Loads `CATALOGUE` from `platforms_full.json`.
  - Loads `EXTRA` from `platforms_extra.json`.
  - Defines `EXTENDED = CATALOGUE + EXTRA` and `EXTENDED_TOTAL`.
- `backend/services/search.py`
  - `_run_full(username, extended=True)` must run `EXTENDED`.
  - Every scan result must retain `platform_checks`: one row for each platform actually attempted.
- `backend/app.py`
  - Supports `standard`, `full`, and `extended` scopes.
  - Extended scans require sign-in; do not expose extended platform details to guests.
- `frontend/index.html` and `frontend/assets/js/app.js`
  - Expose the Extended choice and show the actual 3,166-platform count.
- `frontend/data/platforms.json`
  - Downloadable, sanitized catalogue list. Keep it aligned with the runtime lists.

## Safety and accuracy requirements

1. Keep Standard at 100 and Full at 560. Extended is a separate opt-in tier.
2. Do not report a blocked request, timeout, login wall, ambiguous response, or invalid handle as “no account.” Use an `unknown`/unverified outcome.
3. A result must expose the platform, attempted public profile URL, verdict, status code, and human-readable reason.
4. Preserve the current live `found` events, but use the final completed report as the source of truth.
5. Do not add browser impersonation, CAPTCHA bypassing, signup checks, credential use, proxy rotation, or anti-bot evasion.
6. Keep rate limits, concurrency limits, deadlines, caching, and guest entitlement boundaries intact.

## Required checks before handing back

```powershell
python -m pytest backend/tests -q
node --check frontend/assets/js/app.js
node --test frontend/tests/*.test.cjs
```

The platform-catalogue test must confirm that `frontend/data/platforms.json` exactly matches the active Standard, Full, and Extended lists.

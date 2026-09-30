# Website Deep Search

`/deep-search.html` mirrors the Android app's public-source research flow. A full name searches Wikidata human records, GitHub full-name profiles and ORCID. A handle checks GitHub, Hacker News, Reddit, Bluesky, mastodon.social, DEV and Keybase. Both modes execute a bounded indexed-web plan and offer the remaining queries as browser links.

## Paid access

`POST /api/investigate/stream` verifies the Firebase bearer token and reads the server-owned entitlement before any public-source requests start. `deep_search_enabled` is true for a purchased Extended pack, including a pack with zero credits, or an unexpired legacy paid pass. Guests get 401 and signed-in free accounts get 402. Client-supplied plan fields have no effect.

Deep Search is included in the existing ₹99 plan. It spends neither Extended credits nor free daily scans. Standard and Extended username scan behavior stays unchanged. Concurrent Deep Searches share the existing full-scan admission limit, and the source adapters use bounded requests and response sizes.

## Evidence and privacy

Results stream as progress, partial and complete NDJSON events. Account presence requires a matching populated public API record. A failed feed keeps its confirmed profile and explains the activity gap. Blocks and malformed payloads are unavailable, never account absence. Name records remain candidates; no handles are guessed from names. Owner links are not crawled. Keybase proofs are labelled as published proofs, not independently verified signatures.

Indexed hits must satisfy the query's host, path boundary, quoted phrase and file-type constraints. The source host decides the result group. Google Custom Search uses the existing configured provider when available. Otherwise the app's keyless DuckDuckGo Lite and Bing RSS adapters run with pacing; a challenge or refusal stops requests to that provider. Source gaps stay visible, with browser query links as the continuation path.

Website searches run on the server, unlike Android's device lookups. Queries are sent to those public sources. This feature does not cache results or save them to account history. Export is an explicit local JSON download. Responses use `Cache-Control: no-store`.

Instagram results are indexed profiles, captions and mentions. The feature does not retrieve private content, likes or Instagram comment bodies. Recent activity is limited to what each public source returns, and Mastodon coverage is limited to mastodon.social.

## Validation and release

Run `python -m pytest backend/tests -q` and `node --test frontend/tests/*.test.cjs` from the repo root. The browser check is `node frontend/tests/deep-search-browser.cjs` with Playwright available on `NODE_PATH`; it uses local fixtures for access, streaming, theme, viewport and download checks. Set `MYRECON_BROWSER` when Chrome is installed at a different path.

Deploy the backend and frontend together. The frontend needs the new `deep_search_enabled` field from `/api/me`, and the backend must enforce paid admission before the new page is published. Existing paid purchases need no database migration. Local test and provider checks are not production deployment verification.

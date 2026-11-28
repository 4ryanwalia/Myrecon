# Deep Review Submission Packet 04: 24-Platform Byte-Level False-Positive Study & Scoring Tautology Analysis

## Custom Context Prompt (Paste into Google Deep Review)

> Please perform a strict adversarial peer review of this 24-platform empirical HTTP response comparison and heuristic-scoring failure analysis. Focus on: (1) whether the 6-of-24 identical/echo-only finding is properly bounded without over-generalizing to all platforms, (2) whether the "tautology trap" analysis (final URL echo, generic meta description, sitewide og:image) accurately diagnoses common username-checker false positives, (3) whether the two proposed profile-specific signals (handle in `<title>`, rendered per-account follower/following stats) have edge-case failure modes or blind spots (e.g., localized titles, client-rendered SPAs, zero-follower accounts), and (4) what missing data (such as the full 24-platform raw table) should be published to maximize scientific reproducibility.

---

# Why Username Checkers Report Accounts That Don't Exist: 24-Platform Paired Response Measurement

**Author:** Aryan Walia (CEH, Founder, MyRecon)
**Measured:** 6 September 2026 (Methodology review updated 28 November 2026)
**Canonical URL:** `https://www.myrecon.xyz/guides/why-username-checkers-report-fake-accounts.html`
**License:** CC BY 4.0 (Dataset JSON-LD declared on page)

## 1. Key Finding

Paired HTTP GET requests issued within the same minute from a residential connection across 24 well-known platforms (one handle known to exist vs synthetic control `zzqnope99123xqq`) showed that **6 of 24 platforms returned the same HTTP 200 page for both handles: 5 byte-for-byte identical, and 1 (WhatsApp) differing by only 29 bytes due to echoing the requested handle back into the HTML**.

Under RFC 9110 (HTTP Semantics), HTTP 200 confirms only that a representation was returned, never that a user profile exists.

## 2. Recorded Byte-Level Measurements (6 September 2026)

| Platform | Real Handle Response | Synthetic Control (`zzqnope99123xqq`) | Byte Difference |
|---|---|---|---|
| Discord | HTTP 200, 63,660 bytes | HTTP 200, 63,660 bytes | 0 bytes |
| MeWe | HTTP 200, 15,465 bytes | HTTP 200, 15,465 bytes | 0 bytes |
| Battle.net | HTTP 200, 4,776 bytes | HTTP 200, 4,776 bytes | 0 bytes |
| Matrix | HTTP 200, 2,774 bytes | HTTP 200, 2,774 bytes | 0 bytes |
| EyeEm | HTTP 200, 2,186 bytes | HTTP 200, 2,186 bytes | 0 bytes |
| WhatsApp | HTTP 200, 220,565 bytes | HTTP 200, 220,536 bytes | 29 bytes (handle echo) |

## 3. Root Causes & Scoring Tautology Proof

Three standard web-engineering patterns generate uniform HTTP 200 responses: (1) client-side single-page application (SPA) shells, (2) signed-out login walls, and (3) branded soft-404 pages.

Heuristic scorers frequently fall into a **tautology trap** by summing non-discriminative features:
- Handle appearing in final URL (+1, guaranteed because the client requested it)
- Presence of canonical URL / meta description (+2, present on generic shells)
- Presence of `og:image` (+1, sitewide default share banner)

Measured on `duolingo.com/profile/<handle>`, both a real handle and the invented control scored identical totals of **4 points** (`title=0, canon=2, url=1, type=0, img=1, desc=0`), triggering a false high-confidence match.

## 4. Proposed Account-Specific Evidence Gate & Trade-Off

Requiring at least one per-account rendered signal (handle echoed inside `<title>` rather than generic site name, or per-account rendered follower/following statistics) removed 11 false positives from a 16-account scan (Duolingo, Twitch, Trello, WordPress, Spotify, Trakt, HackerRank, Odysee, Giphy, CoinMarketCap, and Instructables), at the deliberate cost of classifying client-rendered or rate-limited sites (e.g., Instagram returning HTTP 429 for `@instagram`) as `unknown` rather than `not_found`.

## 5. Known Limitations & Open Questions for Deep Review (28 November 2026)

1. **Partial table disclosure:** The published article prints the 6 failing platforms in detail rather than all 24 measured platforms with raw headers/hashes. Publishing the complete 24-row CSV (as done in our later 1 Nov and 27 Nov studies) would improve full reproducibility.
2. **Temporal drift of byte counts:** Front-end bundle hashes change on every platform deploy; byte sizes are reproducible only as a live paired differential test, not as fixed constants.
3. **Edge cases in the proposed gate:** New accounts with 0 followers or localized/private titles can fail both title and stat checks unless paired with official typed API rules (as implemented in MyRecon's later Discord Get User API lookup and GitHub REST checks).
4. **Network origin sensitivity:** Residential vs datacenter IP ranges experience sharply different HTTP 429/403 refusal rates, requiring strict separation of `not_found` from `unknown`.

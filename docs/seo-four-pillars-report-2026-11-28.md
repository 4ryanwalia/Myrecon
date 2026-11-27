# Four-pillar SEO pass: final report, 28 Nov 2026

**Inputs**
- Baseline: `docs/seo-baseline-2026-11-28.md`
- Decision table: `docs/seo-vehicle-decisions-2026-11-28.md`
- Off-site list: `docs/seo-offsite-authority-2026-11-28.md`

The user approved everything on 28 Nov ("do everything now"). Their own brief makes the freeze non-negotiable, so three items stay frozen until 9 Dec: the /find/instagram-account retitle and two redirects.

## Context that limits every number below

- The site lost about 95% of its impressions when Google's November 2026 core update finished, around 24 Nov.
- Everything here makes pages better and more citable. None of it can be expected to move rankings before Google re-evaluates the site, which its own guidance says "could take several months", possibly "until the next core update". A December 2026 core update is preannounced.
- These changes ship before the 9 Dec 7-day vs 7-day re-judge, so that comparison cannot separate their effect from the update's.

## Pillar 2: pages upgraded (body only; titles, H1s and URLs unchanged)

| # | Page | What it now holds that it did not before | Sources and check date |
|---|---|---|---|
| 1 | /blog/best-osint-apps-for-android.html | Google Play "Data safety" table for all 9 Play apps, MyRecon's own row included (it declares the most sharing), and a "Where do other apps beat MyRecon?" section | Each app's Play Data safety page, 28 Nov |
| 2 | /blog/account-deletion-vs-deactivation.html | "What will my friends see if I deactivate?" and "How long can an Instagram account stay deactivated?" (PAA questions), a Facebook row and steps (30-day cancel, up to 90 days to delete content), and a slow answer split | facebook.com/help 214376678584711, 224562897555674 and 728869160569983 (the Instagram article), 28 Nov |
| 3 | /blog/sherlock-vs-maigret-vs-myrecon.html | "Where does Sherlock beat MyRecon?", "Where does Maigret beat MyRecon?" (from the 1 Nov 35-control study), "Is Sherlock OSINT legal to use?" (PAA), and a slow answer fixed | Our own study; READMEs as read on 18 Nov |
| 4 | /blog/instagram-osint-public-profile-guide.html | A **new measurement**: signed-out requests for @instagram, a real handle and a made-up handle all returned HTTP 200, a page of about 537.6 KB, a generic title and no profile record (27 Nov, 23:33 UTC). Plus two PAA answers | Our measurement |
| 5 | /find/github-profile | A **working in-browser GitHub user lookup** (created_at, type, repos, followers) through `GET /users/{username}`. A page-specific CSP allows api.github.com | GitHub Docs (Get a user, REST rate limits), 28 Nov |
| 6 | /whatsmyname-alternatives.html | A **new measurement**: all 690 active WhatsMyName rules replayed on 27 Nov. 291 (42.2%) still work, and no false positives. Downloadable CSV (CC BY-SA 4.0, handles omitted) and Dataset JSON-LD. The web UI was rechecked | Our measurement; whatsmyname.app read 28 Nov |
| 7 | /osint-tool-pricing.html | All 8 paid vendors re-read (none changed). 4 vendors added: OSINT-UI, OSINT Search Engine, OSINTverse, Forensic OSINT. IntelMind is left out (404). MyRecon's row re-dated | Vendor pages, 28 Nov |
| 8 | /blog/best-data-breach-checkers.html | Alert-trigger table quoting each provider (HIBP, Mozilla Monitor, XposedOrNot, Google, Apple, 1Password), and "Where do other breach checkers beat MyRecon?" | Provider pages, 28 Nov |
| 9 | /reverse-email-lookup.html | "Which Holehe checks does MyRecon skip, and why?" (12 of 123 modules, by method; this fact exists only here) and "What does this email lookup not do?" | backend/data/email-account-services.json (Holehe 14da70f) |
| 10 | /username-checker.html | Daily public-controls benchmark table (MyRecon, Sherlock, Maigret, HTTP 200 baseline), rebuilt from data/benchmarks.json on every build and scoped to 10 handles on 3 platforms | Our scheduled run |
| 11 | /reverse-username-lookup.html | A real dated sample result (octocat on 3 platforms against each official API), built from the same run, with data-driven wording | Our scheduled run |
| 12 | blog/find-your-own-old-accounts → blog/delete-old-online-accounts merge | **Not done**: frozen until 9 Dec | n/a |

## Pillar 3: authority

**On site (shipped):**
- 38 static guides had `author`/`publisher` as a bare `{"@type":"Organization","name":"MyRecon"}`. They now carry the site's Organization `@id`, so every page points at one entity.
- Every blog byline now links "How we check facts" to /about.html#editorial-method.
- Homepage `sameAs` is unchanged: GitHub and Play only. No official social profiles are live, and linking empty ones does more harm than good.

**Off site:** 10 ranked actions with drafts are in `docs/seo-offsite-authority-2026-11-28.md`. The Dev.to item is an outline only, under Dev.to's rules on AI-drafted posts.

## Pillar 4: technical fixes (top impact only), before and after

| # | Fix | Before | After | Re-measure |
|---|---|---|---|---|
| 1 | Indexing backlog: requested never-requested URLs first | 16 sitemap URLs in no GSC bucket, 28 "Discovered" (28 Nov) | 10 requested on 28 Nov (log in the baseline doc §7). The quota ran out at mgm-resorts-2023 | GSC URL Inspection on 5 Dec and 12 Dec |
| 2 | Single-inbound pages | 3 (alienstealerlogs, carhartt, limeleads; alienstealerlogs had 77 impressions at 39.2) | 0 (audit). Contextual links from the stealer-logs, settlement-claims and data-broker guides | `node scripts/seo-audit.js`, Crawl budget section |
| 3 | Slow answers (first paragraph under an H2 over 70 words) | 75 sections on 54 pages | 56 sections on 39 pages. Zero on every upgraded or ranking page. The 19 guide sections were split at sentence boundaries with wording unchanged. The rest are build-generated case files | `seo-audit.js` passages |
| 4 | Entity consistency (Organization `@id`) | 38 guides without it | 0 | `grep -L '#organization'` over sitemap pages |
| 5 | Wrong-intent redirect | /privacy/how-to-delete-github-account → /privacy/ hub | → /guides/delete-github-account.html (exact match). That URL had no impressions, so the freeze does not apply | `curl -sI` after deploy |
| 6 | LeakCheck attribution (open obligation since 25 Nov) | No "Powered by LeakCheck" link on results | Shown under email results whenever a LeakCheck source answered | Run an email check on the live site |
| 7 | sitemap.xml "Couldn't fetch" | GSC: Couldn't fetch, last read blank, 0 discovered. File serves 200 with the same 237 URLs as sitemap-index.xml (Success) | Resubmitted on 28 Nov after the deploy. GSC accepted it (Submitted: Nov 28) and still shows the cached "Couldn't fetch" immediately afterwards. No coverage was lost, because sitemap-index.xml lists the same URLs | GSC Sitemaps, 5 Dec |
| 8 | Redirect chains | 50 retired-but-indexed URLs checked | All single-hop; nothing to fix | Same curl loop |
| 9 | Core Web Vitals on top landing pages | GSC: "No data" (too little traffic). The PageSpeed Insights keyless quota was used up on 28 Nov | Lab reading from the in-app browser: TTFB 22 to 80 ms, full load 1.0 to 1.6 s on /, /find/instagram-account and the Android listicle. LCP and CLS were not measurable that way. **Not ranked as a top issue; no change made** | PSI with a free API key, or a field-data check once GSC has some |

**Not done (cannibalisation):**
- Title and H1 fixes inside query families are frozen until 9 Dec.
- Queue for after 9 Dec, each with its GSC query data:
  - the /find/instagram-account title
  - the phone-lookup redirect target
  - the linked-email redirect target
  - /free-osint-tool.html vs blog/best-free-osint-tools-for-investigators on "osint tools"
  - the old-accounts merge

## Tests

- `TZ=UTC node scripts/build-site.js`: clean.
- `npm run test:seo`: 41 of 42 pass in the worktree. The 42nd (asset-optimization) fails only because the worktree has no `esbuild`. It passes 4/4 against the main checkout's node_modules, and it fails the same way on untouched origin/main.
- The editorial overlap test (more than 75% shared 5-word phrases) passes.
- No em dashes in any added line.
- Commit hygiene: timestamp-only churn was reverted (breaches.json, case-files.json, feed.xml). The `app.js?v=` hash bumps are intended, because app.js changed.

## Live verification after deploy (commit 9e666dcd, 28 Nov)

- All 11 upgraded URLs return 200 with a self-canonical (curl).
- /privacy/how-to-delete-github-account returns 308 to /guides/delete-github-account.html.
- /downloads/whatsmyname-rule-replay-2026-11-27.csv returns 200 as text/csv.
- The live optimized app bundle contains the "Powered by LeakCheck" link.
- /find/github-profile sends a single Content-Security-Policy whose connect-src includes api.github.com. The .html variant 308s to it.
- The live GitHub lookup for octocat (in-app browser) returned: User, created 2011-01-25, 8 public repos, "Requests left this hour: 59", and no console errors.
- The IndexNow workflow succeeded for 9e666dcd.
- The indexing quota for 28 Nov was already used, so the 11 upgraded URLs are queued (baseline doc §7) rather than requested.

## Re-measure plan

Use the same method as `docs/seo-baseline-2026-11-28.md` (GSC in the signed-in in-app browser) and `docs/ai-citation-check-2026-11-18.md` (one navigate per query, `gl=us&hl=en`, read after the AI Overview renders).

| Date | What to read |
|---|---|
| **5 Dec 2026** | Re-inspect all 10 URLs requested on 28 Nov; request mgm-resorts-2023 and genesys; check sitemap.xml status |
| **9 Dec 2026** | 7-day vs previous 7-day: clicks, impressions, position (site, per country: US, India, UK, Brazil, Canada); indexed count. **Confounded** by this release and possibly the December core update. Then decide the frozen items with query data |
| **12 Dec 2026** | Second re-inspection of the 28 Nov URLs |
| **26 Dec 2026** (4 weeks) | 28-day page and query tables for the 11 upgraded pages and their target queries: "osint app for android", "deactivate vs delete account", "sherlock vs maigret", "instagram osint", "github user search", "whatsmyname alternative", "how much do osint tools cost", "best data breach checker", "reverse email lookup", "username checker", "reverse username lookup". GSC Generative AI report by page. Re-run the AI citation check on the 15 queries from 18 Nov plus these 11 |
| **23 Jan 2027** (8 weeks) | Same as 26 Dec. Count queries in the top 10, not just average position |

**Monthly:**
- Re-read the pricing table (next on 28 Dec).
- Re-run the WhatsMyName replay (same script, same method) to show decay over time.

## What I could not verify

- Instagram's own help pages rendered empty to the fetcher, so its deletion window and any maximum deactivation length are not claimed. TikTok support returned 503.
- Google's dark-web-report help URL returned 404, and Mozilla Monitor's FAQ hit a challenge page. Their rows say "not stated" instead of guessing.
- IntelMind pricing returned 404, so it is not in the table.
- Core Web Vitals field data does not exist for this site yet.
- Whether github.com profile pages show a join date: not checked, so no claim is made.
- The WhatsMyName replay ran once, from one network. Refused requests (23.2%) may succeed elsewhere, and the page says so.

## Claims deliberately not made

- No "top 10", "best" or rank claims. MyRecon is called "ranked first" only inside listicles that disclose that MyRecon publishes them.
- No Review or AggregateRating schema; no new FAQ schema without visible answers.
- No "accuracy across 560+ sites" claim. The benchmark is described as 10 handles on 3 platforms.
- No statement that LimeLeads is a data seller: the record does not say so.
- No Holehe "silent" claim; the page says each tested service receives the address.
- No country pages. Countries without local facts (UK, Brazil, Canada, Indonesia) get none.
- No typo or doorway pages, and no "view a private Instagram" content.

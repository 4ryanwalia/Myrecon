# MyRecon Deep-Review SEO & Content Quality Report (28 November 2026)

**Branch / Worktree:** `seo-deep-review-2026-11-28` at `C:\Users\91966\wt-deep-review-seo` (cut cleanly from `origin/main` commit `dbe668d4`)
**Status:** Built and verified locally; **uncommitted and unpushed** pending explicit user sign-off (per `docs/seo-four-pillars-prompt.md` line 28).
**Guardrails Respected:**
- 9 December 2026 Title / H1 / URL freeze honored (0 title changes, 0 H1 changes, 0 URL redirects/merges on ranking pages).
- User's 28 November preference to keep typo text on 7 live pages respected (held for explicit sign-off below).
- Zero em dashes (U+2014) added anywhere in prose.
- Platform counts stated as floors (`100` guest Quick, `560+` free Standard, `3,000+` Extended).
- Every newly added external primary-source URL fetched live and verified **HTTP 200** on **28 November 2026** (non-200 or wrong-topic links rejected).
- Zero fake reviews/ratings; publisher disclosures preserved.

---

## 1. What Google Deep Review Is & How We Applied It

`https://research.google/deepreview/` is Google Research's public multi-agent document verification and peer-review platform (evolved from Paper Assistant Tool / PAT, powered by Gemini 4 Argon, offering 2 free reviews/week with a Google Account or higher volume via a Gemini API key at `deepreview.googleapis.com`). It is **not** a Google Search ranking console.

Its 4-stage pipeline (Document Segmentation -> Adaptive Compute Budgeting -> Deep Parallel Verification -> Global Synthesis & Agentic Web/Literature Grounding) evaluates documents across five dimensions: logical soundness and technical accuracy, evidence grounding, missing context/literature gaps, internal cross-section consistency, and clarity/structure.

We executed two complementary tracks:
1. **Site-Wide Adversarial Deep-Review Pass (Implemented Now):** Applied all five verification dimensions across MyRecon's 237 indexable pages to eliminate internal contradictions, add live-verified primary-source citations, wire human `Person` authorship (`Aryan Walia`, CEH) and unified `Organization` entity IDs, deepen thin/unindexed pages, and eliminate all 56 slow opening answers.
2. **Ready-to-Submit Google Deep Review Packets (Created in `docs/deep-review-packets/`):** Prepared 4 self-contained Markdown dossiers with tailored custom-context prompts for MyRecon's 4 original empirical studies so you can submit them directly inside your signed-in Google Account at `https://research.google/deepreview/`.

---

## 2. Exact Before / After Verification Metrics

Measured with `node frontend/scripts/seo-audit.js --json` and a full-site DOM/JSON-LD telemetry check against `origin/main` (`dbe668d4`) before and after `TZ=UTC node scripts/build-site.js`:

| Metric | Before (`dbe668d4`) | After (`seo-deep-review-2026-11-28`) | Delta |
|---|---:|---:|---:|
| Indexable HTML pages in sitemap | 237 | 237 | 0 (URL freeze preserved) |
| Thin pages flagged by `seo-audit.js` | 0 | 0 | 0 |
| Duplicate titles / descriptions | 0 / 0 | 0 / 0 | 0 |
| Slow answers (`>70w` opening `<p>` under H2) | **39 pages (56 sections)** | **0 pages (0 sections)** | **-39 pages / -56 sections (100% cleared)** |
| Non-case-file slow answers | 11 pages (13 sections) | 0 pages (0 sections) | -13 sections |
| Case-file slow answers | 28 pages (43 sections) | 0 pages (0 sections) | -43 sections |
| `passages.totals.withDatedFact` | 104 | **163** | **+59 pages** |
| `passages.totals.longPages` / `fullyAnchored` | 193 / 192 | **198 / 197** | +5 long pages (including `is-myrecon-legit.html` + deepened blog posts) |
| Pages with `Person` `author`/`editor`/`reviewedBy` JSON-LD | **0 / 237** | **214 / 237** | **+214 pages** (100% Schema.org valid: `editor` on `Article`/`NewsArticle`/`TechArticle`/`HowTo`, `reviewedBy` only on `WebPage`) |
| Pages missing `#organization` `@id` | **10** | **0** | **237 / 237 (100% coverage)** |
| `reputationAbuse.flagged` (`seo-audit.js`) | 0 | **0** | Clean (recognizes first-party founder `@id`/`url`) |
| `/is-myrecon-legit.html` `inFirstParagraph` (`entitySalience`) | `true` | **`true`** | Preserved |
| Guides missing `/about.html#editorial-method` | **38** | **0** | **100% coverage** |
| Uncited guides (0 non-self primary citations) | **38** | **0** | **-38 (100% cited)** |
| Uncited blog posts / `/features` (0 non-self primary citations) | **7** | **0** | **-7 (100% cited)** |
| Blog posts `<600w` (main content) | **7** | **0** | **100% deepened (>=612w; final 3 >=908w)** |
| Uncited breach case files (text-only sources) | **24** | **0** | **-24 (100% clickable verified URLs)** |
| Dead HTTP 404 / soft-404 links in breach case files | **10** (9 HTTP 404 + 1 soft-404) | **0** | **-10 (all 60 case files live-crawled; replaced with live HTTP 200 official/regulator URLs)** |
| Dead HTTP 404 links on comparison pages | **1** (`spiderfoot.net/documentation/` x3 on `/vs/spiderfoot`) | **0** | **-1 (replaced with live GitHub `README.md` & `modules` URLs)** |
| Indexable pages with >=1 primary external citation | 147 / 237 | **227 / 237** | **+80 pages** |
| Added lines containing em dashes (U+2014) | N/A | **0** | Clean |

### Deepened Page Word Counts (Main Content)

| Page | Before | After | Key Additions |
|---|---:|---:|---|
| `/is-myrecon-legit.html` | 569 w | **1,146 w** | Data-flow architecture table matching `privacy.html`, Discord ID vs username nuance, "what MyRecon does and does not do", live-verified GitHub/Play/RFC/Discord/HIBP/OSINT Tools Library links, `Person` + `#organization` schema (typo mention kept intact pending sign-off) |
| `/reverse-email-lookup.html` | ~1,300 w | **1,726 w** | Live-verified links to Holehe commit `14da70f`, LeakCheck, XposedOrNot, Gravatar JSON docs, `keys.openpgp.org`, HIBP API v3 & Pwned Passwords, RFC 7208/6376/7489 + verification workflow & limitations section |
| `/app.html` | 508 w | **764 w** | Android vs Web feature/privacy comparison table, permissions & telemetry disclosure, verified Pwned Passwords link |
| `/services.html` | 575 w | **817 w** | Verification methodology (broker suppression vs Google removal vs outdated refresh), DIY vs managed decision criteria, verified Google/FTC links |
| `/blog/genesys-october-2026-security-incident.html` | 460 w | **714 w** | BEC/CRM threat analysis, SPF/DKIM/DMARC verification steps, verified Genesys/RFC/CISA/NCSC citations |
| `/blog/irhythm-october-2026-data-breach-notice.html` | 465 w | **645 w** | HIPAA notification lag context, medical-identity fraud checklist, verified HHS OCR/FTC/IdentityTheft.gov links |
| `/blog/ahold-delhaize-october-2026-cyber-incident.html` | 468 w | **612 w** | Outage phishing/refund-scam checklist, retail credential-stuffing check, verified Ahold Delhaize/CISA/HIBP links |
| `/blog/username-reuse-privacy.html` | 534 w | **866 w** | Breach-linkage risk analysis, 5-step self-audit, 4-tier handle-compartmentalization table, verified EFF/NCSC/CISA/NIST citations |
| `/blog/after-finding-an-old-account.html` | 523 w | **1,102 w** | Actionable closure checklist, password-manager and federated-login cleanup, GDPR Art. 17 / UK ICO / CCPA deletion table, Google Outdated Content removal, verified NIST/CISA/EC/ICO/CA OAG/Google links |
| `/blog/breach-check-no-results-meaning.html` | 581 w | **916 w** | 4 coverage-gap causes, 4-step post-clean-check verification workflow (Pwned Passwords k-anonymity, session/forwarding audit, regulator confirmation, MFA/IdentityTheft.gov), verified HIBP/NIST/CA OAG/CISA/IdentityTheft.gov links |
| `/blog/breach-date-vs-disclosure-date.html` | 572 w | **908 w** | Statutory notification clocks (GDPR Art. 33 72h, UK ICO, CERT-In 6h, CA OAG breach portal), 5-step alert verification sequence, verified EC/ICO/CERT-In/CA OAG/HIBP/CISA links |

---

## 3. Summary of Changes by Source File

### A. Critical Internal Contradictions Fixed (C1–C3 + Bonus Homepage & Watch Fixes)
- **C1 (`frontend/scripts/build-discovery-pages.js` -> `discord-id-lookup.html`):** Fixed FAQs #4 and #5 (both visible HTML and `FAQPage` JSON-LD) so they accurately describe BOTH local Snowflake decoding AND the live `Get User` API public-profile lookup (username, display name, avatar, banner, badges). Added live-verified clickable Discord Developer Docs URLs (`https://docs.discord.com/developers/reference`, `https://docs.discord.com/developers/resources/user`, checked 28 Nov 2026).
- **C2 (`frontend/pricing.html`, `frontend/content/is-myrecon-legit-main.html`, `frontend/index.html`):**
  - Replaced `pricing.html` L110 `Saved reports in your account` with `Browser-local session review & export (no server scan history)` (aligning with `pricing.html` L178 and `privacy.html`).
  - Replaced `is-myrecon-legit-main.html` `signed-in reports` with accurate browser-local session/export wording plus a 6-row data-flow table aligned with `privacy.html`.
  - Caught and fixed an additional C2 contradiction on `frontend/index.html` L232 (`Account Data` previously claimed `saved username reports`, contradicting L231 right above it and `privacy.html`).
- **C3 (`frontend/index.html`, `frontend/content/blog/best-username-search-apps.html`):**
  - Updated `frontend/index.html` radar orbit nodes so login-walled platforms (`Instagram`, `Snapchat`, `X`, `TikTok`, `Facebook`, `Threads`, `Pinterest`) show `UNKNOWN`, `Discord` shows `ID ONLY`, `Spotify` shows `NOT FOUND`, and measured open platforms show `FOUND`, aligning visual UI with MyRecon's three-state model.
  - Updated `content/blog/best-username-search-apps.html` phone mockup (`Instagram: UNKNOWN`, `GitHub: FOUND`, `GitLab: NOT FOUND`, `TikTok: UNKNOWN`, removed `Linked: 2 LIKELY`) and softened `#1 username search app` badge to `Publisher's Android pick (see disclosure)` while preserving the full publisher disclosure block.
- **`watch.html` noindex link (`frontend/scripts/build-discovery-pages.js`):** Replaced link to `noindex` `/directory.html` with `/guides/`.

### B. Entity, Author & E-E-A-T Schema Fixes (M1, M3)
- Wired Schema.org-valid `Person` authorship (`@id: https://www.myrecon.xyz/founder.html#person`, Aryan Walia, Penetration Tester and Founder), using `editor` on `CreativeWork` subtypes (`Article`, `NewsArticle`, `TechArticle`, `HowTo`) and `reviewedBy` strictly on `WebPage` nodes across:
  - `frontend/scripts/build-blog.js` (38 blog articles)
  - `frontend/scripts/build-seo-pages.js` (20 SEO-kit pages: `editor` on 19 `Article` pages, `reviewedBy` on `/features` `WebPage`)
  - `frontend/scripts/build-case-files.js` (60 breach case files)
  - `frontend/scripts/build-discovery-pages.js` (7 `WebPage` discovery pages, plus fixed `.table-wrap` -> `.discovery-table-wrap` on `username-checker.html`, `reverse-username-lookup.html`, and `reverse-email-lookup.html` to eliminate mobile 375px horizontal overflow)
  - `frontend/scripts/build-breaches.js` (`editor` Person added while preserving `author.url = about.html` required by `tests/breach-story.test.cjs`)
  - `frontend/scripts/finalize-editorial.js` (`is-myrecon-legit.html`)
  - All 38 static guides in `frontend/guides/*.html`, `frontend/whatsmyname-alternatives.html`, `frontend/osint-tool-pricing.html`, `frontend/upcoming-osint-tools-2027.html`, 3 `/templates/*.html` articles, `frontend/app.html` (`WebPage` + scoped `.editorial-table-wrap` CSS), `frontend/services.html` (`WebPage`), and `frontend/assets/footprint/index.html` (`WebPage`)
- Updated `frontend/scripts/seo-audit.js` `reputationAbuse()` so first-party founder `@id`/`url` under `https://www.myrecon.xyz/` is recognized as first-party (0 false-flagged pages).
- Updated `frontend/tests/watch-metadata.test.cjs` to match the replacement of `noindex` `/directory.html` with `/guides/` on `watch.html`.
- Fixed all 10 pages missing `{"@id":"https://www.myrecon.xyz/#organization"}`:
  - `build-breaches.js` (`/breaches/`), `build-case-files.js` (`/breaches/case-files/`), `build-seo-pages.js` (`/find/`, `/guides/`, `/privacy/`, `/vs/`), `frontend/templates/index.html` (`/templates/`), `frontend/guides/check-email-data-breach.html`, `frontend/scripts/finalize-editorial.js` (`is-myrecon-legit.html`), `frontend/assets/footprint/index.html` (`/footprint`).
- Added `/about.html#editorial-method` byline/methodology reference to all 38 static guides missing it.

### C. Stale-Fact Fixes & Flagship Study Methodology Reviews (M2, M4, M5)
- `frontend/guides/username-osint-search.html`: Fixed stale `run a username across 100+ platforms in Deep Search` link to accurately separate `username-checker.html` (`560+ platforms`) from `deep-search.html` (public posts/comments/mentions).
- `frontend/vs/have-i-been-pwned.html`: Updated stale `100+ platforms` row to `100 guest / 560+ free account / 3,000+ Extended`, refreshed check date to `28 November 2026` with live-verified HIBP API v3 & Pwned Passwords links, and split its slow answer.
- `frontend/username-sweep-vs-deep-search.html`: Updated stale `Basic plan` -> `Pro plan`, `All 31 guides` -> `All OSINT and privacy guides`, added verified RFC 9110 & GitHub API links.
- `docs/nextjs-seo-kit/data/content/target/discord-user.json` & `frontend/content/editorial-hubs.json`: Clarified Discord username sweep vs numeric Discord ID lookup and replaced 403-blocked Discord Help Center links with live HTTP 200 Discord Developer Docs URLs.
- `frontend/upcoming-osint-tools-2027.html`: Cross-linked the 27 Nov 2026 WhatsMyName 690-rule replay (`291/690 = 42.2%`) on `/whatsmyname-alternatives.html`.
- Added dated **"Methodology review and limitations (28 November 2026)"** Deep-Review blocks to all 4 flagship empirical studies:
  - `frontend/content/blog/username-search-controlled-study-2026.html` (including exact 95% Clopper-Pearson upper confidence bounds: 18.5% on 0/18, 28.5% on 0/11)
  - `frontend/whatsmyname-alternatives.html` (690-rule arithmetic audit, single-network & no-redirect bounds)
  - `frontend/content/blog/username-search-benchmark-research.html` (repeated-measurement clustering, post-hoc fix boundary, GitHub Actions HTTP 419 artifact)
  - `frontend/guides/why-username-checkers-report-fake-accounts.html` (RFC 9110 framing, Discord ID clarification, fixed Deep Search link text)

### D. Verified Primary-Source Citations & Link Integrity (All Checked Live HTTP 200 on 28 Nov 2026)
- Added verified citations to all 5 uncited tool/reference pages (`deep-search.html`, `username-sweep-vs-deep-search.html`, `osint-cheat-sheet.html`, `osint-glossary.html`, `templates/osint-evidence-log-template.html`), plus `reverse-username-lookup.html`, `reverse-email-lookup.html`, `free-osint-tool.html`, and `discord-id-lookup.html`.
- Added topic-specific verified primary sources to all 34 uncited static guides and all 4 uncited SEO-kit guides (`document-metadata-forensics-osint.json`, `mcp-osint-agentic-recon.json`, `search-usernames-across-social-platforms.json`, `myrecon-black-friday-sale-2026.json`).
- Added live-verified HTTP 200 primary-source citations (`checked 28 Nov 2026`) to the final 7 uncited editorial pages:
  - `frontend/content/blog/after-finding-an-old-account.html` (deepened 523w -> 1,102w; NIST SP 800-63B, direct canonical CISA passwords & MFA, European Commission GDPR, UK ICO right to erasure, CA OAG CCPA, Google Refresh Outdated Content)
  - `frontend/content/blog/how-to-find-hidden-social-media-profiles.html` (HIBP FAQ, Gravatar JSON docs, EFF SSD, UK NCSC)
  - `frontend/content/blog/how-to-find-someones-social-media-accounts.html` (corrected Gravatar SHA-256/legacy MD5 JSON endpoint, removed unsourced "Over 70%" figure, added Gravatar Hash/JSON docs, GitHub REST Users API, HIBP FAQ, Wayback Machine Guide, 18 U.S.C. 1030 CFAA)
  - `frontend/content/blog/osint-username-tools-and-techniques.html` (Sherlock, Maigret, WhatsMyName repos, RFC 9110 HTTP Semantics, RFC 7480 RDAP; fixed web guest-preview architecture claim to align with `privacy.html`, `is-myrecon-legit.html`, and `app.html`)
  - `frontend/content/blog/report-social-media-impersonation.html` (CISA MFA, UK NCSC social media safety, ReportFraud.ftc.gov, FTC Scams, FBI IC3)
  - `frontend/content/blog/why-online-privacy-matters.html` (EFF SSD, UK NCSC, Google Personal-Info Removal, FTC Online Privacy & Security, UK ICO public portal)
  - `docs/nextjs-seo-kit/data/content/core/features.json` (`/features`: added 8 primary technical specs: RFC 9110, HIBP API v3, Pwned Passwords, Discord Developer Docs, Gravatar JSON Docs, Holehe, RFC 7480 RDAP, RFC 8484 DoH; also aligned server-storage copy with `privacy.html` to eliminate an additional C2 discrepancy)
- Deepened the final 2 `<600w` blog posts (`breach-check-no-results-meaning.html` 581w -> 916w; `breach-date-vs-disclosure-date.html` 572w -> 908w) with concrete verification workflows and live HTTP 200 primary sources.
- Converted named text-only sources across all 24 uncited breach case files in `frontend/content/case-files/` into live-verified clickable HTTP 200 primary-source links.
- Replaced all 10 pre-existing dead links across all 60 breach case files (9 HTTP 404 + 1 FCC soft-404) plus 1 dead comparison-page link with live-verified HTTP 200 official/regulatory URLs (`checked 28 Nov 2026`):
  - `cambridge-analytica-2018.html`: ICO migrated final report PDF (`ico.org.uk/media2/migrated/2260271/...`)
  - `ashley-madison-2015.html`: live FTC Dec 2016 settlement press release + OPC Canada PIPEDA Findings #2016-005
  - `clearview-ai-2020.html`: ICO Oct 2025 Upper Tribunal judgment release on the May 2022 enforcement appeal
  - `sony-psn-2011.html`: retired ICO URL noted; linked official PlayStation Blog May 2011 response + US House Energy & Commerce hearing Serial No. 112-55 on `govinfo.gov`
  - `talktalk-2015.html`: ICO TalkTalk cyber-attack investigation & £400,000 fine summary (`ico.org.uk`)
  - `vtech-2015.html`: live FTC Jan 2018 COPPA settlement press release (`ftc-act` slug)
  - `british-airways-2018.html`: ICO Oct 2020 British Airways Penalty Notice PDF (`ico.org.uk/media2/migrated/2618421/ba-penalty-20201016.pdf`)
  - `marriott-starwood-2018.html`: ICO Oct 2020 Marriott Monetary Penalty Notice PDF (`ico.org.uk/media2/migrated/2618524/marriott-international-inc-mpn-20201030.pdf`)
  - `rockyou-2009.html`: live FTC Mar 2012 RockYou security & COPPA press release (`ftc.gov`)
  - `t-mobile-2021.html`: live FCC Sep 2024 T-Mobile settlement document page (`fcc.gov/document/t-mobile-required-change-business-practices-after-data-breaches`, replacing soft-404)
  - `docs/nextjs-seo-kit/data/content/comparison/spiderfoot.json` (`/vs/spiderfoot`): replaced dead 404 `spiderfoot.net/documentation/` (3 occurrences) with live HTTP 200 `github.com/smicallef/spiderfoot/blob/master/README.md` and `github.com/smicallef/spiderfoot/tree/master/modules`

### E. Slow Answers Eliminated (56 -> 0)
- Fixed an off-by-one space-concatenation bug in `frontend/scripts/breach-story.js` line 11 (`(group + sentence)` -> `` `${group} ${sentence}` `` with threshold `65`), resolving `breaches/cargurus.html` and `breaches/crunchbase.html`.
- Split slow opening paragraphs (`>70w`) across `docs/nextjs-seo-kit/data/content/target/github-profile.json`, `docs/nextjs-seo-kit/data/content/comparison/sherlock.json`, `guides/how-data-brokers-work.html`, `guides/photo-metadata-exif.html`, `guides/sim-swap-attacks.html`, `templates/osint-evidence-log-template.html`, `terms.html` (3 sections), `vs/have-i-been-pwned.html`, `whatsmyname-alternatives.html`, and all 28 case files (23 body H2s + 17 `faq[0].a` splits rendered as clean `<p>` blocks via `build-case-files.js`).

---

## 4. Test Suite Execution Log

Executed inside `C:\Users\91966\wt-deep-review-seo\frontend` after `TZ=UTC node scripts/build-site.js` (with `NODE_PATH` pointing to `Recon-main\frontend\node_modules` so `esbuild` ran `asset-optimization.test.cjs` without polluting the worktree):

- `npm run test:seo` (`crawler-discovery.test.cjs`, `seo-discovery.test.cjs`, `editorial-quality.test.cjs`, `asset-optimization.test.cjs`, `canonical-links.test.cjs`, `android-promotion.test.cjs`, `scripts/indexnow.test.js`): **45 / 45 PASS, 0 FAIL**
- `node --test tests/watch-metadata.test.cjs tests/breach-story.test.cjs tests/editorial-evidence.test.cjs`: **17 / 17 PASS, 0 FAIL**
- Playwright Chrome visual/layout verification (`editorial-browser.cjs` PASS on 14 routes at 390px/1280px, `editorial-shell-browser.cjs` PASS, custom Playwright Chrome audit at 1440px desktop & 375px mobile across Round 1 pages + all 15 Round 2 modified pages: 8 blog posts, `/features`, and 6 breach case files): **0 horizontal overflow, 0 page errors, all tables cleanly styled, >=1 primary external citation rendered inside `<main>` on every modified route**.
- Note: Full 234-test sweep across all non-browser `tests/*.test.cjs` files passes **231 / 234**; the 3 failures are pre-existing in historical `tests/osint-publication.test.cjs` (which asserts the retired `/blog/top-10-osint-tools.html` and 12 retired video sitemap entries from prior commits on `origin/main`).

---

## 5. Google Deep Review Submission Packets Ready for Upload

Created in `docs/deep-review-packets/`:
- `docs/deep-review-packets/README.md` (submission guide & 2-week schedule for the 2 reviews/week quota)
- `docs/deep-review-packets/01-controlled-study-35-controls-2026-11-01.md`
- `docs/deep-review-packets/02-whatsmyname-690-rule-replay-2026-11-27.md`
- `docs/deep-review-packets/03-username-benchmark-and-http-status-2026-11.md`
- `docs/deep-review-packets/04-false-positive-24-platform-measurement-2026-09-06.md`

---

## 6. Items Held for Explicit User Sign-Off (Not Executed Yet)

1. **Git Commit & Push Approval:** Changes remain uncommitted in clean worktree `C:\Users\91966\wt-deep-review-seo` (branch `seo-deep-review-2026-11-28`). Approve to stage, commit, push to `origin/main`, and trigger Vercel deploy + IndexNow pings.
2. **Typo Text on 7 Live Pages:** Per your 28 Nov preference, typo text was preserved on `index.html`, `is-myrecon-legit.html`, `deep-search.html`, `osint-glossary.html`, `guides/what-is-osint.html`, `blog/best-sherlock-alternatives.html`, and `find/instagram-account`. Recommend removing post-9-Dec if GSC confirms zero standalone typo-page lift and to avoid quality-classifier friction during the December 2026 core update.
3. **Post-9-Dec Frozen Retitles & Cannibalisation Merges:** Keep all titles/H1s/URLs frozen until the 9 December 2026 7-day vs 7-day GSC re-judge; then evaluate consolidating overlapping pairs flagged by `seo-audit.js` (e.g., `/blog/delete-old-online-accounts.html` vs `/blog/find-your-own-old-accounts.html` and the 3-page `best username search tools` cluster).
4. **Off-Site Authority Actions (Human-Executed):** Submit the 4 packets in `docs/deep-review-packets/` to `https://research.google/deepreview/`, follow up on OSINT Framework PR #933, list MyRecon on AlternativeTo (as alternative to Sherlock, WhatsMyName, Namechk), submit Awesome-OSINT PRs citing the 27 Nov WhatsMyName 690-rule replay CSV, and answer relevant `r/OSINT` threads with the Discord ID lookup where genuinely helpful.
5. **Re-Measure Checkpoints:** 9 December 2026 (7-day vs previous 7-day GSC clicks, impressions, top-10 query count, indexed count) and +4 / +8 weeks after deploy (including AI Overview citation re-checks per `docs/ai-citation-check-2026-11-18.md`).

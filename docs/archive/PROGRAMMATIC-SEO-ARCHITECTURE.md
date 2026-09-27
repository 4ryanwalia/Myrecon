# Programmatic SEO Architecture — MyRecon (myrecon.xyz)

> Historical planning document from September 2026. It records proposals,
> not a guarantee that every route, integration, or commercial offer shipped.
> Check the current site and source before citing a feature or metric.

**Deliverable:** 100–200 page programmatic SEO architecture, sitemap structure,
metadata generator, page layout specs, and content generation engine.

Written against the actual stack: static HTML on Vercel, no framework, Node
build scripts in `frontend/scripts/` (`build-blog.js`, `build-breaches.js`,
`build-sitemap.js`, `indexnow.js`), a 561-platform lookup table in
`backend/data/platforms_full.json`, and the quality bar already established in
`SEO-REPORT.md` (50–60 char titles, 140–160 char descriptions, zero orphan
pages, JSON-LD on every page).

---

## Table of contents

1. [Strategic foundation](#0-strategic-foundation)
2. [Deliverable 1 — Site architecture & programmatic sitemap](#1-deliverable-1--site-architecture--programmatic-sitemap)
3. [Deliverable 2 — SEO metadata generator template](#2-deliverable-2--seo-metadata-generator-template)
4. [Deliverable 3 — High-converting page layout specifications](#3-deliverable-3--high-converting-page-layout-specifications)
5. [Deliverable 4 — Programmatic content generation strategy](#4-deliverable-4--programmatic-content-generation-strategy)
6. [Expansion — novel silos and untapped keyword clusters](#5-expansion--novel-silos-and-untapped-keyword-clusters)
7. [Guardrails — compliance, ethics, and spam defence](#6-guardrails--compliance-ethics-and-spam-defence)
8. [Rollout plan and measurement](#7-rollout-plan-and-measurement)

---

## 0. Strategic foundation

### 0.1 The three audiences and what each one searches for

| Audience | Job to be done | Query shape | Monetisation path |
|---|---|---|---|
| **Cybersecurity professionals / investigators** | Enumerate a handle's full presence fast, without running Sherlock in a terminal | `sherlock alternative`, `username osint tool`, `cross-platform entity resolution`, `osint api` | Pro pass, API, enterprise |
| **Privacy-conscious individuals** | Find where *their own* data is exposed, then remove it | `how to delete [platform] account`, `remove my info from [broker]`, `find my old accounts` | Footprint removal service (`/services.html`) |
| **Developers / automators** | Wire lookups into a pipeline | `open source intelligence api`, `username lookup api`, `automated reconnaissance` | API keys, enterprise |

Every page cluster below maps to exactly one audience. **Never mix two intents
on one URL** — a "vs Sherlock" page is investigator intent, and bolting
"delete your account" content onto it dilutes both.

### 0.2 Intent tiers

- **Tier 1 — Transactional/product** (`/`, `/pricing.html`, `/vs/*`, `/find/*`)
  Direct conversion. Publish first, protect hardest.
- **Tier 2 — Informational with a conversion bridge** (`/guides/*`, `/delete/*`)
  Ranks on long-tail, feeds Tier 1 through contextual CTAs.
- **Tier 3 — Authority/link-magnet** (`/breaches/*`, `/case-files/*`, `/blog/*`)
  Already shipping. Exists to earn links and freshness signals for the whole
  domain.

### 0.3 Non-negotiable constraints from the existing audit

These are inherited rules; violating them re-opens bugs that `SEO-REPORT.md`
already closed:

1. Sitemap is **generated from disk** (`build-sitemap.js`) — new pages must be
   real files in output, never a hand-edited list.
2. Every canonical points at **`https://www.myrecon.xyz`** (apex redirects).
3. Exactly **one H1** per page, no heading-level skips.
4. Titles **50–60 chars, zero duplicates across the site** (assert at build).
5. Descriptions **140–160 chars**, never cut mid-word.
6. JSON-LD on every page; **nothing marked up that is not visible on-page**.
7. **Editing generated output is temporary — only the generator counts.**

---

## 1. Deliverable 1 — Site architecture & programmatic sitemap

### 1.1 Information architecture (top-level)

```
www.myrecon.xyz/
├── /                                  Hub (Tier 1)
├── /pricing.html  /enterprise.html  /api.html  /cli.html  /legal-osint.html
├── /find/                          [A] Platform username lookup silo (55)
├── /vs/                            [B] Comparison silo (30)
├── /solutions/                     [C] Extraction-keyword silo (12)
├── /guides/                        [D] OSINT how-to library (36, 19 exist)
├── /delete/                        [E] Deletion & privacy hub (42)
├── /for/                           [F] Persona/use-case pages (8)
├── /tools/                         [G] Free tool pages (6)
├── /breaches/  /case-files/  /blog/  [H] Tier-3 authority (exists, 150+)
└── /deep-search.html  /services.html  /app.html  /about.html  /contact.html
```

**Click-depth rule (inherited):** nothing more than 3 clicks from `/`. Every
silo has an index page (`/find/`, `/vs/`, `/delete/`, `/solutions/`, `/for/`,
`/tools/`) that is itself an indexable CollectionPage, so depth is
`/ → /find/ → /find/instagram.html` = 2.

---

### 1.2 Cluster A — Core product pages (14 pages)

| Path | Content intent | Primary target keyword |
|---|---|---|
| `/` | Transactional hub: 560-platform sweep, email, breach, domain | `osint tool` / `username lookup` |
| `/username-search.html` | Feature: multi-platform reverse username lookup | `reverse username lookup` |
| `/email-investigation.html` | Feature: cross-platform email tracking | `email footprint check` |
| `/phone-lookup.html` | Feature: cross-platform phone-to-entity correlation | `phone number osint` |
| `/breach-exposure.html` | Feature: breach correlation + risk band | `check if email was breached` |
| `/deep-search.html` | Feature: username correlation console (exists) | `username correlation` |
| `/pricing.html` | Free vs Pro pass vs enterprise, FAQ schema | `osint tool pricing` / `free username lookup` |
| `/enterprise.html` | Bulk, API SLA, onboarding, security review | `enterprise osint platform` |
| `/legal-osint.html` | Law-enforcement / legal-hold workflow, chain of custody | `osint for law enforcement` |
| `/api.html` | OSINT API docs hub, endpoints, rate limits, code samples | `open source intelligence api` |
| `/cli.html` | Terminal client — the honest "we also *are* a CLI tool" page | `osint command line tool` |
| `/services.html` | Removal service (exists) | `personal data removal service` |
| `/about.html` / `/founder.html` / `/contact.html` | Trust / E-E-A-T (exist) | brand + `about [brand]` |

**Internal link rule:** every Tier 2 page links back to exactly one Cluster A
page with a descriptive anchor (never "click here").

---

### 1.3 Cluster B — Programmatic comparison pages (30 pages)

Path pattern: `/vs/<slug>.html` · Intent: commercial investigation ·
Primary keyword: `<competitor> alternative` + `<brand> vs <competitor>`

**URL naming law:** one slug, one competitor, one canonical, forever. Never
rename a published comparison slug.

| # | Path | Target keyword |
|---|---|---|
| 1 | `/vs/sherlock.html` | sherlock alternative |
| 2 | `/vs/maigret.html` | maigret alternative |
| 3 | `/vs/social-searcher.html` | social searcher alternative |
| 4 | `/vs/namechk.html` | namechk alternative |
| 5 | `/vs/spiderfoot.html` | spiderfoot alternative |
| 6 | `/vs/instant-username-search.html` | instant username search alternative |
| 7 | `/vs/knowem.html` | knowem alternative |
| 8 | `/vs/usersearch.html` | usersearch.org alternative |
| 9 | `/vs/whatsmyname.html` | whatsmyname alternative |
| 10 | `/vs/holehe.html` | holehe alternative |
| 11 | `/vs/maltego.html` | maltego alternative |
| 12 | `/vs/osint-industries.html` | osint industries alternative |
| 13 | `/vs/namecheckr.html` | namecheckr alternative |
| 14 | `/vs/checkuser.html` | checkuser alternative |
| 15 | `/vs/social-catfish.html` | social catfish alternative |
| 16 | `/vs/spokeo.html` | spokeo alternative |
| 17 | `/vs/beenverified.html` | beenverified alternative |
| 18 | `/vs/pipl.html` | pipl alternative |
| 19 | `/vs/hunter.io.html` | hunter.io alternative |
| 20 | `/vs/epieos.html` | epieos alternative |
| 21 | `/vs/ghunt.html` | ghunt alternative |
| 22 | `/vs/intelx.html` | intelligence x alternative |
| 23 | `/vs/recon-ng.html` | recon-ng alternative |
| 24 | `/vs/theharvester.html` | theharvester alternative |
| 25 | `/vs/amass.html` | amass alternative |
| 26 | `/vs/dehashed.html` | dehashed alternative |
| 27 | `/vs/haveibeenpwned.html` | have i been pwned alternative |
| 28 | `/vs/google-dorks.html` | google dorking vs tool |
| 29 | `/vs/username-checker-extensions.html` | browser username checker vs tool |
| 30 | `/vs/manual-osint.html` | manual osint vs automated |

**Supporting hub pages (3, count inside Cluster B):**
`/vs/` (index — "MyRecon vs manual and CLI OSINT tools"), `/vs/free-tools/`,
`/vs/paid-tools/`.

**Differentiation requirement:** each page must carry at least **one data
point the competitor's own site cannot have** — a measured speed benchmark
(§3.1), platform-count delta, or evidence-class table. A comparison page with
no proprietary data is a doorway page.

---

### 1.4 Cluster C — Universal username target pages (55 pages)

Path pattern: `/find/<platform>.html` · Intent: informational→transactional ·
Primary keyword: `[platform] username lookup` / `find [platform] account by
username`

**The engine:** each page is generated from one record of
`backend/data/platforms_full.json` (561 records), filtered to a curated
top-55 allowlist by category weight and search demand. The page is *not* a
thin spinner — it contains that platform's real lookup mechanics (URL pattern,
status-code semantics, whether it has an API, false-positive risk) pulled from
the same fields the tool uses at runtime.

| Tier | Platforms (slugs) |
|---|---|
| **Tier 1 — publish first (15)** | `instagram`, `tiktok`, `x-twitter`, `reddit`, `telegram`, `youtube`, `facebook`, `linkedin`, `snapchat`, `pinterest`, `discord`, `twitch`, `github`, `spotify`, `steam` |
| **Tier 2 (20)** | `threads`, `bluesky`, `mastodon`, `tumblr`, `medium`, `quora`, `vimeo`, `dailymotion`, `behance`, `dribbble`, `deviantart`, `figma`, `soundcloud`, `substack`, `patreon`, `fiverr`, `upwork`, `goodreads`, `letterboxd`, `last-fm` |
| **Tier 3 (20)** | `roblox`, `epic-games`, `xbox`, `playstation-network`, `hackernews`, `stackoverflow`, `keybase`, `kaggle`, `gravatar`, `venmo`, `cashapp`, `etsy`, `ebay`, `amazon-author`, `flickr`, `500px`, `strava`, `duolingo`, `wattpad`, `airbnb` |

**Per-page keyword set (programmatically derived):**
`[platform] username lookup` (primary) · `find [platform] account by
username` · `check [platform] username` · `is [platform] username taken` ·
`[platform] profile search by username`.

**Mandatory unique blocks per page** (feeds the dedupe defence in §4.4):

1. Platform-specific lookup facts: URL pattern (`instagram.com/{username}/`),
   response semantics (200 vs 404 vs 429), login wall behaviour, API vs HTML
   probe, `echoes_handle` false-positive risk.
2. "What a found profile reveals" — bio, avatar, follower graph, join date.
3. "False positives on [platform]" — ties directly to your existing
   `/guides/why-username-checkers-report-fake-accounts.html` (internal link).
4. Screenshot-free evidence table (avoids image weight; site is 51KB total).
5. Related finds: 3 sibling platforms + 1 guide + 1 comparison.
6. Embedded deep-search CTA pre-filled with the platform.

**Scale rule:** ship Tier 1 (15) → measure indexed rate → ship Tier 2 only if
the Tier 1 cohort clears **≥70% indexed within 60 days**. Do not publish 55 at
once into a domain with no history for that template.

---

### 1.5 Cluster D — Educational & how-to long-tail guides (36 pages, 19 exist)

Path pattern: `/guides/<slug>.html` · Intent: informational ·
Primary keyword: long-tail `how to` / `what is`

**Existing (19):** `what-is-osint`, `username-osint-search`,
`check-email-data-breach`, `how-data-brokers-work`, `reduce-your-digital-footprint`,
`reverse-image-search`, `social-media-privacy`, `verify-an-osint-finding`,
`why-username-checkers-report-fake-accounts`, `what-http-responses-reveal`,
`investigate-a-domain`, `dns-records-explained`, `spf-dkim-dmarc-explained`,
`whois-rdap-explained`, `ip-geolocation-reverse-dns`, `how-to-spot-phishing`,
`strong-passwords-guide`, `two-factor-authentication` (+ index).

**New (17):**

| # | Slug | Primary keyword |
|---|---|---|
| 1 | `find-hidden-accounts-with-a-username` | how to find hidden accounts |
| 2 | `track-a-digital-footprint` | how to track a digital footprint |
| 3 | `username-enumeration-explained` | username enumeration |
| 4 | `cross-platform-entity-resolution` | what is entity resolution |
| 5 | `pii-correlation-explained` | pii correlation |
| 6 | `reverse-username-search-explained` | reverse username search |
| 7 | `find-all-accounts-linked-to-email` | find all accounts linked to my email |
| 8 | `find-accounts-linked-to-phone-number` | accounts linked to phone number |
| 9 | `detect-impersonation-accounts` | how to find fake accounts of me |
| 10 | `osint-for-hr-screening` | osint background check candidates |
| 11 | `brand-impersonation-monitoring` | how to find impersonators of your brand |
| 12 | `stealer-logs-explained` | what are stealer logs |
| 13 | `combolist-explained` | what is a combolist |
| 14 | `credential-stuffing-explained` | credential stuffing check |
| 15 | `cross-check-breach-exposure` | how to check breach exposure across sites |
| 16 | `metadata-osint-in-photos` | photo metadata osint |
| 17 | `osint-workflow-for-investigators` | osint investigation workflow |

**Editorial bar:** 1,200+ words, ≥4 H2s, ≥2 internal links in-body, ≥1
external authority link (NIST, CISA, FTC, ICO), one original observation or
measured data point. Anything failing this is not shipped (see §4.5 QA gate).

---

### 1.6 Cluster E — Privacy, digital hygiene & account deletion hub (42 pages)

Path pattern: `/delete/<slug>.html` · Intent: high-volume informational ·
Primary keyword: `how to delete [platform] account` / `remove [broker] listing`

This cluster is the volume engine — deletion queries have enormous,
evergreen, low-difficulty demand, and every page has a natural contextual
pitch into `/services.html`.

**E1 — Platform deletion guides (25):**
`instagram`, `facebook`, `tiktok`, `x-twitter`, `snapchat`, `youtube`,
`linkedin`, `reddit`, `pinterest`, `twitch`, `discord`, `tumblr`, `medium`,
`quora`, `steam`, `roblox`, `epic-games`, `whatsapp`, `telegram`, `signal`,
`slack`, `dropbox`, `google`, `microsoft`, `amazon`

**E2 — Data broker & people-search opt-outs (14):**
`spokeo`, `whitepages`, `beenverified`, `intelius`, `mylife`,
`fastpeoplesearch`, `truepeoplesearch`, `radaris`, `ussearch`,
`peoplefinder`, `pipl`, `acxiom`, `lexisnexis`, `clearview-ai`

**E3 — Regional / high-intent specials (3):**
`truecaller-listing-removal` (massive India demand, matches your audience),
`gravatar-opt-out` (you already have Gravatar breach data), `google-results-removal`
(Delisting under GDPR/CCPA "right to be forgotten")

**Hubs (3, inside Cluster E):**
`/delete/` (index: "Account deletion guides for 42 platforms"),
`/delete/data-brokers/` (index: opt-out master list),
`/privacy-checklist.html` (lead-magnet checklist → email capture).

**Per-page unique blocks:**
1. Exact current steps with the real settings path (`Settings → Accounts →
   Deactivate`), screenshot-free numbered list (mobile + desktop variants).
2. **Deactivation vs deletion** callout (you already have a blog post on this
   — cross-link, don't duplicate).
3. What survives deletion: cached profiles, data-broker copies, breach copies.
4. Retention window table (e.g. "up to 90 days for backups").
5. **Contextual pitch block** (see §3.2) → `/services.html` + free scan.
6. Schema: `HowTo` (steps visible on-page) + `FAQPage` (only FAQs visible).

---

### 1.7 Cluster F — Persona / use-case pages (8 pages)

Path pattern: `/for/<slug>.html` · Intent: segment qualification

`/for/cybersecurity-analysts.html` · `/for/private-investigators.html` ·
`/for/legal-teams.html` · `/for/journalists.html` · `/for/brand-protection.html` ·
`/for/hr-screening.html` · `/for/incident-response.html` ·
`/for-individuals-check-yourself.html`

Each: problem → workflow (3 steps) → compliance note → feature proof → CTA.
These are the pages your sales/enterprise traffic lands on; they also capture
`osint tools for [role]` queries with almost no competition.

### 1.8 Cluster G — Free tool pages (6 pages)

Path pattern: `/tools/<slug>.html` · Intent: free utility (top-of-funnel)

`/tools/username-availability-checker.html` · `/tools/data-broker-opt-out-list.html` ·
`/tools/email-exposure-check.html` · `/tools/handle-variation-generator.html` ·
`/tools/breach-timeline.html` · `/tools/username-regex-tester.html`

Free, no-signup, one screen, result + "unlock the full 560-platform report"
CTA. These are your highest-link-velocity assets — put them in
`BACKLINK-STRATEGY.md` outreach.

### 1.9 Cluster H — Existing authority assets (unchanged)

`/breaches/*` (generated), `/case-files/*` (generated), `/blog/*` (hand-written
source in `content/blog/`), plus `/guides/` and the 9 privacy articles. These
stay as-is; new clusters only need to **link into** them.

### 1.10 Page-count rollup

| Cluster | New pages | Phase |
|---|---|---|
| A — Core product | 9 net new (5 exist) | 1 |
| B — Comparisons (+3 hubs) | 33 | 1 |
| C — Platform lookup (+index) | 56 | 1–2 |
| D — Guides (+index) | 18 | 2 |
| E — Deletion/privacy (+3 hubs) | 45 | 2–3 |
| F — Personas (+index) | 9 | 3 |
| G — Free tools (+index) | 7 | 3 |
| **Total new** | **177** | |
| Existing indexable (now) | 168 | |
| **Target site total** | **~345** (≈180 core pages + breach/case-file archive) | |

If you want to stay inside a strict **100–200 page** programmatic envelope:
ship Clusters A+B+C (98) + Cluster E (45) = **143 pages**, defer D/F/G to
phase 2. The comparison + platform + deletion triad alone carries the entire
keyword thesis.

### 1.11 XML sitemap structure (scale beyond 50k URL rule)

`build-sitemap.js` already errors above 50,000 URLs — irrelevant now, but the
structure should be split by cluster from the start for crawl-budget hygiene:

```
/sitemap.xml                      ← sitemap index
/sitemap-core.xml                 ← Cluster A + F + G
/sitemap-comparisons.xml          ← Cluster B
/sitemap-lookup.xml               ← Cluster C
/sitemap-guides.xml               ← Cluster D
/sitemap-deletion.xml             ← Cluster E
/sitemap-breaches.xml             ← Cluster H (existing generated)
/sitemap-case-files.xml           ← Cluster H (existing generated)
```

Each entry keeps the existing `<lastmod>` precedence: JSON-LD `dateModified`
→ git commit → mtime. **A platform page's `lastmod` must be tied to the
platform record's `last_verified` date**, not the build time — otherwise every
rebuild claims 177 pages changed today, which is the exact failure mode the
current script was written to avoid.

---

## 2. Deliverable 2 — SEO metadata generator template

### 2.1 Token dictionary

| Token | Source | Example |
|---|---|---|
| `{{platform}}` | `platforms_full.json → name` | `Instagram` |
| `{{platform_slug}}` | slugified name | `instagram` |
| `{{competitor}}` | comparison record | `Sherlock` |
| `{{competitor_slug}}` | slug | `sherlock` |
| `{{broker}}` | broker record | `Spokeo` |
| `{{topic}}` | guide record | `Username Enumeration` |
| `{{number}}` | computed | `560` |
| `{{year}}` | build date | `2026` |
| `{{audience}}` | persona record | `Cybersecurity Analysts` |
| `{{brand}}` | constant | `MyRecon` |
| `{{verb}}` | rotation pool | `Find` / `Locate` / `Check` |

**Verb rotation pool (prevents title-template collision):**
`Find`, `Locate`, `Check`, `Search`, `Trace`, `Audit`, `Map`, `Sweep` —
selected by `hash(slug) % pool.length` so assignment is deterministic across
builds (no random drift between local and CI output).

### 2.2 Title templates (hard cap 60 chars, target 50–60)

| Cluster | Template | Example | Chars |
|---|---|---|---|
| A (feature) | `{{topic}}: {{benefit}} \| {{brand}}` | `Reverse Username Lookup Across 560 Sites \| MyRecon` | 51 |
| A (pricing) | `Pricing: Free & Pro OSINT Scans \| {{brand}}` | `Pricing: Free & Pro OSINT Scans \| MyRecon` | 42* |
| B | `{{brand}} vs {{competitor}}: {{diff}} ({{year}})` | `MyRecon vs Sherlock: Username OSINT Compared (2026)` | 51 |
| B (alt) | `{{competitor}} Alternative: {{diff}} \| {{brand}}` | `Sherlock Alternative — No CLI, 560 Sites \| MyRecon` | 51 |
| C | `{{verb}} {{platform}} Account by Username` | `Find Instagram Account by Username` | 34* |
| C (long) | `{{platform}} Username Lookup & Profile Search` | `Instagram Username Lookup & Profile Search` | 42* |
| D | `How to {{task}} ({{year}} Guide) \| {{brand}}` | `How to Find Hidden Accounts (2026 Guide) \| MyRecon` | 51 |
| D (what-is) | `What Is {{topic}}? {{plain}}` | `What Is Username Enumeration? A Plain Guide` | 43* |
| E | `How to Delete Your {{platform}} Account ({{year}})` | `How to Delete Your TikTok Account (2026)` | 40* |
| E (broker) | `How to Remove Your Info from {{broker}} — {{year}}` | `How to Remove Your Info from Spokeo (2026)` | 42* |
| F | `{{brand}} for {{audience}}: {{benefit}}` | `MyRecon for Cybersecurity Analysts: Faster Triage` | 49 |
| G | `Free {{tool}} — {{brand}}` | `Free Username Availability Checker — MyRecon` | 44* |

\* = under the 50-char floor flagged in `SEO-REPORT.md` Phase 2.3. **The
generator must pad, not accept** — see §2.5 fallback ladder. Example pad:
`Find Instagram Account by Username (Free Check)` = 47… still short →
append qualifier: `Find Instagram Account by Username — Free 560-Site Scan`
= 61 ✗ → drop suffix → `Find Instagram Account by Username | MyRecon` = 45.
The ladder resolves this automatically; see the code.

### 2.3 Description templates (140–160 chars)

Structure law: **`[What it is] + [proof/specific] + [CTA verb]`.** Never two
sentences that could open any other page on the site.

| Cluster | Template | Example (chars) |
|---|---|---|
| B | `Compare {{brand}} with {{competitor}} on platform coverage, speed, setup and cost. Benchmarked {{number}}-site sweep, no terminal required. See the matrix.` | `Compare MyRecon with Sherlock on platform coverage, speed, setup and cost. Benchmarked 560-site sweep, no terminal required. See the matrix.` (141) |
| C | `Run a {{platform}} username lookup across {{number}} sites. See profile URL, evidence type and false-positive risk, then sweep every other platform for the same handle.` | (157) |
| D | `A practical guide to {{task}}: the manual technique, the checks that catch errors, and where automation saves an hour of clicking. With examples.` | (146) |
| E | `Delete your {{platform}} account step by step — plus what still shows up afterward. Free scan finds where else your profile is still exposed.` | (143) |
| E (broker) | `Remove your personal info from {{broker}} with the current opt-out steps. Then check the other {{number}} sites still listing your name, phone and address.` | (154) |
| F | `How {{audience}} use {{brand}} for cross-platform entity resolution: faster triage, documented evidence, exportable reports. See the workflow.` | (144) |
| G | `Free {{tool}}. Enter a handle and get instant results — no signup. Unlock the full {{number}}-platform report with one free account.` | (131)* |

\* padded in code to ≥140 with the platform qualifier clause.

### 2.4 The generator (drop-in Node, matches existing script style)

```js
/* metadata.js — title/description builder with a tiered fallback ladder.
 * Same principle as the breach generator: the template lives here, never in
 * the output. Validation failures throw, so a bad title cannot ship. */

const SITE = "MyRecon";
const VERBS = ["Find", "Locate", "Check", "Search", "Trace", "Audit", "Map", "Sweep"];
const hash = (s) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 0);
const verbFor = (slug) => VERBS[hash(slug) % VERBS.length];
const len = (s) => [...s].length;              // count code points, not bytes

function buildTitle(cluster, vars) {
  const slug = vars.slug;
  const ladder = {
    lookup: [
      `${verbFor(slug)} ${vars.platform} Account by Username`,
      `${vars.platform} Username Lookup & Profile Search`,
      `${vars.platform} Account Finder — Check Any Handle`,
      `${vars.platform} Username Search | ${SITE}`,
    ],
    vs: [
      `${SITE} vs ${vars.competitor}: ${vars.diff} (2026)`,
      `${vars.competitor} Alternative: ${vars.diff} | ${SITE}`,
      `${vars.competitor} vs ${SITE} — Compared (2026)`,
    ],
    guide: [
      `How to ${vars.task} (2026 Guide) | ${SITE}`,
      `${vars.topic} Explained: ${vars.plain} | ${SITE}`,
      `How to ${vars.task} — Step-by-Step | ${SITE}`,
    ],
    delete: [
      `How to Delete Your ${vars.platform} Account (2026)`,
      `Delete Your ${vars.platform} Account: Full Steps`,
      `${vars.platform} Account Deletion Guide (2026) | ${SITE}`,
    ],
  }[cluster];

  for (const candidate of ladder) {
    const n = len(candidate);
    if (n >= 50 && n <= 60) return candidate;   // the window SEO-REPORT set
  }
  throw new Error(`${slug}: title ladder exhausted (${ladder.map(len)})`);
}

function buildDescription(cluster, vars) { /* ...same ladder, gate 140–160... */ }

/* Build-time assertions — fail the build, never ship a bad head. */
function assertHead({ url, title, description, allTitles, allDescs }) {
  if (len(title) < 50 || len(title) > 60) throw new Error(`${url}: title ${len(title)}`);
  if (len(description) < 140 || len(description) > 160) throw new Error(`${url}: desc ${len(description)}`);
  if (allTitles.has(title)) throw new Error(`${url}: duplicate title`);
  if (allDescs.has(description)) throw new Error(`${url}: duplicate description`);
}

module.exports = { buildTitle, buildDescription, assertHead };
```

### 2.5 Validation gates (run in CI before deploy)

| Gate | Rule | Failure action |
|---|---|---|
| Title length | 50–60 chars, code points | build fails |
| Description length | 140–160 chars, no mid-word cut | build fails |
| Title uniqueness | global set across all pages | build fails |
| Description uniqueness | global set (cluster-level: must differ by ≥40% token overlap) | build fails |
| Canonical host | `https://www.myrecon.xyz` only, never apex | build fails |
| H1 count | exactly 1 | build fails |
| JSON-LD parse | every block parses; required props present | build fails |
| Orphan check | every page ≥1 inbound internal link from an indexable page | build fails |
| Broken internal links | crawl local build | build fails |
| Keyword cannibalisation | one `primary_keyword` per URL across the site | warn → manual |

The cannibalisation gate is the one that matters for Cluster C: `Find
Instagram Account by Username` (Cluster C) and `Instagram Privacy Self-Audit`
(existing blog post) must never be assigned the same `primary_keyword`.

---

## 3. Deliverable 3 — High-converting page layout specifications

### 3.1 Tool comparison layout (`/vs/*.html`)

```
┌─────────────────────────────────────────────────────────────────┐
│ H1: MyRecon vs Sherlock: Username OSINT, Compared               │
│ Meta: 45-word standfirst — who each tool is for, one sentence   │
│ [TOC] Overview · Matrix · Speed · Setup · Pricing · Verdict      │
├─────────────────────────────────────────────────────────────────┤
│ §1 Quick verdict (≤80 words, above the fold, answers the        │
│   query immediately — this is the snippet bait)                 │
│   "Sherlock is free and scripted; MyRecon is the no-CLI path    │
│    to the same enumeration with evidence scoring."              │
├─────────────────────────────────────────────────────────────────┤
│ §2 FEATURE COMPARISON MATRIX  (table, 8–12 rows, real values)   │
│   | Capability        | MyRecon | Sherlock |                     │
│   | Platforms         | 560     | 400+*    |  ← *cite source    │
│   | Evidence scoring  | ✓       | ✗        |                     │
│   | False-positive... | per-plat| none     |                     │
│   | Setup             | none    | python3  |                     │
│   | GUI / report      | ✓       | ✗        |                     │
│   | Output format     | HTML/CSV| terminal |                     │
│   | Maintenance       | managed | self-fix |                     │
│   → marked up as HTML <table> (never an image), each row a      │
│     matching visible <tr> for Table JSON-LD where eligible      │
├─────────────────────────────────────────────────────────────────┤
│ §3 SPEED BENCHMARK (original data — the differentiator)         │
│   Same handle, same network, 3 runs, median:                    │
│   MyRecon 560-site sweep: 8.4s · Sherlock 400-site: 41.2s       │
│   Method note published (honesty = E-E-A-T + link bait)         │
├─────────────────────────────────────────────────────────────────┤
│ §4 SETUP & WORKFLOW                                             │
│   Sherlock: git clone → pip install → python sherlock user →    │
│             read terminal, verify manually                      │
│   MyRecon: paste handle → evidence-scored report → export       │
│   Code block (CLI variant) for the audience that wants both     │
├─────────────────────────────────────────────────────────────────┤
│ §5 WHERE SHERLOCK WINS (yes, say it — credibility + wins        │
│   featured-snippet "is sherlock free" queries)                  │
├─────────────────────────────────────────────────────────────────┤
│ §6 PRICING SIDE BY SIDE                                         │
├─────────────────────────────────────────────────────────────────┤
│ §7 VERDICT + CTA                                                │
│   [Run a free 560-site sweep]  [See pricing]                    │
│   "No signup for the first 100 platforms."                      │
├─────────────────────────────────────────────────────────────────┤
│ §8 FAQ (4 Q&As, visible on page → FAQPage JSON-LD)              │
│   "Is there a Sherlock alternative with a GUI?"                 │
│   "Does MyRecon do everything Sherlock does?"                   │
│   "Is Sherlock still maintained?"                               │
│   "Can I run both?"                                             │
├─────────────────────────────────────────────────────────────────┤
│ Related: [vs Maigret] [vs Social Searcher] [Username OSINT guide]│
│ Breadcrumb: Home / Compare / MyRecon vs Sherlock                │
└─────────────────────────────────────────────────────────────────┘
```

**Value proposition line (no-code CLI alternative), used verbatim in §1 and §7:**
> "Sherlock tells you what exists. MyRecon tells you what it means — 560
> platforms, evidence-scored, no terminal, no Python, no maintenance."

**Conversion rule:** the primary CTA appears three times (quick verdict,
§4, §7) and always states what is free.

---

### 3.2 Account deletion & privacy guide layout (`/delete/*.html`)

```
┌─────────────────────────────────────────────────────────────────┐
│ H1: How to Delete Your Instagram Account (2026)                 │
│ Standfirst + "Last verified: 12 Sep 2026" (freshness signal)    │
│ [TOC] Before you start · Steps · Mobile · Desktop · What survives│
├─────────────────────────────────────────────────────────────────┤
│ §1 BEFORE YOU START (2–3 bullets)                               │
│   • Download your data (Settings → Your activity → Download)    │
│   • Deactivate first if you might return                        │
│   • Note: deletion is irreversible after 30 days                │
├─────────────────────────────────────────────────────────────────┤
│ §2 HOW TO DELETE — numbered steps (7–10), each:                 │
│   1. Open Settings → Accounts Center → Personal details         │
│   2. → Account ownership and control → Deactivation or deletion │
│   ...  (mobile path AND desktop path as separate H3s)           │
│   → marked up HowTo JSON-LD: name, total_time, step[n] w/ text  │
├─────────────────────────────────────────────────────────────────┤
│ §3 DELETION vs DEACTIVATION callout box                         │
│   (links to your existing blog post — no duplication)           │
├─────────────────────────────────────────────────────────────────┤
│ §4 WHAT STILL SHOWS UP AFTER DELETION                           │
│   • Cached copies in search results (→ link /delete/google-results-removal) │
│   • Data broker copies (→ link /delete/data-brokers/)           │
│   • Breach records — deletion never removes these (→ link /breaches/) │
│   • Old screenshots / third-party reposts                       │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ⚠ CONTEXTUAL PITCH BLOCK (unique to this template)         │ │
│ │ "Deleting one account doesn't audit the rest of you.       │ │
│ │  Your handle likely exists on other platforms — and         │ │
│ │  brokers may still list your name and phone."              │ │
│ │ [Scan my footprint free →]  [See removal service →]        │ │
│ │ copy variant rotated per platform + per broker record      │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ §5 FAQ (4: reactivation, message history, business accounts,     │
│   how long until it's gone from search) → FAQPage JSON-LD       │
├─────────────────────────────────────────────────────────────────┤
│ Related: [3 sibling deletions] [data-broker opt-out hub]         │
│          [reduce your digital footprint guide]                   │
└─────────────────────────────────────────────────────────────────┘
```

**Pitch block copy rotations (4 minimum, selected by `hash(slug)`):**
1. "Deleting one account doesn't audit the rest of you…"
2. "Your handle probably didn't die with this account. Free scan: 560 sites."
3. "Broker listings survive account deletion. Check what else is exposed."
4. "You removed the account. Did you remove the copies? Scan for residuals."

**Broker variant difference:** the pitch flips from *scan* to *service* —
"Opting out of 14 brokers one form at a time takes an afternoon. Our removal
service handles the rest."

---

### 3.3 How-to OSINT guide layout (`/guides/*.html`)

```
┌─────────────────────────────────────────────────────────────────┐
│ H1: How to Find Hidden Accounts With a Username                 │
│ Standfirst (40–60 words) · reading time · author/organization   │
│ [TOC] 6 sections                                                │
├─────────────────────────────────────────────────────────────────┤
│ §1 WHAT YOU'RE ACTUALLY DOING (why handle reuse links accounts) │
│ §2 THE MANUAL TECHNIQUE — honest, complete, works without us:   │
│   • Handle-variation list (john_doe, john.doe, johndoe…)        │
│   • Direct URL probes per platform + status-code reading        │
│   • Search-engine operators (site:reddit.com "john_doe")        │
│   • Avatar reverse-image correlation                            │
│   → links to existing /guides/what-http-responses-reveal.html   │
│ §3 WHERE MANUAL BREAKS DOWN: 40+ platforms × 5 variants = 200+  │
│   probes, rate limits, login walls, false positives             │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ AUTOMATION BRIDGE (mid-article, after the manual value)     │ │
│ │ "Same workflow, 560 platforms, evidence-scored:             │ │
│ │  [Run a free sweep] — first 100 platforms, no signup."      │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ §4 VERIFY BEFORE YOU ACT (link verify-an-osint-finding.html —   │
│   matching ≠ identity; the trust differentiator)                │
│ §5 FALSE POSITIVES & FAILURE MODES (link why-username-checkers…)│
│ §6 ETHICS & LAWFUL USE — authorised research only, own-data     │
│   audits, no stalking; mirrors /terms.html                     │
├─────────────────────────────────────────────────────────────────┤
│ FAQ (4–5) → FAQPage · HowTo JSON-LD where steps are the page    │
│ Related: 3 guides + 1 platform page + 1 comparison              │
└─────────────────────────────────────────────────────────────────┘
```

**Length & shape:** 1,400–2,200 words, 6 H2s, 2 CTA placements (never above
the manual technique — earn the conversion first), 3+ in-body internal links,
1 external authority link.

### 3.4 Platform lookup page layout (`/find/*.html`) — bonus spec

Hero (H1 + live lookup input pre-wired to that platform) → Platform facts
table (URL pattern, API availability, response semantics, false-positive
risk) → "What a found profile shows" → "How we verify the match" (evidence
classes) → false-positive warning → **sweep CTA** ("check this handle on 559
other sites") → related platform chips (3) → guide link → FAQ (4) →
breadcrumb. Schema: `WebApplication` + `BreadcrumbList` + `FAQPage`.

### 3.5 Shared conversion furniture

- **Sticky CTA bar** on Clusters B/C/E only: dismissible, never obscures
  content on mobile (tap-target rules from the audit: ≥44×44).
- **Every CTA states the free boundary** — "first 100 platforms", "no signup".
- **End-of-page related block:** 3 contextually rotated links (reuse the
  rotating sibling window from `build-breaches.js`; never `.slice(0,3)`
  static — that produced the 1-inbound-link bug already fixed).

---

## 4. Deliverable 4 — Programmatic content generation strategy

### 4.1 Architecture: one generator per cluster, one record per page

Mirror the proven pattern (`build-breaches.js`, `build-blog.js`):

```
frontend/
├── content/
│   ├── platforms.seo.json      ← SEO layer for the top-55 allowlist
│   ├── comparisons.seo.json    ← 30 competitor records
│   ├── deletion.seo.json       ← 42 deletion/broker records
│   ├── personas.seo.json       ← 8 records
│   └── tools.seo.json          ← 6 records
├── scripts/
│   ├── metadata.js             ← §2.4 title/description ladder
│   ├── build-lookup.js         ← generates /find/*.html
│   ├── build-vs.js             ← generates /vs/*.html
│   ├── build-delete.js         ← generates /delete/*.html
│   ├── build-personas.js
│   ├── build-tools.js
│   ├── qa-gate.js              ← §4.5, runs before sitemap
│   └── build-sitemap.js        ← existing; discovers new dirs automatically
└── data/platforms.json         ← generated lookup data (already exists)
```

**Rule (already learned the hard way):** generated output is disposable; a
content fix goes in the record or the template, never in
`/find/instagram.html`.

### 4.2 JSON schema — platform lookup record

Extends `backend/data/platforms_full.json` (runtime) with an SEO layer, so
the page can never contradict the tool:

```jsonc
{
  // runtime fields (existing, source of truth)
  "name": "Instagram",
  "url": "https://www.instagram.com/{username}/",
  "ok_status": 200,
  "category": "Social",
  "api": "https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
  "missing_status": 404,
  "echoes_handle": false,

  // SEO layer (new)
  "seo": {
    "slug": "instagram",
    "tier": 1,
    "primary_keyword": "instagram username lookup",
    "secondary_keywords": [
      "find instagram account by username",
      "check if instagram username is taken",
      "instagram profile search by username"
    ],
    "title": "Find Instagram Account by Username",        // optional override
    "title_ladder": "lookup",                             // picks §2.2 ladder
    "description_intro": "Run an Instagram username lookup across 560 sites.",
    "h1": "Find Any Instagram Account by Username",
    "unique_facts": [                                     // REQUIRED: ≥3 platform-specific strings
      "Instagram returns HTTP 200 for profile URLs but requires a session for some regions.",
      "The web_profile_info endpoint needs the X-IG-App-ID header.",
      "Handles can be re-registered after deletion, so a 404 today is not proof of absence."
    ],
    "false_positive_note": "Instagram soft-404s some suspended accounts.",
    "faq": [                                              // 4 per page, platform-worded
      { "q": "Can I look up an Instagram account without logging in?",
        "a": "Yes — MyRecon reads the public profile endpoint..." },
      { "q": "Why did the lookup return 'unknown' for a real account?",
        "a": "Rate limits and regional blocks..." },
      { "q": "Does an Instagram username search show private accounts?",
        "a": "It confirms the handle exists and shows public fields only..." },
      { "q": "How do I check this handle on other platforms?",
        "a": "Run a 560-platform sweep..." }
    ],
    "related_guides": ["username-osint-search", "why-username-checkers-report-fake-accounts"],
    "related_platforms": ["tiktok", "threads", "x-twitter"],
    "last_verified": "2026-09-20",                         // drives <lastmod>
    "status": "publish"                                   // publish | hold | noindex
  }
}
```

**Minimum-unique-content rule:** `unique_facts.length >= 3` and each
`unique_facts[i].length >= 80`. The QA gate rejects the record otherwise —
this is the single mechanical defence against the "55 identical pages"
failure that gets programmatic SEO sites penalised.

### 4.3 JSON schema — comparison record

```jsonc
{
  "competitor": "Sherlock",
  "slug": "sherlock",
  "category": "cli",
  "primary_keyword": "sherlock alternative",
  "diff_angle": "No CLI, evidence-scored",          // must differ per record
  "matrix": [
    { "row": "Platforms checked",  "myrecon": "560",      "them": "400+", "source": "README, Sep 2026" },
    { "row": "False-positive handling", "myrecon": "Per-platform evidence", "them": "None", "source": "—" },
    { "row": "Setup",              "myrecon": "None",     "them": "git + pip + python3", "source": "—" },
    { "row": "Report output",      "myrecon": "HTML/CSV", "them": "Terminal", "source": "—" },
    { "row": "Price",              "myrecon": "Free tier", "them": "Free (OSS)", "source": "—" }
  ],
  "benchmark": { "myrecon_seconds": 8.4, "them_seconds": 41.2, "runs": 3, "date": "2026-09-20" },
  "where_they_win": "Sherlock is fully offline-scriptable and free forever — if you live in a terminal, keep it.",
  "faq": [ /* 4 */ ],
  "source_urls": ["https://github.com/sherlock-project/sherlock"],
  "status": "publish"
}
```

**Field that prevents doorway-page classification:** every record must fill
`diff_angle`, `benchmark`, and `where_they_win`. QA rejects records missing
any of the three.

### 4.4 Markdown/front-matter schema — hand-written guides & deletion pages

Follow `content/blog/` exactly (JSON comment + body), extended:

```html
<!--
{
  "title": "How to Delete Your TikTok Account",
  "headline": "How to Delete Your TikTok Account",
  "description": "Delete your TikTok account step by step ...",
  "cluster": "delete",
  "primary_keyword": "how to delete tiktok account",
  "secondary_keywords": ["delete tiktok account permanently", "tiktok deactivation vs deletion"],
  "h1": "How to Delete Your TikTok Account",
  "audience": "individuals",
  "datePublished": "2026-09-27",
  "dateModified": "2026-09-27",
  "lastVerified": "2026-09-27",
  "author": { "name": "MyRecon Research", "url": "/founder.html" },
  "schema": ["HowTo", "FAQPage", "BreadcrumbList"],
  "ctaBlock": "pitch-variant-2",
  "internalLinks": ["/delete/", "/services.html", "/guides/reduce-your-digital-footprint.html"],
  "status": "publish"
}
-->
<h2>Before you start</h2> ...
```

Hand-written where accuracy drifts fast (platform settings paths change
quarterly) — that is exactly why `lastVerified` exists: a build can flag
records older than 180 days for human re-verification.

### 4.5 QA gate (`qa-gate.js`) — runs before `build-sitemap.js`

```js
// Fail the build on any of:
// 1. title/desc length or uniqueness (§2.5)
// 2. primary_keyword collision across all records
// 3. unique_facts < 3 or total page body unique-token ratio < 0.62
//    (shingle similarity vs every other page in the same cluster)
// 4. <2 internal inbound links from indexable pages
// 5. FAQ count < 3 or FAQ not visibly present in body (schema/body mismatch)
// 6. lastVerified older than 180 days on /delete/* and /find/* → warn
// 7. missing self-canonical or non-www canonical → fail
// 8. any <a href> that 404s in the local build → fail
```

**Duplicate-content defences (the explicit question):**

| Defence | Implementation |
|---|---|
| **Unique dynamic intros** | First paragraph assembled from `description_intro` + `unique_facts[0]` + `diff_angle`; never a shared boilerplate paragraph |
| **Rotating module order** | Section order seeded by `hash(slug)` across 3 legal permutations — same content, different composition, no two pages structurally identical |
| **Sentence-level variation pools** | 6+ phrasings per shared concept ("Run a sweep" / "Check every platform" / "Sweep 560 sites…"), selected deterministically |
| **Token-overlap threshold** | Build-time shingle check; >38% pairwise overlap within a cluster fails the build |
| **Canonicals** | Self-referencing on www; `rel=canonical` on any variant (e.g. `/find/twitter` and `/find/x-twitter` → **one** page, other 301s) |
| **Noindex thin tier** | Any record that cannot meet the content floor ships with `status: noindex` rather than publishing a doorway page — the site's `robots.txt`/meta path already supports this |
| **Dynamic FAQs** | Per-record, platform-worded, visibly rendered — never a shared FAQ block with the brand name swapped |
| **Real unique data** | Benchmarks, platform response semantics, last-verified dates: data competitors cannot copy |
| **Sitemap hygiene** | Cluster-split sitemaps; `lastmod` from `lastVerified`, not build time |
| **Internal link rotation** | Rotating sibling window (already proven in `build-breaches.js`) — prevents the "every page links to the same 3" pattern that reads as templated |
| **Staged publishing** | 15 → 35 → 55 pages with an indexed-rate checkpoint between cohorts |
| **IndexNow** | Existing `scripts/indexnow.js` submits only changed URLs per build (diff against previous build manifest) |

### 4.6 Programmatic FAQ + Schema.org plan

| Page type | JSON-LD |
|---|---|
| `/find/*` | `WebApplication`, `BreadcrumbList`, `FAQPage` |
| `/vs/*` | `WebPage`/`Article`?, `BreadcrumbList`, `FAQPage` (+ `Table` only where fully visible) |
| `/delete/*` | `HowTo` (steps visible), `FAQPage`, `BreadcrumbList` |
| `/guides/*` | `Article`, `BreadcrumbList`, `FAQPage` |
| `/solutions/*` | `Service` or `TechArticle`, `BreadcrumbList` |
| `/for/*` | `Service`, `BreadcrumbList` |
| `/tools/*` | `WebApplication`, `BreadcrumbList` |
| indexes | `CollectionPage`, `ItemList` (item names = real page titles) |

Golden rule from the existing audit: **nothing in JSON-LD that is not visible
on the page.** No invented ratings, no review schema, no aggregate stars.

---

## 5. Expansion — novel silos and untapped keyword clusters

Beyond the brief. These are the ones with the best difficulty/demand ratio for
this domain specifically.

### 5.1 `/solutions/` — the extraction-keyword silo (12 pages)

Your four core extraction keywords are **B2B/commercial queries with weak
competition** — nobody ranks a real product page for "cross-platform entity
resolution". Each page is a solution landing page (not a blog post), targeting
one concept, with the product as the answer:

| # | Slug | Primary keyword | Angle |
|---|---|---|---|
| 1 | `automated-data-extraction` | automated data extraction | vs manual copy-paste; structured output |
| 2 | `cross-platform-entity-resolution` | cross-platform entity resolution | 0–100 confidence score, factors shown |
| 3 | `pii-correlation` | pii correlation | email/phone/handle → one entity graph |
| 4 | `reverse-data-scraping` | reverse data scraping | "start from the identity, not the site" |
| 5 | `automated-reconnaissance` | automated reconnaissance | recon in seconds, evidence attached |
| 6 | `open-source-intelligence-api` | open source intelligence api | endpoints, rate limits, code samples |
| 7 | `digital-footprint-mapping` | digital footprint mapping | graph output, export |
| 8 | `username-enumeration-platform` | username enumeration tool | scale + evidence classes |
| 9 | `credential-exposure-monitoring` | credential exposure monitoring | breach + combolist correlation |
| 10 | `brand-impersonation-detection` | brand impersonation detection | trademark/watch use case |
| 11 | `people-search-api-alternative` | people search api | privacy-first, no PII resale |
| 12 | `investigation-graph-software` | investigation graph tool | existing graph feature as product |

Each page: definition block (snippet bait) → how the product does it (3
steps) → output sample → comparison mini-table vs manual → API snippet → CTA
→ FAQ (4). Cross-link every page to the guide with the same topic
(§1.5 rows 3–6) — **one transactional, one informational, never both on the
same URL.**

### 5.2 Impersonation & scam-detection silo (8 pages, Tier 2)

`/guides/find-fake-accounts-of-me.html`, `/for-individuals/verify-a-profile.html`,
plus per-platform: `/find/instagram-impersonation-check.html`-style pages are
**too close to Cluster C** — instead fold into guides: "How to Spot a Fake
Instagram Profile", "How to Report an Impersonator on TikTok/X/…". Query
intent is rising (romance-scam reporting) and it funnels to both the tool and
`/services.html`.

### 5.3 "Find accounts linked to X" silo (6 pages)

Sub-silo under `/guides/` that matches your extraction thesis literally:
`linked-to-email`, `linked-to-phone`, `linked-to-ip`, `linked-to-domain`,
`linked-to-credit-card-alias`(skip — sensitive), `linked-to-physical-address`.
Safe framing: **own-data audits and authorised investigation only.**

### 5.4 Developer/API docs silo (`/docs/`, 10 pages, phase 4)

`/docs/`, `/docs/username-lookup/`, `/docs/email-analysis/`,
`/docs/breach-check/`, `/docs/rate-limits/`, `/docs/authentication/`,
`/docs/errors/`, `/docs/sdks/`, `/docs/webhooks/`, `/changelog`.

Crawls beautifully, converts technical buyers, and gives `/api.html` a real
content moat. Query class: `username lookup api`, `osint api python`,
`reverse username api`.

### 5.5 Alternates & handle-variation programmatic pages (20, phase 4)

`/find/<platform>/username-ideas`-style pages are thin by default. Viable
version: **"Is `<handle>` taken across social media?"** public demo pages
generated from a curated set of 20 famous/reserved handles showing real
availability state — genuine tool output, not spun prose. Treat as a free-tool
growth loop, not SEO bulk.

### 5.6 Query-patterns worth owning that competitors ignore

- `sherlock not working` / `sherlock false positives` → comparison page FAQ
  section (support intent, converts hard).
- `how long does sherlock take` → benchmark section is the answer.
- `maigret vs sherlock` → hub `/vs/` cross-links both.
- `x platform down / username lookup not working` → status-style FAQ blocks on
  `/find/*` pages ("if Instagram returns 429…").
- `remove my phone number from internet` → `/delete/data-brokers/` hub + 14
  broker pages.
- `truecaller remove phone number` → your E3 special; enormous demand, thin
  competition in English.
- `is [tool] safe / legal` → `/vs/manual-osint.html` + `/legal-osint.html`;
  legality queries are unanswered across this niche.

### 5.7 What NOT to build (explicit negatives)

- **No geo-siloed pages** (`/osint-tools/london/`) — no physical-market intent;
  pure doorway pattern.
- **No per-variation page explosion** (`/find/instagram-private-account`,
  `/find/instagram-by-email`, …) — cannibalises Cluster C; fold as H2/H3 on
  the parent page.
- **No "track person X" query targeting** — stalking-intent keywords
  (`track my boyfriend's location`) are converting poison: policy risk on
  Google Ads/search quality, brand risk, and contradicts `/terms.html`
  (lawful use only). Frame everything as *own-data audit* or *authorised
  research*.
- **No AI-spun 800-word pages.** The QA floor in §4.5 is a build failure, not
  a guideline.
- **No adult/sensitive-platform lookup pages** in v1 — dual-use optics aren't
  worth the ranking.

---

## 6. Guardrails — compliance, ethics, and spam defence

1. **Positioning law:** every generated page must present MyRecon as an
   *ethical, authorised* alternative. Carry a consistent line: "For lawful
   OSINT and authorised research only" (already in `/terms.html`).
2. **Personal-data pages:** deletion/lookup pages target *your own data* or
   *authorised investigations*; no pages that instruct surveillance of third
   parties without lawful basis.
3. **Google spam policy fit:** this plan is built to the letter of the
   "scaled content abuse" and "site reputation" rules — unique data, staged
   rollout, content floor, noindex fallback, no expired-domain or
   pyramidal-link tricks.
4. **YMYL-adjacent hygiene:** cite primary sources (FTC, ICO, NIST, platform
   help centres) with outbound links; never restate broker/legal claims from
   memory.
5. **Copyright:** platform logos are hotlinked per existing convention; do
   not fabricate partner/endorsement claims in comparison pages.
6. **Data-source honesty:** benchmark numbers must be reproducible (method
   note published) — the same standard `SEO-REPORT.md` applied to itself.

---

## 7. Rollout plan and measurement

### Phase 1 — Weeks 1–6 (foundation, 98 pages)
1. `metadata.js` + `qa-gate.js` (before any page exists).
2. Cluster A: `/pricing.html`, `/api.html`, `/cli.html`, `/enterprise.html`,
   `/username-search.html`, `/email-investigation.html`.
3. Cluster B: `/vs/` hub + top 10 comparisons (Sherlock, Maigret, Social
   Searcher, Namechk, SpiderFoot, WhatsMyName, Namechk, Maltego, HIBP,
   Social Catfish).
4. Cluster C Tier 1: `/find/` hub + 15 platform pages.
5. Sitemap split into cluster files; submit; request indexing on hubs.

### Phase 2 — Weeks 7–16 (volume, +90 pages)
6. Cluster B remainder (20) + Cluster C Tier 2/3 (40) **conditional on ≥70%
   indexed rate in Phase 1 cohort**.
7. Cluster E: `/delete/` hub + 25 platform deletion guides + 14 broker
   opt-outs + 3 specials.
8. Cluster D: 17 new guides (staggered 2–3/week with the blog cadence).

### Phase 3 — Weeks 17–26 (segmentation, +25 pages)
9. Cluster F personas, Cluster G tools, Cluster C/E hubs cross-linked.

### KPIs (measured in GSC per cluster, not per page)

| Metric | Target at 90d | Target at 180d |
|---|---|---|
| Indexed / submitted, Cluster C | ≥70% | ≥90% |
| Indexed / submitted, Cluster E | ≥75% | ≥90% |
| Impressions (Cluster B+C) | +200% vs baseline | +600% |
| Pages with ≥1 query (GSC) | 60% of new pages | 80% |
| CTR on Comparison pages | ≥3.5% | ≥5% |
| Assisted signups from `/guides/*` + `/delete/*` | track in analytics | — |
| Cannibalisation flags (qa-gate) | 0 | 0 |

**Pruning rule:** at day 90 and 180, any new page with 0 impressions after
100+ days gets one of three actions — improve (add unique data), consolidate
(canonical into a sibling), or `noindex`. Never leave dead weight in a
programmatic cohort; Google's "site quality" read of a template is the
average, not the best page.

---

*Companion documents: `SEO-REPORT.md` (technical audit state),
`BACKLINK-STRATEGY.md` (link acquisition for Clusters G and D),
`LEGAL-CHECKLIST.md` (dual-use compliance).*

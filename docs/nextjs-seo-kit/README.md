# MyRecon programmatic SEO kit: 206 route records

The repository's live frontend is static HTML on Vercel; the root `app/` is an Android Gradle module. `build.py` still emits a separate Next.js migration preview under `generated-next-app/`. Production pages use `frontend/scripts/build-seo-pages.js`, which renders the same published JSON records as static HTML, and Vercel rewrites their extensionless canonical routes to those files. Keep the Next.js output separate; do not point `build.py` at `frontend/` or the repository root.

The inventory contains **5 core + 25 comparison + 80 platform + 49 guide + 47 privacy = 206** routes. `data/inventory.json` is the route and keyword list; `data/content/{kind}/{slug}.json` contains one strict-schema record per route, marked `published`. `data/pages.json` is an aggregate mirror for tools that expect one JSON array. The reviewer value `Codex editorial pass` identifies automated content generation, not independent human approval. Platform coverage and official privacy instructions can change, so verify those sources during editorial maintenance.

## 1. URL taxonomy

| Cluster name | URL slug pattern and count | Focus keywords | Search intent | Canonical logic |
|---|---|---|---|---|
| Core SaaS | `/`, `/features`, `/pricing`, `/enterprise-osint-api`, `/privacy-audit` (5) | OSINT social media lookup; digital footprint audit; legal OSINT API | Product and commercial | One clean URL per product job; self-canonical; redirect old `.html` URL only after migration |
| Comparisons | `/vs/{tool}` (25) | `{tool} alternative`, `MyRecon vs {tool}` | Commercial investigation | Self-canonical when independently useful; old `.html` routes require redirects before migration |
| Platform targets | `/find/{platform-purpose}` (80) | `{platform} username lookup`, `find {platform} profile` | Task and tool | Some routes are manual-only or describe distinct entities; confirm support and merge duplicate intent before public release |
| OSINT guides | `/guides/{question}` (49) | Public profile search, verification, privacy, and evidence workflows | Informational | Keep one answer per distinct question and preserve privacy boundaries |
| Privacy and deletion | `/privacy/{task}` (47) | Account deletion, broker opt-out, and search-result removal | Removal and self-audit | Official instructions change; verify each source and date before public release |

The complete current route list lives in `data/inventory.json`. It includes the requested platform routes such as `/find/threads-account`, `/find/roblox-user`, `/find/pinterest-board`, and `/find/kick-streamer`; broker routes such as `/privacy/delete-whitepages-info` and `/privacy/opt-out-radaris`; the six requested investigation guides; and comparisons for Epieos, OSINT Combine, and SEON.

### Collision and route rules

* The present `/vs/sherlock.html` and `/vs/maigret.html` are real pages. During a migration, publish the new route only when the old route permanently redirects; until then keep the current `.html` canonical. The same applies to existing guide topics. Do not emit two sitemap entries for one intent.
* Query terms, case variants, trailing slash variants, tracking parameters, and `www`/apex hosts must resolve or canonicalize to one URL. Search-result URLs and scan reports must be `noindex` and absent from the sitemap; user-submitted handles must never become indexable pages.
* A platform page exists only if the product really performs a supported public check or clearly labels a manual-only flow. The product must not suggest private-account discovery or guaranteed identity attribution.
* Privacy instructions and opt-out endpoints change. Their `reviewed_at` and official links are release gates, not freshness decoration.

## 2. Content contracts

The strict Draft 2020-12 JSON Schemas are in `schemas/`: [comparison](schemas/comparison.schema.json), [target](schemas/target.schema.json), [deletion](schemas/deletion.schema.json), [guide](schemas/guide.schema.json), and [core](schemas/core.schema.json). Each rejects unknown properties and requires substantive sections, a canonical slug, a CTA route, a review date, and three to five FAQs. The schemas require these additional fields:

| Page type | Required evidence-bearing fields | Publication rule |
|---|---|---|
| Comparison | `competitor`, `capabilities[]` with evidence URLs, `benchmark` object or `null`, `pros[]`, `cons[]`, `migration_note`, visible `faq[]` | Publish a numeric speed claim only when measured under the recorded method, sample size, and date. `null` renders a clear “no comparable benchmark” line. |
| Platform target | `platform.public_lookup`, `limitations`, `privacy_overview`, `false_positive_note`, `manual_steps[]`, `scan_trigger` | Verify the lookup is currently supported and that actual scan results distinguish found, absent, and unavailable. |
| Deletion | `official_help_url`, `steps[]`, `caveat`, optional `optout_link`, `audit_pitch`, visible `faq[]` | Recheck the official procedure on the target device and review what remains after deletion. No invented retention window. |

All five page types include visible FAQs and matching `FAQPage` JSON-LD. The shared `UsernameSearchInput` component routes a submitted handle into MyRecon's current username scanner using its supported deep link.

For production, `modified_at` changes only after a material content revision and `reviewed_at` records an actual manual source check. The current generated records have `status: "published"` and `reviewer: "Codex editorial pass"` to match the requested build input; this does not constitute human source verification. Check official links and product claims before deploying them. The builder enforces schema shape and unique URLs/titles; it cannot establish factual accuracy or search demand.

## 3. Complete Markdown page frameworks

The generator's TSX is a compact default presentation. These layouts define the full editorial and conversion contract for production UI. The copy below is reusable **structure**, with concrete example language; fill only evidence-backed fields. Each heading becomes a visible section. Never publish bracketed editorial notes.

### Comparison: `/vs/sherlock`

```md
# MyRecon vs Sherlock for username investigations

Sherlock suits analysts who want local, scriptable username checks. MyRecon
starts in a browser and gives users a review surface for public matches.
Neither tool can prove identity from a shared handle alone.

[Try a public username scan →](/)

## Quick verdict
Choose Sherlock when terminal automation and local output are central to your
workflow. Choose MyRecon when you want to begin a public footprint review in a
browser. For a high-stakes finding, open the source profile and corroborate it.

## Capability comparison
| Capability | MyRecon | Sherlock | Evidence |
|---|---|---|---|
| Start a check | Browser form | Local CLI command | Link to both product docs |
| Review a hit | Open public profile from result | Open URL from output | Link to actual UI/docs |
| Unavailable site | Labeled as unchecked when supported | Verify current output behavior | Tested trace + docs |

## Speed under the same conditions
If a benchmark exists, publish sample size, handle sample, network region,
tool versions, timeout, concurrency, run date, median, and p95 for both tools.
If it does not exist, say: “No comparable speed benchmark has been published.”
Do not use an unmeasured “faster than Sherlock” claim.

## Where Sherlock is stronger
Sherlock runs locally and can fit an analyst's existing command-line process.
Its output can be retained with other case notes. Check its current supported
sites and options against the official project before quoting a coverage count.

## Where MyRecon is stronger
Open a browser, submit the handle, then inspect linked public results without
installing Python. Keep unavailable checks visible as uncertainty. A result
card is a starting point for review, not a verified identity conclusion.

## Moving from a CLI workflow
Enter the same handle, compare linked public profiles, record uncertain checks,
and preserve the original result URLs. Keep existing scripts where they help.

## Frequently asked questions
### Does a shared username prove the same person owns both profiles?
No. Treat it as a lead and corroborate with independent public evidence.

### Can either tool reveal a private account?
They can report only what their supported public checks can establish.

[Try a public username scan →](/)
```

The actual page must show the exact FAQ text before emitting `FAQPage` JSON-LD. For this SaaS, FAQ markup is a machine-readable description, **not** a strategy that assumes Google FAQ rich results. A safe graph fragment is:

```json
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"Does a shared username prove the same person owns both profiles?","acceptedAnswer":{"@type":"Answer","text":"No. Treat it as a lead and corroborate with independent public evidence."}}]}
```

### Platform target: `/find/github-profile`

```md
# Find a public GitHub profile by username

A GitHub handle can lead to a public profile and activity. Start with the
visible source page; a matching string alone is not an identity match.

Username: [input, autocomplete off] [Run public footprint scan]
Help text: “We check supported public pages. Blocked and uncertain checks are
reported separately.”

## How to check manually
1. Search users on GitHub for the exact candidate handle.
2. Open the resolved profile and verify it is not an error or redirect.
3. Record the URL and observation date; compare independent public clues.

## What may be exposed
The account holder may expose a biography, avatar, location, website link,
and public repository activity. A repository can also contain details the
author did not intend to share. Private repositories are outside this check.

## False positives and blind spots
The same handle can belong to unrelated people on different services. A
renamed profile or organization account can also confuse a simple URL check.
Login walls and rate limits mean “unknown,” not “no account.”

## Scan across platforms
Use the real lookup component and show found / absent / unchecked states.
Link to the identity-verification guide and adjacent developer platforms.
```

The input should submit to the app's existing scan flow; adapt the form action in generated TSX during migration. Do not expose a username in server logs, analytics events, or indexed query URLs by default. A client-side event can initiate the authorized scan and update results without creating crawlable pages.

### Privacy and deletion: `/privacy/how-to-delete-reddit-account`

```md
# How to delete a Reddit account

Use Reddit's current Help Center instructions for your device and sign-in
method. Review data you want to save before confirming deletion.

## Before you start
Deleting the account does not delete posts or comments. Review and remove
those separately if that is part of your goal. Save any data you need first.

## Delete the account
1. On reddit.com, sign in and open Account Settings.
2. Scroll to Advanced and select Delete Account. On mobile, use Settings and
   the account-specific settings to reach Delete account.
3. Enter the required details, acknowledge that deletion is irreversible,
   and confirm. Follow Reddit's linked-login instructions if needed.

## What can remain public
Reddit says account deletion does not delete your posts or comments. Quotes,
search results, and copies elsewhere may still point to earlier activity.
Check each surface separately; closing one account does not close another.

## Scan where else your username or email is still exposed
Run a self-audit of supported public sources, open each match, and choose the
service-specific deletion or opt-out route. Label blocked checks as unknown.

[Run a public footprint audit →](/privacy-audit)
```

For a data broker, replace account settings steps with the **official** opt-out form and record any identity proof requested by that broker. Do not submit users' sensitive documents through MyRecon unless the product has a verified secure process for it.

## 4. Build and sitemap blueprint

```powershell
python -m pip install -r docs/nextjs-seo-kit/requirements.txt
python docs/nextjs-seo-kit/make_inventory.py
python docs/nextjs-seo-kit/make_content.py
python docs/nextjs-seo-kit/build.py
node frontend/scripts/build-seo-pages.js
node frontend/scripts/build-sitemap.js
```

The default Next.js build reads every JSON file under `data/content/`, requires at least 200 published records, and writes to `generated-next-app/`. It emits `app/{cluster}/{slug}/page.tsx`, `components/UsernameSearchInput.tsx`, and a migration-preview sitemap; it does not deploy that output. The static renderer mirrors the 206 records to `frontend/content/seo-pages/` for the standalone Vercel root, writes HTML into `frontend/`, and keeps the shared username search component connected to the live scanner. The sitemap builder uses each page's canonical URL. Vercel runs both scripts during its frontend build. The Next.js manifest and static-page manifest track only their own generated files. Sitemap protocol supports `<changefreq>` and `<priority>`, but they are not ranking controls; split the sitemap before it reaches 50,000 URLs.

Suggested Next.js integration:

```text
app/
  layout.tsx                  # shared nav, footer, metadataBase
  page.tsx                   # generated only if no existing homepage
  vs/sherlock/page.tsx       # generated comparison
  find/github-profile/page.tsx
  privacy/how-to-delete-reddit-account/page.tsx
public/sitemap.xml           # generated, never hand edited
```

If a route already has an authored `page.tsx`, use that file as the canonical source or exclude the generated record. Never let a generator overwrite an unrelated page. For larger datasets, a shared dynamic route with `generateStaticParams` and `generateMetadata` may reduce source-file churn; keep the same content validation and canonical rules. If using Next's `app/sitemap.ts`, remove `public/sitemap.xml` to avoid duplicate sitemap ownership.

## 5. Anti-duplicate and ranking strategy

1. **One distinct task per URL.** Compare intent, audience, and actual scan path. Merge `/find/reddit-profile` and `/find/reddit-username` unless each solves a different demonstrated task. Similar titles alone are not proof of distinct value.
2. **Unique evidence block.** A comparison needs a sourced capability matrix and honestly measured benchmark or explicit absence of one. A platform page needs the actual lookup behavior, privacy limits, and false-positive cases. A deletion page needs the current official procedure and a concrete post-deletion audit. Do not spin adjective variants of the same intro.
3. **Human review.** Require a named reviewer, source URLs, a date, and a screenshot or test trace in the editorial ticket. Check every official link and every product claim before publication. Re-review deletion pages when the UI changes, and comparisons when competitor releases alter capabilities.
4. **Canonical consistency.** `rel=canonical`, HTTP redirects, internal links, and sitemap must all indicate the same URL. Do not publish both `.html` and clean versions with self-canonicals. A sitemap is a canonical hint, not an indexing guarantee.
5. **Crawl graph.** Add `/vs/`, `/find/`, `/guides/`, and `/privacy/` hubs; link each child from its hub and to two or three contextually related pages. Keep live scan results and user-entered identifiers outside the crawl graph. Use real visible breadcrumbs and `BreadcrumbList` data only when the hierarchy is rendered.
6. **Structured data mirrors the page.** `Article` or `WebPage` plus visible FAQ when useful; do not add unsupported aggregate ratings, fabricated testing claims, or invisible answers. FAQ rich results are largely restricted on Google, and `HowTo` rich results are not a dependable growth lever. Structured data helps interpretation but cannot rescue thin content.
7. **Measure and prune.** Launch reviewed cohorts, inspect Search Console canonical selection, indexing, query intent, and engagement. Consolidate pages that receive the same queries or fail to provide distinct help. Treat ranking as an outcome to measure, never a guaranteed result of generating 100 URLs.

## Sources used for the blueprint

* [Google: build and submit a sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
* [Google: canonicalize duplicate URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
* [Google: spam policies, including scaled content abuse](https://developers.google.com/search/docs/essentials/spam-policies)
* [Google: helpful, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
* [Google: FAQ and HowTo search appearance changes](https://developers.google.com/search/blog/2023/08/howto-faq-changes)
* [Next.js: `generateStaticParams`](https://nextjs.org/docs/app/api-reference/functions/generate-static-params)

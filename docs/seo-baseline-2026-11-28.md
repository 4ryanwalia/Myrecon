# SEO baseline, 28 Nov 2026

Read on 28 Nov 2026 from Google Search Console (property `sc-domain:myrecon.xyz`, Search type Web, signed-in session in the in-app browser), the live site (curl), and `npm run audit:seo` on a clean worktree of origin/main at 58c19017. No paid tools.

**Read this first.** Almost all of the 28-day window (29 Oct to 25 Nov) comes from before the November 2026 core update finished, around 24 Nov. Since 24 Nov the site has had about 14 impressions a day, against 150 to 300 before. So every "position 6 to 21" figure below shows the site as it ranked before the update. Those pages were the site's best assets then. Nobody knows yet whether Google will rank them there again. Plan on that basis: upgrade the existing pages that held their positions, and build few new pages.

## 1. Performance

The latest 2 to 3 days lag, so windows end on 25 Nov unless marked otherwise.

| Window | Clicks | Impressions | CTR | Avg position |
|---|---|---|---|---|
| 3 months (26 Aug to 25 Nov) | 258 | 6.64K | 3.9% | 27.0 |
| 28 days (29 Oct to 25 Nov) | 191 | 4.65K | 4.1% | 26.6 |
| 1 to 19 Nov, per day | 4 to 12 | 118 to 303 | | 19.6 to 35.8 |
| 20 to 23 Nov, per day | 5 to 12 | 259, 148, 121, 96 | | 30.6 to 41.7 |
| 24 Nov | 1 | 4 | | 67.8 |
| 25 Nov | 1 | 13 | | 66.5 |
| 26 Nov (lagging) | 1 | 28 | | 50.0 |
| 27 Nov (lagging) | 0 | 11 | | 72.8 |

**After the update (24 to 27 Nov, page view).** Only 10 URLs had any impressions:
- the homepage: 49 impressions at 62.3
- /find/github-profile: 3 at 60.7
- /browser.html: 2
- 7 more URLs with 1 impression each

Every other page in the table below had none.

**Not a technical failure** (all checked 28 Nov):
- Manual actions: "No issues detected".
- Index: 254 indexed, stable.
- Crawl stats: 5.8K requests, 84% 200, 14% 301, 2% 404, average response 75 ms, "No problems" on both hosts.
- Sitemap: served as 200 `application/xml`, also with a Googlebot user agent.

Google's own Search Status Dashboard (read 28 Nov in `docs/seo-recovery-plan-2026-11-28.md`) dates the November 2026 core update from 10 Nov for 13 days 20 hours. It also preannounces a December 2026 core update.

### Generative AI features (GSC report, 28 days)

336 impressions. Top pages:

| Page | Impressions |
|---|---|
| / | 98 |
| /blog/best-data-breach-checkers.html | 35 |
| /find/github-profile | 23 |
| /find/instagram-account | 21 |
| /osint-tool-pricing.html | 19 |
| /blog/account-deletion-vs-deactivation.html | 18 |
| /blog/best-sherlock-alternatives.html | 12 |
| /blog/instagram-username-search.html | 11 |

The daily chart falls to 0 to 1 after 22 Nov.

### Countries (28 days)

| Country | Clicks | Impressions | CTR | Position |
|---|---|---|---|---|
| United States | 51 | 1,715 | 3.0% | 38.3 |
| India | 28 | 419 | 6.7% | 13.4 |
| United Kingdom | 13 | 290 | 4.5% | 36.9 |
| Brazil | 6 | 150 | 4.0% | 30.1 |
| Canada | 5 | 117 | 4.3% | 32.8 |
| Indonesia | 10 | 103 | 9.7% | 16.9 |
| Germany | 4 | 101 | 4.0% | 22.3 |
| Australia | 8 | 92 | 8.7% | 34.4 |

By impressions the top 5 are the US, India, the UK, Brazil and Canada. India's average position (13.4) is much better than the US (38.3). Most of India's impressions come from brand and long-tail queries, not from head terms.

### Queries (28 days)

545 queries had impressions. Most have 1 or 2, so the position of any single query is noise. The table below keeps the ones that carry a decision. Re-read the full list from GSC with the same date range (`start_date=20261029&end_date=20261125`) and 500 rows per page.

| Query | Clicks | Impressions | Position | Landing page | Note |
|---|---|---|---|---|---|
| myrecon | 23 | 39 | 1.9 | / , /about.html | brand |
| sherlock.xyz alternatives | 0 | 160 | 7.9 | /vs/sherlock, best-sherlock-alternatives | a different product (Sherlock the Web3 audit firm); not our intent |
| osint tools | 0 | 35 | 79.5 | best-free-osint-tools-for-investigators | head term, never near page 1 |
| insta recon | 3 | 26 | 6.3 | /find/instagram-account | |
| reverse username search | 0 | 24 | 47.0 | reverse-username-lookup, username-checker | |
| instagram osint | 1 | 22 | 20.6 | blog/instagram-osint-public-profile-guide | |
| siteinstagram.com username | 0 | 22 | 7.9 | blog/instagram-username-search | operator typo; weak intent |
| username lookup | 0 | 17 | 75.9 | several | |
| best osint tools | 0 | 15 | 37.8 | best-free-osint-tools-for-investigators | |
| osint instagram private account | 0 | 14 | 29.9 | instagram-osint guide | |
| username search | 0 | 13 | 79.0 | several | |
| osint app for android | 0 | 11 | 7.0 | best-osint-apps-for-android | real intent, near page 1 |
| deactivate vs delete question family | 0 | about 15 across 8 phrasings | 8 to 11 | account-deletion-vs-deactivation | real intent, near page 1 |
| sherlock / maigret family | 0 | about 13 across 5 phrasings | 4.8 to 11 | sherlock-vs-maigret-vs-myrecon | real intent, near page 1 |

## 2. Pages at positions 6 to 21 (28 days, live 200 with index only)

Each URL was checked live on 28 Nov with curl. URLs that now 308 are excluded:
- blog/reverse-username-lookup-guide
- blog/top-10-osint-tools
- guides/top-10-osint-tools-2026 and -2027
- browser.html
- guides/instagram-username-osint-tool
- guides/reverse-lookup-phone-number-free-osint
- guides/find-linked-email-addresses-from-username

/directory.html (237 impressions at 9.9) is excluded too: it has been `noindex` since 24 Nov.

"Real queries" lists that page's own GSC query table (`&page=!`), as impressions@position.

| Page | Impr | Pos | Real queries behind it | Leverage |
|---|---|---|---|---|
| /find/instagram-account | 181 | 9.6 | insta recon 25@6.2; instagram username search engine 8@24.6; osint instagram username 3@13.7 | High. Retitled 28 Nov from "Instagram OSINT & Public Username Lookup". See the freeze list |
| /vs/sherlock | 177 | 8.7 | sherlock.xyz alternatives 139@8.0 | **Low.** 79% of impressions are a different product |
| /blog/instagram-osint-public-profile-guide.html | 197 | 18.2 | instagram osint 22@20.6; osint instagram private account 14@30.4; osint instagram 9@26 | High, real intent |
| /blog/instagram-username-search.html | 140 | 18.0 | siteinstagram.com username 22@7.9; instagram search username 9@54.9 | Medium, the best query is an operator typo |
| /find/github-profile | 107 | 9.0 | how to search github profiles 2@9.5; github username lookup 1@12 | Medium, mostly anonymised queries |
| /blog/best-data-breach-checkers.html | 81 | 14.2 | long AI-style questions at 1 to 10 ("which consumer apps keep watch for stolen passwords?" 3@1.7) | Medium. These look like AI Mode fan-out queries, which is the second-biggest AI-report page |
| /blog/best-osint-apps-for-android.html | 76 | 13.1 | osint app for android 11@7.0; osint apps android 6@5.7; osint tools for android 6@26 | **High, real intent, owned app** |
| /blog/instagram-privacy-self-audit.html | 76 | 14.8 | privacy checks instagram 3@44 | Low |
| /blog/best-sherlock-alternatives.html | 65 | 6.7 | sherlock.xyz alternatives 21@7.1; sherlocq alternatives 3@9.3 | Low to medium, mostly wrong intent |
| /about.html | 55 | 7.0 | myrecon 29@3.5 | brand |
| /breaches/ | 45 | 14.7 | (anonymised) | low |
| /blog/find-your-own-old-accounts.html | 45 | 17.7 | how to find old accounts 4@63 | Low. Cannibalises delete-old-online-accounts |
| /osint-tool-pricing.html | 37 | 6.3 | (anonymised) | Medium; 19 AI-feature impressions |
| /find/discord-user | 34 | 10.9 | (anonymised) | Medium. The new /discord-id-lookup.html tool now serves this intent |
| /blog/sherlock-vs-maigret-vs-myrecon.html | 34 | 7.4 | sherlock / maigret 2@5; sherlock and maigret 2@11 | **High, real intent** |
| /guides/username-osint-search.html | 29 | 14.7 | (anonymised) | low |
| /blog/how-to-find-someones-social-media-accounts.html | 27 | 8.7 | (anonymised) | low |
| /guides/myrecon-black-friday-sale-2026 | 26 | 5.5 | brand + sale | seasonal |
| /founder.html | 23 | 9.5 | aryan walia 6@10.5 | brand |
| /blog/social-media-osint-tools.html | 21 | 13.0 | (anonymised) | low |
| /guides/brand-impersonation-monitoring | 15 | 12.3 | 1 query | low |
| /blog/report-social-media-impersonation.html | 13 | 12.7 | 1 query | low |
| /whatsmyname-alternatives.html | 12 | 20.9 | whatsmyname alternative 1@53 | Medium. Holds the archival fact; ranked #4 for "is whatsmyname still maintained" on 18 Nov |
| /guides/check-email-data-breach.html | 12 | 20.6 | data breach check 1@69 | low |
| /blog/social-media-username-search.html | 11 | 9.8 | (anonymised) | low |
| /blog/breach-date-vs-disclosure-date.html | 10 | 8.9 | (anonymised) | low |
| /blog/account-deletion-vs-deactivation.html | 183 | 21.9 | the deactivate-vs-delete family at 8 to 11; "account deletion and retention" 10@64 | **High, real intent** (just outside 21 on average, inside it for its real queries) |

Breach archive pages also sit in this band on 1 to 12 impressions each: hottopic, rockyou-2009, bvd, uber-2022, burgerkingrussia, cdek and crunchbase. There is too little evidence to act on.

**The pages that matter.** These five had real-intent queries in the 6 to 21 band before the update:
- best-osint-apps-for-android
- account-deletion-vs-deactivation
- sherlock-vs-maigret-vs-myrecon
- instagram-osint-public-profile-guide
- /find/instagram-account

Two more carry dated or original facts and get AI-feature impressions:
- osint-tool-pricing
- whatsmyname-alternatives

## 3. Indexing (GSC Page indexing, read 28 Nov)

| State | Count |
|---|---|
| Indexed | 254 |
| Page with redirect | 178 |
| Discovered, currently not indexed | 42 |
| Crawled, currently not indexed | 11 (validation: Failed) |
| Alternate page with proper canonical | 2 |
| Not found (404) | 1 |

**Sitemap cross-check.** The live sitemap.xml and the 7 child sitemaps both list the same 237 URLs (the diff is empty). Of those 237:
- 193 are indexed.
- 28 sit in a not-indexed bucket.
- **16 appear in no bucket.** This is the closest the report gets to "URL is unknown to Google". The bucket lists lag, so a page requested on 25 or 26 Nov may already be known.

61 indexed URLs are no longer in the sitemap. They are retired URLs that now 308, and they will drop out on their own.

**Crawled, currently not indexed:** 4 HTML pages plus 7 data files. Ignore the data files, which are JSON, CSV and a README.
- /reverse-email-lookup.html (crawled 25 Nov)
- /is-myrecon-legit.html (22 Nov)
- /guides/what-http-responses-reveal and /guides/how-to-spot-phishing (15 Oct, old extensionless URLs)

Google read these pages and declined to index them. That calls for content work, not a resubmit.

**Discovered, currently not indexed (42):**
- **Blog:** genesys-october-2026-security-incident, irhythm-october-2026-data-breach-notice, username-reuse-privacy
- **Breach pages (17):** addi, advanceautoparts, canadiantire, castlerat, doublecounter, harvard, mckesson, neogen, notsocradar, pdl, prosper, sberspasibo, suno, synthient credential stuffing, synthient stealer log, tokopedia, wattpad, youhack
- **Case files (13):** aadhaar-exposures-2018, cambridge-analytica-2018, clearview-ai-2020, ebay-2014, equifax-2017, home-depot-2014, irhythm-2026, jpmorgan-2014, lastpass-2022, mgm-resorts-2023, morrisons-2014, twilio-0ktapus-2022, uber-2016
- **Guides:** people-search-apps-what-they-find, remove-personal-info-from-search, search-operators-osint, sim-swap-attacks, social-media-privacy
- **Other pages:** /username-sweep-vs-deep-search.html
- **Video pages, now noindex:** videos/digital-footprint-checker, videos/instagram-username-search

**In the sitemap, in no bucket (16):**
- **Tool page:** /discord-id-lookup.html
- **Guides:** bluesky-at-protocol-osint, data-breach-settlement-claims, delete-github-account, discord-id-creation-date, document-metadata-forensics-osint, india-data-breaches, mcp-osint-agentic-recon, reddit-username-lookup, reverse-gamertag-lookup, telegram-username-search
- **Other pages:** /osint-glossary.html, /upcoming-osint-tools-2027.html, /vs/epieos, /vs/maigret, /vs/namechk

### Sitemaps

| Sitemap | Submitted | Last read | Status | Discovered |
|---|---|---|---|---|
| sitemap-index.xml | 25 Nov | 25 Nov | Success | 256 |
| sitemap.xml | 25 Nov | (blank) | **Couldn't fetch** | 0 |
| sitemap-core.xml | 20 Oct | 22 Nov | Success | 44 (12 videos) |
| sitemap-blog.xml | 20 Oct | 26 Nov | Success | 39 |
| sitemap-breaches.xml | 20 Oct | 24 Nov | Success | 122 |
| sitemap-guides.xml | 20 Oct | 26 Nov | Success | 47 |
| sitemap-find.xml | 20 Oct | 26 Nov | Success | 4 |
| sitemap-vs.xml | 20 Oct | 27 Nov | Success | 7 |
| sitemap-privacy.xml | 20 Oct | 23 Nov | Success | 1 |

The live sitemap.xml returns 200 `application/xml; charset=utf-8` at 44,629 bytes, the same to a Googlebot user agent, with no redirect and no `noindex`. It lists the same 237 URLs as the index. The "Couldn't fetch" status therefore costs no coverage: every URL in it is also read through sitemap-index.xml. The counts GSC shows (256, 122 and so on) come from older reads and are higher than today's live 237, because 19 archive pages were noindexed and dropped on 25 Nov.

## 4. Audit (`node scripts/seo-audit.js --gsc <28-day pages CSV>`, origin/main 58c19017)

- **Cannibalised families (audit):**
  - "username search / checker": /, /username-checker.html, /vs/sherlock
  - "best username search tools": best-username-search-apps, best-username-search-tools, sherlock-vs-maigret
  - "digital footprint checker": / and /digital-footprint-checker.html
- **Cannibalised in GSC, not flagged by the audit:**
  - "osint tools": /free-osint-tool.html (159 impressions at 67.6) vs blog/best-free-osint-tools-for-investigators (239 at 74.6)
  - "find/delete old accounts": blog/delete-old-online-accounts vs blog/find-your-own-old-accounts (title overlap 0.67)
  - Instagram: /find/instagram-account, blog/instagram-username-search and blog/instagram-osint-public-profile-guide all draw "instagram username/osint" queries
- **Thin pages:** 0. Duplicate titles and descriptions: 0. Sitemap and canonical mismatches: 0. Redirecting sitemap URLs: 0. Internal links through a redirect: 0. Orphans: 0.
- **Slow answers** (H2 whose first paragraph runs over 70 words): 75 sections on 54 pages.
  - Most are breach case files.
  - Pages that rank or matter: account-deletion-vs-deactivation (1), sherlock-vs-maigret-vs-myrecon (1), guides/india-data-breaches (2), guides/reverse-gamertag-lookup (2), guides/what-is-osint (2), guides/discord-id-creation-date (1), guides/delete-github-account (1).
- **Entity salience:** "MyRecon" is in the title and first paragraph of every key tool page. It is not in the H1 of /, /username-checker.html, /reverse-username-lookup.html, /digital-footprint-checker.html or /free-osint-tool.html. That is by design: the H1 states the query and the title carries the brand.
  - Homepage `sameAs`: GitHub repo and Play listing only.
- **Long pages:** 193. Question-shaped H2s: 176. FAQPage: 120. Dataset: 4. A dated fact in the text: 104.

## 5. Freeze list (no retitle, merge or redirect until the 9 Dec re-judge)

Every URL with impressions in the 28-day page table is frozen. Three items are already wrong or doubtful. They should go to the post-9-Dec queue with their query data, and nothing should change now:

1. **/find/instagram-account title.** From 20 Oct to 27 Nov it was "Instagram OSINT & Public Username Lookup | MyRecon", and it earned all of its 28-day data under that title. Commit f7704535 changed it on 28 Nov to "Instagram Signed-Out Account Visibility Guide | MyRecon", which drops both "OSINT" and "username lookup". Its queries: insta recon 25@6.2, instagram username search engine 8@24.6, osint instagram username 3@13.7.
2. **/guides/reverse-lookup-phone-number-free-osint** 308s to /guides/digital-footprint-audit-checklist. It had 10 impressions at 15.4 and 3 clicks, and its phone-lookup intent does not match a footprint checklist. The better target is /blog/reverse-phone-lookup-and-osint-techniques.html.
3. **/guides/find-linked-email-addresses-from-username** 308s to /guides/search-usernames-across-social-platforms. It had 18 impressions at 7.3 and 1 click. The better target may be /reverse-email-lookup.html.

## 6. Indexing request queue

- Google needs one request per URL, so URLs never requested come first.
- The quota ran out after 4 to 7 requests a day on 25 and 26 Nov.
- **Already requested (do not repeat):**
  - 25 Nov: india-data-breaches, developers, username-sweep-vs-deep-search, people-search-apps-what-they-find, remove-personal-info-from-search, search-operators-osint, sim-swap-attacks, reverse-email-lookup
  - 26 Nov: reverse-gamertag-lookup, social-media-privacy, username-reuse-privacy, case-files/equifax-2017
  - 28 Nov: discord-id-lookup

Queue, in order:

| # | URL | State | Why first |
|---|---|---|---|
| 1 | /guides/telegram-username-search.html | not in any bucket | 1K to 10K a month (Keyword Planner, 28 Nov) |
| 2 | /guides/reddit-username-lookup.html | not in any bucket | 1K to 10K a month |
| 3 | /vs/maigret | not in any bucket | "maigret" 10K to 100K a month |
| 4 | /guides/discord-id-creation-date.html | not in any bucket | sits next to the Discord tool |
| 5 | /guides/delete-github-account.html | not in any bucket | sourced GitHub Docs facts |
| 6 | /vs/namechk | not in any bucket | "namechk" 10K to 100K a month |
| 7 | /vs/epieos | not in any bucket | "epieos" 10K to 100K a month |
| 8 | /guides/data-breach-settlement-claims.html | not in any bucket | |
| 9 | /breaches/case-files/aadhaar-exposures-2018.html | Discovered | India relevance |
| 10 | /breaches/case-files/lastpass-2022.html | Discovered | |
| 11 | /breaches/case-files/mgm-resorts-2023.html | Discovered | |
| 12 | /blog/genesys-october-2026-security-incident.html | Discovered | |

Held back on purpose:
- /upcoming-osint-tools-2027.html, /osint-glossary.html (its typo table), bluesky, mcp-osint and document-metadata. These are the 11-26 and 11-27 additions that `docs/seo-recovery-plan-2026-11-28.md` flags as trend-chasing. Re-judge them on 9 Dec before spending quota on them.
- /reverse-email-lookup.html and /is-myrecon-legit.html (Crawled, not indexed). Google read them and declined, so content comes first.

Request results are logged in section 7 as they happen.

## 7. Request log

| Date | URL | GSC state before (live URL Inspection) | Result |
|---|---|---|---|
| 28 Nov | /guides/telegram-username-search.html | Discovered, currently not indexed. Referring page: none detected | Requested |
| 28 Nov | /guides/reddit-username-lookup.html | Discovered, currently not indexed. Referring page: none detected | Requested |
| 28 Nov | /vs/maigret | URL is unknown to Google | Requested |
| 28 Nov | /guides/discord-id-creation-date.html | URL is unknown to Google | Requested |
| 28 Nov | /guides/delete-github-account.html | Discovered, currently not indexed | Requested |
| 28 Nov | /vs/namechk | Page with redirect (last crawl saw the old redirect; live today) | Requested |
| 28 Nov | /vs/epieos | Discovered, currently not indexed | Requested |
| 28 Nov | /guides/data-breach-settlement-claims.html | Discovered, currently not indexed | Requested |
| 28 Nov | /breaches/case-files/aadhaar-exposures-2018.html | URL is unknown to Google | Requested |
| 28 Nov | /breaches/case-files/lastpass-2022.html | URL is unknown to Google | Requested |
| 28 Nov | /breaches/case-files/mgm-resorts-2023.html | URL is unknown to Google | **Quota exceeded**: request on the next run |

The quota ran out after 10 requests today, 11 including the Discord tool requested earlier on 28 Nov.

**Next run queue** (updated after the 28 Nov release, commit 9e666dcd):

1. /breaches/case-files/mgm-resorts-2023.html
2. /blog/genesys-october-2026-security-incident.html
3. These 11 pages, upgraded on 28 Nov and already indexed. Request a recrawl so Google sees the new body:
   - /blog/best-osint-apps-for-android.html
   - /blog/account-deletion-vs-deactivation.html
   - /blog/sherlock-vs-maigret-vs-myrecon.html
   - /blog/instagram-osint-public-profile-guide.html
   - /find/github-profile
   - /whatsmyname-alternatives.html
   - /osint-tool-pricing.html
   - /blog/best-data-breach-checkers.html
   - /reverse-email-lookup.html
   - /username-checker.html
   - /reverse-username-lookup.html
4. The remaining Discovered case files: cambridge-analytica-2018, clearview-ai-2020, ebay-2014, home-depot-2014, irhythm-2026, jpmorgan-2014, morrisons-2014, twilio-0ktapus-2022, uber-2016. Also blog/irhythm-october-2026-data-breach-notice, and the indexable breach pages castlerat, harvard, sberspasibo and youhack (all `index, follow`, checked 28 Nov).

**Never request these.** They sit in "Discovered" but are `noindex` by design (the build log of 28 Nov lists them): addi, advanceautoparts, canadiantire, doublecounter, mckesson, neogen, notsocradar, pdl, prosper, suno, both Synthient pages, tokopedia, wattpad, and the /videos/ pages.

Live URL Inspection disagrees with the report's buckets. The report lists aadhaar, lastpass and mgm as "Discovered", but inspection says "URL is unknown to Google". The report lags, so trust the live inspection.

**"Referring page: none detected"** appears on both new username guides. They are linked from /reverse-username-lookup.html and /guides/username-osint-search.html, so Google has not yet crawled those links. That fits a site whose crawl is 90% refresh and 10% discovery.

## 8. Re-inspection dates

- 7 days: 5 Dec 2026
- 14 days: 12 Dec 2026

Re-inspect every URL in section 7 on both dates and record the state.

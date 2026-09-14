# SEO overhaul — myrecon.xyz

Branch `seo-overhaul`, 5 commits, nothing pushed or deployed.

**Stack, for the record.** The Vercel deployment is `frontend/` — hand-written
static HTML, **no framework, no `package.json`, no dependencies**. Build is
`node scripts/gen-env.js && node scripts/build-breaches.js && node scripts/build-sitemap.js`
with `outputDirectory: "."`. There is no `next.config.js`, no `<head>`
abstraction and no native sitemap mechanism, so every `<head>` is maintained in
43 HTML files — of which the 14 `/breaches/*` pages are **generated** by
`scripts/build-breaches.js` and were fixed in the generator, not the output.

The root `vercel.json` points at `web_main.py`; that is a legacy Python target
and **not** what serves the live site. Confirmed against production:
`www.myrecon.xyz/about.html` serves `frontend/about.html`.

---

## 1. Status

### Phase 1 — Crawlability

| Task | Status | Detail |
|---|---|---|
| 1.1 sitemap.xml | **DONE** | Replaced the hand-maintained file with `scripts/build-sitemap.js`, which walks the output directory. 43 URLs, all absolute on `www`, **all with a real `<lastmod>`** (27 of the old 40 had none). Dates come from JSON-LD `dateModified` where present — the breach articles carry HIBP's real modified date, and their mtime is always "now" because they regenerate every build — otherwise the last commit that touched the file. Validated as XML; output is deterministic, so a rebuild that changed nothing produces no diff. Errors out above 50,000 URLs. |
| 1.2 robots.txt | **DONE** | `Sitemap:` corrected to `www`. Added `Disallow: /content/`. **Deliberately did not add `Disallow: /*?`** — CSS and JS are cache-busted with `?v=N`, so a blanket query-string rule would have blocked Googlebot from the files it needs to render. Nothing important was blocked before; only `/api/` was disallowed and that is correct. |
| 1.3 Canonicals | **DONE** | All 41 indexable pages had a self-referencing canonical pointing at the **apex**, which 308s to `www` — a canonical pointing at a redirect, on every page. 274 apex URLs rewritten across 47 files (canonical, `og:url`, JSON-LD `url`, RSS, sitemap, robots, the generator). Zero remain. |
| 1.4 Stray noindex | **DONE — nothing to remove** | Audited meta robots, `X-Robots-Tag`, and both `vercel.json` files. The only `noindex` is `/404.html`, which is correct and **kept**. No framework or CMS noindex settings exist. Vercel's preview-deployment `X-Robots-Tag` left alone as instructed. |
| 1.5 HTTPS + host | **DONE** | Verified live: `http://myrecon.xyz` → 308 → `https://myrecon.xyz` → 308 → `https://www.myrecon.xyz` → 200. Vercel already handles it and uses 308, which Google treats as equivalent to 301, so **nothing needed rebuilding** — see follow-up #1 on the two-hop chain. HSTS was `max-age=63072000` with no directives; now `max-age=63072000; includeSubDomains; preload`. Added `/index.html` → `/` (Vercel was serving both at 200) and `/content/:path*` → `/breaches/`. **No hardcoded `http://` links** except a `localhost` dev fallback in `config.js`, which is correct. **No `*.vercel.app` references anywhere.** No mixed content. |
| 1.6 URL slugs | **DONE — no renames** | All slugs are lowercase, hyphen-separated, no dates, no IDs, no stop-word noise, and `.html` is used consistently. Nothing warranted a rename. One ugly slug flagged rather than changed — follow-up #2. |

### Phase 2 — On-page markup

| Task | Status | Detail |
|---|---|---|
| 2.1 One H1 | **DONE** | Every indexable page already had exactly one H1 containing its real topic, and no inner page used an H1 for the logo. Verified across all 43; no change needed. |
| 2.2 Heading hierarchy | **DONE** | Two real defects fixed. `/guides/` jumped H1→H3 for 18 cards that are siblings under the page heading — now H2. The homepage footer used three `<h4>`s as styling for what are nav labels (also creating an H2→H4 skip) — now `<p class="footer-col-title">` with the look moved into CSS. **Verified identical rendering** via computed styles: 12.48px, uppercase, 0.9984px letter-spacing, same colour, same margins. |
| 2.3 Meta titles | **DONE** | 17 titles ran over 60 chars (worst 95); 13 under 50. **Now every one of 42 indexable pages is 50–60, with zero duplicates.** Generated titles use a tiered-fallback builder (below). |
| 2.4 Meta descriptions | **DONE** | 22 were outside 140–160 (worst 217). **All 42 now sit in range, none duplicated, none cut mid-word.** |
| 2.5 Image alt text | **DONE — already clean** | Every `<img>` on the site already had a descriptive `alt` and explicit `width`/`height`. Decorative logos correctly use `alt=""`. Nothing to fix; nothing blanket-filled. |
| 2.6 OG + Twitter | **DONE** | Only the homepage had the full set; the other 42 pages had between zero and five tags. All 43 now carry the complete block plus `apple-touch-icon` and the manifest. `og:image` is always the site card — **verified 1200×630**, so the declared dimensions are true. The breach pages had been pointing `og:image` at HIBP's small square logo, which `summary_large_image` letterboxes; the logo stays in JSON-LD where a square mark is correct. |
| 2.7 Schema (JSON-LD) | **DONE** | `Organization` and `WebSite` did not exist anywhere — both now on the homepage with `@id` references. `BreadcrumbList` on every nested page (was: only breach articles). The 10 pages with no JSON-LD now carry a matching type: `AboutPage`, `ContactPage`, `ProfilePage`+`Person`, `CollectionPage`, `Service`, `MobileApplication`, `WebApplication`, `WebPage`. **82 blocks across 43 pages, every one parsed and checked for required properties by script.** Nothing marked up that is not visible on the page: no ratings, no reviews, no invented FAQ. `SearchAction` included with a real working template — see follow-up #4. |
| 2.8 Head hygiene | **DONE** | `lang="en"`, charset and viewport present everywhere. Favicon + `apple-touch-icon` now on all 43 (was 1). **Zero duplicate meta tags** — this pass found and removed 7 duplicate-and-truncated `og:` tags it had itself introduced on a first attempt whose regex treated the apostrophe in "A Beginner's Guide" as a closing quote; values were recovered from git and rewritten quote-correctly. |

### Phase 3 — Links

| Task | Status | Detail |
|---|---|---|
| 3.1 Internal linking | **DONE** | **No orphan pages and nothing beyond 2 clicks from home** — that was already true. The real problem was link *distribution*: 18 guides carried one in-body internal link or none, and 10 of 14 breach articles had exactly one inbound link because the generator took `.slice(0, 3)` of siblings and pointed every article at the same three. Guides now end with 3–4 contextually related links with descriptive anchors; the generator's sibling window rotates and wraps. **Lowest inbound count on the site went from 1 to 4.** |
| 3.2 Broken links | **DONE** | Crawled the local build: **zero broken internal links, zero bad asset paths, zero bad canonical/sitemap URLs.** All 55 external links checked live — all resolve; two 403s are Cloudflare bot-blocking, not dead. Three redirect chains collapsed to zero hops: `twitter.com`→`x.com`, and `troyhunt.com`→`www.troyhunt.com`→trailing slash. Fixed at the generator so HIBP's CC-BY text is untouched and only the `href` moves. Also repaired a malformed anchor pair in `what-is-osint.html` that rendered as "guidesDeep Search". |

### Phase 4 — Performance

| Task | Status | Detail |
|---|---|---|
| 4.1 Image compression | **DONE — nothing to compress** | **Not a skip: there is no oversized image on this site.** Largest is `og-image.png` at 47KB (1200×630, correctly sized for its use). Everything else is SVG: `logo.svg` 809B, `favicon.svg` 578B. **Nothing approaches the 200KB flag and no image's pixel dimensions exceed its display size.** Converting a 47KB OG card to WebP would risk social-scraper compatibility for ~30KB. Breach-article logos are hotlinked from `logos.haveibeenpwned.com` and are not ours to compress. |
| 4.2 LCP | **PARTIAL** | Lighthouse identifies the LCP element as a **text block**, not an image — so there is no LCP image to preload or set `fetchpriority` on, and nothing is lazy-loaded that shouldn't be (the above-fold logo correctly has no `loading="lazy"`; all 24 lazy images are below the fold). Fonts already had `preconnect` and `display=swap`. What was done: **JetBrains Mono removed from the 24 pages that never render a glyph of it**, and the critical reset inlined so first paint is correct. What was not: self-hosting the fonts — follow-up #3. |
| 4.3 CLS | **DONE** | Found a real defect Lighthouse missed. On a **cold cache** every page scored **0.1226 CLS** from one shift — `BODY` moving `[7,8]→[0,0]` — because the browser paints a frame using its own default `body{margin:8px}` before `styles.css` lands. Inlining that one rule fixes it: **measured A/B, 0.1226 without, 0 with**, on the cold first load a search visitor gets. Lighthouse's run had the stylesheet warm and reported 0.007. Images/video/iframes: all images already had explicit dimensions; the site has **no iframes, no embeds and no manual ad slots**. |
| 4.4 INP / JS weight | **DONE — nothing to remove** | **There are no dependencies to remove** — no `package.json`, no node_modules, no bundler. Total own JS is 76.6KB unminified across 5 files, CSS 52.3KB across 3. The three build scripts are Node-only and ship nothing. Lighthouse's "200KB unused JavaScript" is almost entirely the AdSense third-party, which is already `async`. Total Blocking Time 160ms → 120ms across the pass. No long tasks in our own code to break up. |
| 4.5 Lighthouse | **DONE** | Ran against the local build, **3 runs per state** because single runs on this machine swing badly (one early reading of 96 was an outlier that three later runs at 65–70 contradicted). Numbers in §5. |

### Phase 5 — Mobile

| Task | Status | Detail |
|---|---|---|
| Responsive testing | **DONE** | All 13 templates tested at **375, 390, 768 and 1280**. **No page overflowed horizontally at any width and nothing escaped its container.** Fixed: 7 classes of tap target under 44×44 (icon buttons 38×38, tool tabs 39 high, footer links 31, brand 30, Deep Search toggle 22, example chips 33, small buttons 37) and 4 classes of body copy under 16px (feature cards 14.1px, step cards 14.7px, Deep Search standfirst 14.9px, breach data-class lists 12.5px). All scoped to `max-width: 820px`, so the desktop design is untouched. Viewport meta was **already clean** — no `user-scalable=no`, no `maximum-scale`. Left small on purpose: empty-state hints, the HIBP attribution line, the severity-method note. |
| Before/after screenshots | **PARTIAL** | The screenshot tool returned blank frames intermittently in this environment, so verification was done **numerically instead** — every element measured programmatically at each width, before and after, which is stronger evidence than an image. One "after" mobile screenshot captured successfully. To reproduce: `python -m http.server 4173 --directory frontend`, then a browser at 375px. |

### Phase 6 — Off-site

| Task | Status | Detail |
|---|---|---|
| 6.1 Search Console | **PARTIAL — needs your Google account** | I cannot verify a property I have no account for. Done: a commented verification slot for both Google and Bing sits in `frontend/index.html` right after the canonical, so you paste a token and uncomment. Walkthrough in §7. **Use the DNS domain property, not URL-prefix** — reasoning in §7. |
| 6.2 Backlink strategy | **DONE** | `BACKLINK-STRATEGY.md`: 20 named targets, 5 linkable-asset ideas, a 90-day weekly cadence, what not to do, and how to track. **Every URL was checked live**; hosts that block automated requests are marked `[403]`, and anything I could not confirm — whether a site accepts submissions or guest posts — is marked **verify before outreach** rather than asserted. No contact details, prices or affiliations invented. |

---

## 2. Page inventory

43 HTML files → 42 indexable pages + `/404.html` (correctly noindex). The
`/content/` editorial fragment is now redirected and disallowed, so it is no
longer a crawlable URL and is excluded here.

| URL | H1 | Title (chars) | Description (chars) | Canonical | Schema | Indexable |
|---|---|---|---|---|---|---|
| `/` | Investigate any digital footprintwith MyRecon | OSINT Tool for Username, Email & Breach Lookup | MyRecon **(56)** | Search a username across 100+ platforms, check an email or password ag… **(153)** | self/ | FAQPage, Organization, WebApplication, WebSite | yes |
| `/404.html` | This page went dark | Page not found — MyRecon **(24)** | — **(0)** | **none** | — | no |
| `/about.html` | About MyRecon | About MyRecon: Accurate OSINT From Documented Sources **(53)** | MyRecon is an open-source intelligence platform built on reliable, doc… **(152)** | self/about.html | AboutPage, BreadcrumbList | yes |
| `/app.html` | MyRecon for Android | MyRecon for Android: On-Device OSINT & Breach Watch **(51)** | The MyRecon Android app checks a username across many platforms from y… **(152)** | self/app.html | BreadcrumbList, MobileApplication, WebPage | yes |
| `/breaches/` | Every breach worth understanding | Data Breach Archive: What Was Taken and From Whom | MyReco **(59)** | Data breach archive: what was taken, from whom, how many people it tou… **(157)** | self/breaches/ | CollectionPage | yes |
| `/breaches/1win.html` | 1win | 1win Data Breach: 96,166,543 Accounts Exposed | MyRecon **(55)** | On 2 November 2024, 1win was breached. 96,166,543 accounts were expose… **(155)** | self/breaches/1win.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/addi.html` | Addi | Addi Data Breach: 34,532,941 Accounts Exposed | MyRecon **(55)** | On 25 March 2026, Addi was breached. 34,532,941 accounts were exposed,… **(154)** | self/breaches/addi.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/chess2026.html` | Chess.com (2026) | Chess.com (2026) Data Breach: 4,653,212 Accounts Exposed **(56)** | On 3 August 2026, Chess.com (2026) was breached. 4,653,212 accounts we… **(155)** | self/breaches/chess2026.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/demandscience.html` | DemandScience by Pure Incubation | DemandScience by Pure Incubation Data Breach | MyRecon **(54)** | On 28 February 2024, DemandScience by Pure Incubation was breached. 12… **(152)** | self/breaches/demandscience.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/eye4fraud.html` | Eye4Fraud | Eye4Fraud Data Breach: 16,000,591 Accounts Exposed | MyRec **(60)** | On 25 January 2023, Eye4Fraud was breached. 16,000,591 accounts were e… **(159)** | self/breaches/eye4fraud.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/genesismarket.html` | Genesis Market | Genesis Market Data Breach: 8,000,000 Accounts Exposed **(54)** | On 5 April 2023, Genesis Market was breached. 8,000,000 accounts were … **(147)** | self/breaches/genesismarket.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/mangatoon.html` | Mangatoon | Mangatoon Data Breach: 23,040,238 Accounts Exposed | MyRec **(60)** | On 13 May 2022, Mangatoon was breached. 23,040,238 accounts were expos… **(156)** | self/breaches/mangatoon.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/mckesson.html` | McKesson | McKesson Data Breach: 6,404,340 Accounts Exposed | MyRecon **(58)** | On 21 August 2026, McKesson was breached. 6,404,340 accounts were expo… **(155)** | self/breaches/mckesson.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/paidwork.html` | Paidwork | Paidwork Data Breach: 23,272,765 Accounts Exposed | MyReco **(59)** | On 29 March 2026, Paidwork was breached. 23,272,765 accounts were expo… **(142)** | self/breaches/paidwork.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/railyatri.html` | RailYatri | RailYatri Data Breach: 23,209,732 Accounts Exposed | MyRec **(60)** | On 26 December 2022, RailYatri was breached. 23,209,732 accounts were … **(155)** | self/breaches/railyatri.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/suno.html` | Suno | Suno Data Breach: 55,282,226 Accounts Exposed | MyRecon **(55)** | On 25 November 2025, Suno was breached. 55,282,226 accounts were expos… **(160)** | self/breaches/suno.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/synthientcredentialstuffingthreatdata.html` | Synthient Credential Stuffing Threat Data | Synthient Credential Stuffing Threat Data Breach | MyRecon **(58)** | On 11 April 2025, Synthient Credential Stuffing Threat Data was breach… **(148)** | self/breaches/synthientcredentialstuffingthreatdata.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/telegramcombolists.html` | Combolists Posted to Telegram | Combolists Posted to Telegram Data Breach — What Was Expos **(60)** | On 28 May 2024, Combolists Posted to Telegram was breached. 361,468,09… **(143)** | self/breaches/telegramcombolists.html | BreadcrumbList, NewsArticle | yes |
| `/breaches/underarmour.html` | Under Armour | Under Armour Data Breach: 72,742,892 Accounts Exposed **(53)** | On 17 November 2025, Under Armour was breached. 72,742,892 accounts we… **(160)** | self/breaches/underarmour.html | BreadcrumbList, NewsArticle | yes |
| `/contact.html` | Contact | Contact MyRecon — Support, Removals and Disclosure **(50)** | Reach MyRecon about a personal footprint report, a removal enquiry, a … **(156)** | self/contact.html | BreadcrumbList, ContactPage | yes |
| `/content/breaches/UnderArmour.html` | — | — **(0)** | — **(0)** | **none** | — | no |
| `/deep-search.html` | Deep Search | Deep Search: Username Correlation Console | MyRecon **(51)** | Check a username across 100+ public platforms and see every match corr… **(151)** | self/deep-search.html | BreadcrumbList, WebApplication, WebPage | yes |
| `/founder.html` | Aryan Walia | Aryan Walia — Penetration Tester, Founder of MyRecon **(52)** | Aryan Walia is a penetration tester and founder of BugSnaps and MyReco… **(157)** | self/founder.html | BreadcrumbList, Person, ProfilePage | yes |
| `/guides/` | Learn OSINT and online privacy | OSINT Guides: Privacy, Breaches, DNS and Domains | MyRecon **(58)** | Plain-English guides to open-source intelligence and online privacy: e… **(155)** | self/guides/ | BreadcrumbList, CollectionPage | yes |
| `/guides/check-email-data-breach.html` | How to Check If Your Email Was in a Data Breach | How to Check If Your Email Was in a Data Breach | MyRecon **(57)** | Learn what a data breach is, how to check whether your email address w… **(155)** | self/guides/check-email-data-breach.html | Article, BreadcrumbList | yes |
| `/guides/dns-records-explained.html` | DNS Records Explained: A, MX, TXT, NS and More | DNS Records Explained: A, MX, TXT, NS and More | MyRecon **(56)** | A plain-English guide to DNS record types — A, AAAA, MX, NS, TXT, CNAM… **(148)** | self/guides/dns-records-explained.html | Article, BreadcrumbList | yes |
| `/guides/how-data-brokers-work.html` | How Data Brokers Collect and Sell Your Personal Data | How Data Brokers Collect and Sell Your Data | MyRecon **(53)** | Who data brokers are, where they get your information, how they profit… **(152)** | self/guides/how-data-brokers-work.html | Article, BreadcrumbList | yes |
| `/guides/how-to-spot-phishing.html` | How to Spot a Phishing Email or Website | How to Spot a Phishing Email or Fake Website | MyRecon **(54)** | A practical checklist for spotting phishing emails and scam websites: … **(155)** | self/guides/how-to-spot-phishing.html | Article, BreadcrumbList | yes |
| `/guides/investigate-a-domain.html` | How to Investigate a Suspicious Domain: A Step-by-Step | How to Investigate a Suspicious Domain Safely | MyRecon **(55)** | A repeatable workflow for investigating a domain you don't trust: regi… **(156)** | self/guides/investigate-a-domain.html | Article, BreadcrumbList | yes |
| `/guides/ip-geolocation-reverse-dns.html` | IP Geolocation and Reverse DNS: What an IP Address Rev | IP Geolocation and Reverse DNS Explained | MyRecon **(50)** | How IP geolocation is estimated, what ASN and hosting flags mean, and … **(151)** | self/guides/ip-geolocation-reverse-dns.html | Article, BreadcrumbList | yes |
| `/guides/reduce-your-digital-footprint.html` | How to Reduce Your Digital Footprint: A Practical Guid | How to Reduce Your Digital Footprint Online | MyRecon **(53)** | A step-by-step routine to find, shrink and control the public data abo… **(151)** | self/guides/reduce-your-digital-footprint.html | Article, BreadcrumbList | yes |
| `/guides/reverse-image-search.html` | Reverse Image Search: How to Trace a Photo's Origin | Reverse Image Search: Trace a Photo's Origin | MyRecon **(54)** | How reverse image search works, which tools to use, and a practical wo… **(157)** | self/guides/reverse-image-search.html | Article, BreadcrumbList | yes |
| `/guides/social-media-privacy.html` | How to Lock Down Your Social Media Privacy | How to Lock Down Your Social Media Privacy | MyRecon **(52)** | A settings-by-setting guide to reducing what strangers can see and fin… **(156)** | self/guides/social-media-privacy.html | Article, BreadcrumbList | yes |
| `/guides/spf-dkim-dmarc-explained.html` | Email Authentication Explained: SPF, DKIM and DMARC | SPF, DKIM and DMARC Explained for Email Security | MyRecon **(58)** | A plain-English guide to SPF, DKIM and DMARC — the DNS records that st… **(149)** | self/guides/spf-dkim-dmarc-explained.html | Article, BreadcrumbList | yes |
| `/guides/strong-passwords-guide.html` | Password Security: How to Create and Manage Strong Pas | How to Create and Manage Strong Passwords | MyRecon **(51)** | Why password reuse is dangerous, how to create strong passwords, why a… **(157)** | self/guides/strong-passwords-guide.html | Article, BreadcrumbList | yes |
| `/guides/two-factor-authentication.html` | Two-Factor Authentication: Why It Matters and How to S | Two-Factor Authentication: A Complete 2FA Guide | MyRecon **(57)** | What two-factor authentication is, why it stops most account takeovers… **(153)** | self/guides/two-factor-authentication.html | Article, BreadcrumbList | yes |
| `/guides/username-osint-search.html` | Username OSINT: How to Find Accounts Across Platforms | Username OSINT: Find Accounts Across Platforms | MyRecon **(56)** | How username enumeration works across social and developer platforms, … **(160)** | self/guides/username-osint-search.html | Article, BreadcrumbList | yes |
| `/guides/verify-an-osint-finding.html` | How to Verify an OSINT Finding Before You Act on It | How to Verify an OSINT Finding Before Acting | MyRecon **(54)** | A matching username is not proof of identity. A practical method for c… **(154)** | self/guides/verify-an-osint-finding.html | Article, BreadcrumbList | yes |
| `/guides/what-http-responses-reveal.html` | What a Website's Response Actually Tells You | What a Website's HTTP Response Tells You | MyRecon **(50)** | 200, 404, 403 and 429 mean very different things when you check whethe… **(149)** | self/guides/what-http-responses-reveal.html | Article, BreadcrumbList | yes |
| `/guides/what-is-osint.html` | What Is OSINT? A Beginner's Guide to Open-Source Intel | What Is OSINT? Open-Source Intelligence Explained | MyReco **(59)** | A clear beginner's guide to open-source intelligence: what OSINT is, h… **(150)** | self/guides/what-is-osint.html | Article, BreadcrumbList | yes |
| `/guides/whois-rdap-explained.html` | WHOIS and RDAP Explained: Who Owns a Domain? | WHOIS and RDAP Explained: Who Owns a Domain? | MyRecon **(54)** | Understand a domain's registration record: registrar, creation and exp… **(152)** | self/guides/whois-rdap-explained.html | Article, BreadcrumbList | yes |
| `/guides/why-username-checkers-report-fake-accounts.html` | Why Username Checkers Report Accounts That Don't Exist | Why Username Checkers Report Fake Accounts | MyRecon **(52)** | We measured what 24 platforms return for a real handle and an invented… **(155)** | self/guides/why-username-checkers-report-fake-accounts.html | Article, BreadcrumbList | yes |
| `/privacy.html` | Privacy Policy | Privacy Policy: No Accounts, No Stored Searches | MyRecon **(57)** | How MyRecon handles your data: no registration, no search queries kept… **(154)** | self/privacy.html | BreadcrumbList, WebPage | yes |
| `/services.html` | Find what's out there. Then get it taken down. | Personal Data & Footprint Removal Service | MyRecon **(51)** | We find the accounts, listings and data-broker records tied to your na… **(153)** | self/services.html | BreadcrumbList, Service, WebPage | yes |
| `/terms.html` | Terms of Use | Terms of Use — Lawful OSINT and Research Only | MyRecon **(55)** | The terms covering MyRecon: lawful use and authorised research only, n… **(153)** | self/terms.html | BreadcrumbList, WebPage | yes |

---

## 3. Broken links

**Internal: none.** Every internal link, image `src`, script/style `src`,
canonical and sitemap URL in the local build resolves to a file that exists.

| URL | Found on | Status | Action |
|---|---|---|---|
| `https://twitter.com/FalconFeedsio/status/…` | `/breaches/eye4fraud.html` | 301 → `x.com` | **Fixed** — generator rewrites the host; now 200, 0 hops |
| `https://troyhunt.com/telegram-combolists-…` | `/breaches/telegramcombolists.html` | 2 hops → `www.` + trailing slash | **Fixed** — generator normalises; now 200, 0 hops |
| `/guides/what-is-osint.html` → `guides</a><a>Deep Search` | `/guides/what-is-osint.html` | rendered as "guidesDeep Search" | **Fixed** — two anchors had no text between them |
| `https://cybernews.com/security/paidwork-…` | `/breaches/paidwork.html` | 403 to bots | **Left as-is** — Cloudflare bot-block; page is live in a browser |
| `https://hackread.com/everest-ransomware-…` | `/breaches/underarmour.html` | 403 to bots | **Left as-is** — same |
| `https://www.bleepingcomputer.com/…`, `https://www.mckesson.com/…` | `/breaches/mckesson.html` | 403 to bots | **Left as-is** — same |

All other 49 external links returned 200 with zero redirects.

---

## 4. Images

No image on this site required compression. Full inventory:

| File | Before | After | Saved |
|---|---|---|---|
| `assets/img/og-image.png` (1200×630) | 47,981 B | 47,981 B | 0 — under the 200KB flag, correctly sized, and re-encoding an OG card risks scraper compatibility |
| `assets/img/og-image.svg` | 1,711 B | 1,711 B | 0 — vector |
| `assets/img/logo.svg` | 809 B | 809 B | 0 — vector |
| `assets/img/favicon.svg` | 578 B | 578 B | 0 — vector |
| `logos.haveibeenpwned.com/*.png` | external | external | n/a — hotlinked from HIBP, not ours to re-encode |

**Total image weight: 51,079 B.** No `srcset` work was warranted: the only
raster file is a social card that is never rendered in the page.

---

## 5. Before / after metrics

Lighthouse against the local build, **median of 3 runs per state**, headless
Chrome, default mobile throttling. Before = the branch at end of Phase 3.

| | Before | After |
|---|---|---|
| Performance | 67 (65/67/67) | 68 (68/65/70) |
| Accessibility | 91 | **100 on all 15 URLs tested** |
| Best Practices | 79 | 79 |
| **SEO** | 100 | **100** |
| CLS (Lighthouse, warm cache) | 0–0.007 | 0–0.007 |
| **CLS (real cold load, measured in-browser)** | **0.1226** | **0** |
| Total Blocking Time | 160 ms | 120 ms |

**Read this honestly.** The Performance score did not move, and I am not going
to claim it did — it is dominated by the AdSense third-party scripts, not by
anything in this codebase. The genuine wins this phase are accessibility
(91→100) and the cold-load CLS, which Lighthouse's own run never saw because
its cache was warm.

**Correction to an earlier draft of this report.** The first version claimed
"Accessibility 100, zero failing audits" on the strength of a single run
against `/about.html`. That was not a safe generalisation: re-running across
every template found `/` at 96 (colour contrast + an invalid heading order),
`/breaches/suno.html` at 96, `/services.html` at 95 and `/deep-search.html` at
95. Those are now genuinely fixed and 100 is verified per URL — see §10.

| Weight | Value |
|---|---|
| Own JS | 76.6 KB unminified, 5 files, **0 dependencies** |
| Own CSS | 52.3 KB, 3 files |
| Images | 51.1 KB total |
| Largest page HTML | 26.2 KB (`index.html`) |
| Font requests removed | JetBrains Mono dropped from 24 of 41 pages |

Not measured: production figures behind Vercel's CDN, which serves Brotli and
real cache headers. Lighthouse's "enable text compression, 76 KiB" is an
artefact of the local `python -m http.server` and does not apply in production.

---

## 6. Files changed, by phase

### Point the whole site at one hostname, and stop hand-maintaining the sitemap
- frontend/about.html                                
- frontend/app.html                                  
- frontend/assets/data/breaches.json                 
- frontend/assets/js/app.js                          
- frontend/assets/js/env.js                          
- frontend/breaches/1win.html                        
- frontend/breaches/addi.html                        
- frontend/breaches/chess2026.html                   
- frontend/breaches/demandscience.html               
- frontend/breaches/eye4fraud.html                   
- frontend/breaches/feed.xml                         
- frontend/breaches/genesismarket.html               
- frontend/breaches/index.html                       
- frontend/breaches/mangatoon.html                   
- frontend/breaches/mckesson.html                    
- frontend/breaches/paidwork.html                    
- frontend/breaches/railyatri.html                   
- frontend/breaches/suno.html                        
- .../synthientcredentialstuffingthreatdata.html     
- frontend/breaches/telegramcombolists.html          
- frontend/breaches/underarmour.html                 
- frontend/contact.html                              
- frontend/deep-search.html                          
- frontend/founder.html                              
- frontend/guides/check-email-data-breach.html       
- frontend/guides/dns-records-explained.html         
- frontend/guides/how-data-brokers-work.html         
- frontend/guides/how-to-spot-phishing.html          
- frontend/guides/index.html                         
- frontend/guides/investigate-a-domain.html          
- frontend/guides/ip-geolocation-reverse-dns.html    
- frontend/guides/reduce-your-digital-footprint.html 
- frontend/guides/reverse-image-search.html          
- frontend/guides/social-media-privacy.html          
- frontend/guides/spf-dkim-dmarc-explained.html      
- frontend/guides/strong-passwords-guide.html        
- frontend/guides/two-factor-authentication.html     
- frontend/guides/username-osint-search.html         
- frontend/guides/verify-an-osint-finding.html       
- frontend/guides/what-http-responses-reveal.html    
- frontend/guides/what-is-osint.html                 
- frontend/guides/whois-rdap-explained.html          
- ...why-username-checkers-report-fake-accounts.html 
- frontend/index.html                                
- frontend/privacy.html                              
- frontend/robots.txt                                
- frontend/scripts/build-breaches.js                 
- frontend/scripts/build-sitemap.js                  
- frontend/services.html                             
- frontend/sitemap.xml                               
- frontend/terms.html                                
- frontend/vercel.json                               
- 52 files changed, 867 insertions(+), 317 deletions(-)

### Write heads that survive the search results page
- frontend/about.html                                
- frontend/app.html                                  
- frontend/assets/css/styles.css                     
- frontend/assets/data/breaches.json                 
- frontend/breaches/1win.html                        
- frontend/breaches/addi.html                        
- frontend/breaches/chess2026.html                   
- frontend/breaches/demandscience.html               
- frontend/breaches/eye4fraud.html                   
- frontend/breaches/feed.xml                         
- frontend/breaches/genesismarket.html               
- frontend/breaches/index.html                       
- frontend/breaches/mangatoon.html                   
- frontend/breaches/mckesson.html                    
- frontend/breaches/paidwork.html                    
- frontend/breaches/railyatri.html                   
- frontend/breaches/suno.html                        
- .../synthientcredentialstuffingthreatdata.html     
- frontend/breaches/telegramcombolists.html          
- frontend/breaches/underarmour.html                 
- frontend/contact.html                              
- frontend/deep-search.html                          
- frontend/founder.html                              
- frontend/guides/check-email-data-breach.html       
- frontend/guides/dns-records-explained.html         
- frontend/guides/how-data-brokers-work.html         
- frontend/guides/how-to-spot-phishing.html          
- frontend/guides/index.html                         
- frontend/guides/investigate-a-domain.html          
- frontend/guides/ip-geolocation-reverse-dns.html    
- frontend/guides/reduce-your-digital-footprint.html 
- frontend/guides/reverse-image-search.html          
- frontend/guides/social-media-privacy.html          
- frontend/guides/spf-dkim-dmarc-explained.html      
- frontend/guides/strong-passwords-guide.html        
- frontend/guides/two-factor-authentication.html     
- frontend/guides/username-osint-search.html         
- frontend/guides/verify-an-osint-finding.html       
- frontend/guides/what-http-responses-reveal.html    
- frontend/guides/what-is-osint.html                 
- frontend/guides/whois-rdap-explained.html          
- ...why-username-checkers-report-fake-accounts.html 
- frontend/index.html                                
- frontend/privacy.html                              
- frontend/scripts/build-breaches.js                 
- frontend/services.html                             
- frontend/sitemap.xml                               
- frontend/terms.html                                
- 48 files changed, 826 insertions(+), 161 deletions(-)

### Give the guides and breach articles a reason to link to each other
- frontend/assets/css/styles.css                     
- frontend/assets/data/breaches.json                 
- frontend/breaches/1win.html                        
- frontend/breaches/addi.html                        
- frontend/breaches/chess2026.html                   
- frontend/breaches/demandscience.html               
- frontend/breaches/eye4fraud.html                   
- frontend/breaches/feed.xml                         
- frontend/breaches/genesismarket.html               
- frontend/breaches/paidwork.html                    
- frontend/breaches/railyatri.html                   
- frontend/breaches/suno.html                        
- .../synthientcredentialstuffingthreatdata.html     
- frontend/breaches/telegramcombolists.html          
- frontend/breaches/underarmour.html                 
- frontend/guides/check-email-data-breach.html       
- frontend/guides/dns-records-explained.html         
- frontend/guides/how-data-brokers-work.html         
- frontend/guides/how-to-spot-phishing.html          
- frontend/guides/investigate-a-domain.html          
- frontend/guides/ip-geolocation-reverse-dns.html    
- frontend/guides/reduce-your-digital-footprint.html 
- frontend/guides/reverse-image-search.html          
- frontend/guides/social-media-privacy.html          
- frontend/guides/spf-dkim-dmarc-explained.html      
- frontend/guides/strong-passwords-guide.html        
- frontend/guides/two-factor-authentication.html     
- frontend/guides/username-osint-search.html         
- frontend/guides/verify-an-osint-finding.html       
- frontend/guides/what-http-responses-reveal.html    
- frontend/guides/what-is-osint.html                 
- frontend/guides/whois-rdap-explained.html          
- ...why-username-checkers-report-fake-accounts.html 
- frontend/scripts/build-breaches.js                 
- 34 files changed, 194 insertions(+), 23 deletions(-)

### Stop the first paint shifting, and make the page readable without colour vision
- frontend/404.html                                  
- frontend/about.html                                
- frontend/app.html                                  
- frontend/assets/css/styles.css                     
- frontend/assets/data/breaches.json                 
- frontend/breaches/1win.html                        
- frontend/breaches/addi.html                        
- frontend/breaches/chess2026.html                   
- frontend/breaches/demandscience.html               
- frontend/breaches/eye4fraud.html                   
- frontend/breaches/feed.xml                         
- frontend/breaches/genesismarket.html               
- frontend/breaches/index.html                       
- frontend/breaches/mangatoon.html                   
- frontend/breaches/mckesson.html                    
- frontend/breaches/paidwork.html                    
- frontend/breaches/railyatri.html                   
- frontend/breaches/suno.html                        
- .../synthientcredentialstuffingthreatdata.html     
- frontend/breaches/telegramcombolists.html          
- frontend/breaches/underarmour.html                 
- frontend/contact.html                              
- frontend/deep-search.html                          
- frontend/founder.html                              
- frontend/guides/check-email-data-breach.html       
- frontend/guides/dns-records-explained.html         
- frontend/guides/how-data-brokers-work.html         
- frontend/guides/how-to-spot-phishing.html          
- frontend/guides/index.html                         
- frontend/guides/investigate-a-domain.html          
- frontend/guides/ip-geolocation-reverse-dns.html    
- frontend/guides/reduce-your-digital-footprint.html 
- frontend/guides/reverse-image-search.html          
- frontend/guides/social-media-privacy.html          
- frontend/guides/spf-dkim-dmarc-explained.html      
- frontend/guides/strong-passwords-guide.html        
- frontend/guides/two-factor-authentication.html     
- frontend/guides/username-osint-search.html         
- frontend/guides/verify-an-osint-finding.html       
- frontend/guides/what-http-responses-reveal.html    
- frontend/guides/what-is-osint.html                 
- frontend/guides/whois-rdap-explained.html          
- ...why-username-checkers-report-fake-accounts.html 
- frontend/index.html                                
- frontend/privacy.html                              
- frontend/scripts/build-breaches.js                 
- frontend/services.html                             
- frontend/terms.html                                
- frontend/vercel.json                               
- 49 files changed, 309 insertions(+), 55 deletions(-)

### Make the phone layout thumb-sized
- frontend/assets/css/breaches.css    
- frontend/assets/css/deep-search.css 
- frontend/assets/css/styles.css      
- frontend/assets/data/breaches.json  
- frontend/breaches/feed.xml          
- 5 files changed, 40 insertions(+), 2 deletions(-)

---

## 7. Search Console + Bing — your steps

**Use the domain property.** A DNS `TXT` record at the registrar covers `www`,
apex, `http` and `https` in one property. This site redirects three of those
four into the fourth, so a URL-prefix property would show you a fraction of the
picture and would need re-verifying if the canonical host ever changed.

1. **Verify.** [search.google.com/search-console](https://search.google.com/search-console)
   → Add property → **Domain** → `myrecon.xyz` → copy the TXT record → add it at
   your registrar's DNS → Verify. Propagation is usually minutes.
   *Fallback if you cannot edit DNS:* use URL prefix `https://www.myrecon.xyz`,
   and paste the token into the commented `google-site-verification` tag in
   `frontend/index.html` (just after the canonical), then uncomment it.
2. **Submit the sitemap.** Sitemaps → enter `sitemap.xml` → Submit. The full URL
   is `https://www.myrecon.xyz/sitemap.xml`.
3. **Check indexing.** Pages → Indexing. **Expect the "Page with redirect" count
   to fall** — before this pass, all 40 sitemap URLs pointed at the apex and
   every one of them redirected. Give it a couple of weeks.
4. **Request indexing** on the pages that changed most: `/`, `/guides/`,
   `/breaches/`, `/services.html`, `/deep-search.html`. URL Inspection → paste
   the URL → Request Indexing. There is a daily quota; spend it on those.
5. **Bing.** [bing.com/webmasters](https://www.bing.com/webmasters) → Add site →
   **"Import from Google Search Console"**, which carries the verification and
   the sitemap across in about two minutes. The manual route is the
   `msvalidate.01` tag, already slotted in the same place.
6. **IndexNow already works** — `scripts/indexnow.js` posts to Bing, DuckDuckGo,
   Yandex and Seznam, and its key file is live. Google does not participate, so
   step 4 is not optional.

---

## 8. Follow-ups needing your decision

1. **The apex redirect is two hops** (`http://apex` → `https://apex` →
   `https://www`) and uses **308, not 301**. 308 is fine — Google treats it as
   equivalent. The two hops are Vercel's own domain handling and **cannot be
   collapsed from code**. To check it is configured as a redirect rather than a
   second primary domain: Vercel dashboard → your project → **Settings →
   Domains** → confirm `myrecon.xyz` shows **Redirect to `www.myrecon.xyz`**. If
   it is listed as a second production domain instead, change it there.
2. **One ugly slug, deliberately left alone.**
   `/breaches/synthientcredentialstuffingthreatdata.html` is unreadable. Fixing
   it properly means hyphenating on case boundaries in the generator's `slug()`,
   which would change **7 of 14 live, indexed breach URLs** and need 7 redirects.
   Poor trade for a long-tail page. **Say the word and I'll do it with the 301s.**
3. **Self-hosting Inter** would remove the last render-blocking third-party
   request (Lighthouse estimates 570–720ms) and let the exact `woff2` files be
   preloaded. It is the remaining LCP lever. Not done unasked because it means
   committing font binaries and a subsetting step.
4. **`SearchAction` points at `/#tool=username&q={search_term_string}`** — a real
   working entry point the tool reads on load. It is a hash, so no server sees
   it, and **Google retired the sitelinks search box in 2024**. Harmless and
   accurate; say if you would rather it came out.
5. **HSTS now asserts `includeSubDomains; preload`.** That commits *every*
   subdomain of `myrecon.xyz` to HTTPS-only, permanently and hard to undo once
   submitted to the preload list. If any subdomain (an API host, a staging box)
   must serve plain HTTP, **tell me and I'll drop those two directives**.
6. **Asset cache lifetimes are conservative on purpose.** CSS/JS keep
   `must-revalidate` because their cache key is a **hand-maintained `?v=N`** —
   a long immutable lifetime plus a forgotten version bump serves a broken site
   for a year. The proper fix is content-hashing filenames at build time. Worth
   doing; not done unasked.
7. **AdSense Auto Ads.** The account script loads but there are no manual ad
   slots, which means Auto Ads injects units at runtime. That is the one CLS
   source I cannot reserve space for from here. If layout shift on production
   matters, switching to fixed, sized slots is the fix.
8. **~~The `?v=8` cache-buster is stale~~ — done.** Bumped to `?v=9` (and the
   breach stylesheet `?v=1`→`?v=2`) across all 45 files plus the generator,
   because every CSS and JS file changed in this pass. Worth knowing: the cache
   key is still hand-maintained, so the next person to edit a stylesheet has to
   remember. Content-hashing filenames at build time remains the real fix
   (follow-up #6).
9. **Keyword mapping correction.** My initial proposal gave
   `/deep-search.html` "osint people search". **That is wrong** — the page
   states name search is deliberately *not* offered. It is mapped to username
   correlation instead. The rest of the mapping stands; correct me on any of it
   and the titles are a one-line change each.

---

## 9. Reproducing the checks

```bash
cd frontend
node scripts/build-breaches.js && node scripts/build-sitemap.js   # build
python -m http.server 4173 --directory .                          # serve
CHROME_PATH="/c/Program Files/Google/Chrome/Application/chrome.exe" \
  npx lighthouse@12 http://localhost:4173/about.html \
  --chrome-flags="--headless=new" --only-categories=performance,accessibility,best-practices,seo
```

Run Lighthouse at least 3 times. Single runs on a loaded machine vary by 30
points, which is how the one early "96" in this session happened.

---

## 10. Second pass — what a re-audit found

The first pass verified accessibility against **one page** and generalised from
it. Re-running every template found four more defects, one of them a regression
introduced by this work. All are fixed and verified below.

### 10.1 A regression this work introduced

**The brand link's `aria-label` fix was being undone on every build.** Phase 2
rewrote `aria-label="MyRecon home"` to `"MyRecon OSINT — home"` across the HTML
— including the 14 generated breach articles — but the *generator template* in
`scripts/build-breaches.js` still held the old string. The next
`node scripts/build-breaches.js` wrote it straight back. Lighthouse caught it
as `label-content-name-mismatch` on `/breaches/suno.html`.

Fixed at the template. The general lesson applies to this repo: **editing
generated output is always temporary** — only the generator counts.

### 10.2 Colour contrast, in the theme nobody tested

`--text-mute` (`#647089`) was used for the trust chips, article bylines, stat
labels, hints, idle tool tabs and the Deep Search kicker. It measured **3.85:1
on `--bg` and 3.49:1 on `--surface`** — under the 4.5:1 WCAG AA needs. Raised
to `#7d8aa3` (dark) and `#5f6f86` (light), which clears 4.5 on `--bg`,
`--surface` and `--surface-2` in both themes while staying clearly dimmer than
`--text-dim`, so the visual hierarchy is unchanged.

White on `--accent` in primary buttons measured **3.67:1** at 15.2px — below
the large-text threshold that would have permitted 3:1. Buttons now use
`--accent-2`, the palette's own darker blue: 5.17:1 in dark, 6.7:1 in light.
`.btn-ghost` is unaffected.

**The significant find: the light theme never defined the semantic colours at
all.** `--ok`, `--warn`, `--danger` and `--info` were declared once, tuned for a
dark background, and inherited straight into the light palette — where they are
used as **text** in seventeen places, including the exposure verdicts, the
confidence tags, the error box and the breach severity badges. Measured on
white:

| Token | Was (light) | Now | Ratio now (bg / surface / surface-2) |
|---|---|---|---|
| `--warn` | `#fbbf24` — **1.67:1** | `#b45309` | 4.68 / 5.02 / 4.64 |
| `--ok` | `#34d399` — **1.92:1** | `#047857` | 5.11 / 5.48 / 5.07 |
| `--info` | `#38bdf8` — **2.14:1** | `#0369a1` | 5.53 / 5.93 / 5.48 |
| `--danger` | `#fb7185` — **2.69:1** | `#be123c` | 5.86 / 6.29 / 5.81 |

The amber at 1.67:1 was effectively invisible. This is pre-existing, not
introduced here, and Lighthouse never reports it because it only ever renders
the default theme.

The `sev-serious` breach badge (`--accent` on `--surface-2`, 4.31:1) now uses
the `--accent-text` token added in Phase 4: 6.24:1.

### 10.3 Invalid heading order on the homepage

The tool's empty and ready states rendered their status line as `<h3>`
(`"Ready when you are"`, `"Nothing found"`), putting an h3 in a section with no
h2 above it. They are UI status messages, not document headings, so they are
now `<p class="empty-title">` with identical styling — the same treatment the
footer labels got in Phase 2.

### 10.4 Cache-buster bumped

`?v=8` → `?v=9` and `?v=1` → `?v=2` across 45 files and the generator. Without
this, every returning visitor would have kept the old stylesheet and received
none of the contrast, tap-target or CLS fixes.

### 10.5 Two false alarms, recorded so they are not re-investigated

- **`.ex-chip` "loses its colour in light theme" — it does not.** The Browser
  pane was hidden, so CSS transitions never advanced and `getComputedStyle`
  returned the frozen start value of a 0.16s colour transition. Measuring with
  transitions disabled shows it correct at 6.79:1 dark and 7.00:1 light.
- **`min-height: 44px` on `.ex-chip` "pushes its text to the top" — it does
  not.** The element is a `<button>`, which centres its content by default; the
  text measures 14px above and 15px below. Verified rather than assumed.

### 10.6 Verified state

Lighthouse, clean profile per run, every template:

| URL | Accessibility | SEO |
|---|---|---|
| `/` | 100 | 100 |
| `/about.html` | 100 | 100 |
| `/services.html` | 100 | 100 |
| `/app.html` | 100 | 100 |
| `/contact.html` | 100 | 100 |
| `/founder.html` | 100 | 100 |
| `/privacy.html` | 100 | 100 |
| `/terms.html` | 100 | 100 |
| `/deep-search.html` | 100 | 100 |
| `/guides/` | 100 | 100 |
| `/guides/what-is-osint.html` | 100 | 100 |
| `/guides/two-factor-authentication.html` | 100 | 100 |
| `/breaches/` | 100 | 100 |
| `/breaches/suno.html` | 100 | 100 |
| `/breaches/underarmour.html` | 100 | 100 |

Also re-verified after these changes: cold-load CLS still 0 on both templates
measured; no horizontal overflow and no sub-44px tap target at 375px; 43
sitemap URLs; 82 JSON-LD blocks all parsing with required properties; zero
broken internal links; no control characters in any tracked text file.

**One caveat worth stating plainly.** Lighthouse renders only the default
(dark) theme, so its 100s do not certify the light theme. The light-theme
figures above were measured directly in the browser with transitions disabled,
element by element — that is a narrower check than a full axe pass, and a
light-theme audit of the tool's *result* views (which only exist after a live
lookup) has not been done.

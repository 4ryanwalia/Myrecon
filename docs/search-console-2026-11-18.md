# Search Console pass, 18 November 2026

Source: Google Search Console, property `sc-domain:myrecon.xyz`, Search type Web,
read in the browser on 18 Nov 2026. The latest day in the data is 15 Nov 2026.

## Site baseline

| Window | Clicks | Impressions | CTR | Avg position |
| --- | --- | --- | --- | --- |
| Last 3 months | 195 | 5.05K | 3.9% | 26.4 |
| Last 28 days | 167 | 4.75K | 3.5% | 26.6 |
| Last 7 days | 41 | 1.14K | 3.6% | 26.6 |

Almost all traffic is from the last 28 days (about 170 impressions and 6 clicks a
day). The "1,000 to 1,400 impressions a day" in `docs/seo-growth-agent-prompt.md`
matches the 7-day total (1.14K), so it is probably a weekly figure. Use this
table as the baseline.

Not run: `npm run audit:seo -- --gsc`. The query table was read in the browser
and analysed by hand instead of being exported to CSV.

545 queries had impressions in 3 months. Most have 1 to 3 impressions, so
single-query positions are noisy.

## Pages changed in this pass (28-day figures before the change)

| Page | Query evidence | Clicks | Impr. | CTR | Pos. | Change |
| --- | --- | --- | --- | --- | --- | --- |
| /blog/account-deletion-vs-deactivation.html | "deactivate account vs delete account" 3 impr, pos 10.7; "difference between deactivate and delete" 2, pos 10.0; "is deactivating an account the same as deleting it" 2, pos 10.5; "difference between deactivate and delete account" 2, pos 11.0; "if you want to delete an account permanently, you must deactivate it. true or false?" 1, pos 8.0 | 1 | 181 | 0.6% | 18.6 | Title and H1 now use the searchers' wording. The opening paragraph answers directly. Three question H2s, also marked up as FAQPage. A table of how X, Snapchat, Instagram, LinkedIn and Discord treat deactivation vs deletion, from each company's help page, read 18 Nov 2026. Facebook and TikTok are left out because their pages would not load for checking. New descriptive links in from 3 related posts. |
| /blog/sherlock-vs-maigret-vs-myrecon.html | "sherlock / maigret" 2, pos 5.0; "sherlock and maigret" 2, pos 11.0; "maigret vs sherlock" 1, pos 9.0; "sherlock & maigret" 1, pos 9.0 | 0 | 28 | 0% | 6.5 | Title leads with "Sherlock vs Maigret". The opening gives a direct verdict, using site counts from each README (read 18 Nov 2026) and the dated 35-control results. |
| /vs/sherlock | "sherlock.xyz alternatives" 139 impr, 0 clicks, pos 8.0 | 2 | 181 | 1.1% | 8.7 | One sentence says the page covers Sherlock from sherlockproject.xyz. Google's AI Overview for this query is split between that tool and an unrelated product named Sherlock. Expect little change: much of this query's intent is not ours. |

Re-check these three pages in Search Console 4 to 6 weeks after deploy,
comparing the same 28-day window.

## Looked at and left alone

- **/breaches/case-files/vtech-2015.html**: 179 impressions at position 7.8 for
  `"secured consumer services" linkedin`. The intent is someone looking up a
  company on LinkedIn, so it is not worth targeting.
- **/directory.html**: 280 impressions at position 10.1, mostly breach queries
  ("ashley madison scandal" and others). The HTML sitemap competes with the
  individual breach and case-file pages. Noindexing it could pass those
  queries to the specific pages, but it could also lose them. This needs your
  decision.
- **Instagram cluster**: "instagram osint" (35 impressions in 3 months, position
  18.4) lands on /blog/instagram-osint-public-profile-guide.html, whose title
  already matches. Position 18 is an authority problem, not a wording one.
- **/find/github-profile** (135 impressions, position 8.1) and
  **/guides/github-public-profile-privacy-checklist** (85, position 5.6): Search
  Console shows almost no queries for them (the rest are anonymised), so there
  is nothing to match a rewrite to.

# Search Console growth review, 13 October 2026

Live Search Console, Web, three-month range July 21 to October 10:
- 19 clicks, 123 impressions, 15.4% CTR, average position 11.3.
- Homepage: 18 clicks / 106 impressions / position 8.8.
- About: 1 click / 51 impressions / position 6.0.
- Footprint reduction guide: 0 clicks / 19 impressions / position 16.9.
- Guides hub: 0 clicks / 16 impressions / position 8.1.
Page impressions are not additive to property totals. Visible query rows omit anonymized queries; all 14 visible query rows had zero clicks.

## Observed query opportunities
| Query | Impressions | Position |
|---|---:|---:|
| digital footprint checker email | 3 | 28.3 |
| how to clear digital footprint | 2 | 20.5 |
| how to reduce your online footprint | 1 | 10.0 |
| how to reduce your digital footprint | 1 | 18.0 |
| can i find a popular tool to reduce my digital footprint? | 1 | 11.0 |
| user recon | 1 | 9.0 |
| recon social media | 1 | 41.0 |
| recon online | 1 | 49.0 |
| userrecon | 1 | 57.0 |
| email recon | 1 | 78.0 |

Other single-impression queries were intelbase free alternative reddit (2.0), как туда попасть? (3.0), myintred (78.0), reconnaissance website (88.0). These are insufficient evidence to justify new keyword-targeted pages. No volume or traffic uplift forecast is inferred.

## Indexing evidence
15 indexed pages, 3 redirect exclusions. Six valid breadcrumbs and no invalid items in the supplied report. Four videos excluded because they are not on watch pages: best-username-search-tools, instagram-osint-public-profile-guide, free-osint-tools-for-beginners, top-10-osint-tools.

Live direct fetch with Googlebot user-agent returned HTTP 200 and valid XML for sitemap.xml (197 URLs) and sitemap-index.xml (one child). This is a simulated user-agent fetch, not a Google URL Inspection test. Search Console still reports direct sitemap Couldn't fetch, index Success with zero discovered pages. Do not claim that indexing or sitemap report processing is resolved. Existing sitemap submissions already dated October 13; avoid repeated resubmissions.

## Implemented scope
- Email/username title and description on the existing footprint guide.
- Cleanup guide content explaining source removal, search removal, ownership and verification, with contextual links to the email workflow and worksheet.
- Homepage links to the footprint workflow and new video hub.
- Twelve watch pages using existing 32-second captioned videos, matching VideoObject metadata, transcripts, source-guide links and breadcrumbs; one video hub.
- Build-time visible breadcrumb navigation derived from existing structured data, skipping noindex pages and pages already showing breadcrumbs.
- Sitemap now contains 210 canonical pages. These are crawl-eligible URLs, not 210 indexed pages.

## Follow-up measurement
After release, inspect the cleanup guide, email footprint guide and a watch page in URL Inspection. Compare subsequent 28-day impressions and clicks per page/query against this small baseline. Track indexed watch URLs and valid breadcrumb items independently. The old articles remain articles: watch-page eligibility belongs to the new URLs and does not mean the old exclusion report must clear.

Sources: https://developers.google.com/search/docs/appearance/video ; https://developers.google.com/search/docs/appearance/structured-data/breadcrumb ; https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview

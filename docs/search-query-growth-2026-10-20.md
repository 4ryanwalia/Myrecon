# Search query growth: October 20, 2026

## Screenshot baseline
The supplied screenshot shows 10 of 50 queries. Its date range and average positions are not visible. Do not extrapolate rankings or total traffic from it.

| Query | Clicks | Impressions | Primary page |
|---|---:|---:|---|
| ig recon | 1 | 3 | /find/instagram-account |
| username lookup | 0 | 4 | /username-checker.html |
| username checker | 0 | 4 | /username-checker.html |
| instagram osint | 0 | 3 | /find/instagram-account |
| digital footprint checker email | 0 | 3 | /blog/digital-footprint-checker.html |
| osint instagram | 0 | 3 | /find/instagram-account |
| social media checker | 0 | 3 | /username-checker.html |
| ig_recon | 0 | 2 | /find/instagram-account |
| how to clear digital footprint | 0 | 2 | /guides/reduce-your-digital-footprint.html |
| social media username checker | 0 | 2 | /username-checker.html |

IG recon can have navigational intent for another tool. The page explains the generic public-research meaning and does not claim affiliation. No keyword-swapped duplicate pages were added.

## Expanded coverage
- Username page: find accounts by username, reverse username lookup, old social media usernames, username availability versus public presence.
- Instagram page: Instagram OSINT, public Instagram profile lookup, IG recon checklist, Instagram privacy self-audit, verification limits.
- Footprint page: digital footprint checker by email, email and username footprint audit, footprint cleanup, account-removal verification.
- Platform search guide: accounts linked to your own email, email breach check versus profile search, forgotten-account discovery.
- Cleanup guide: how to clear your digital footprint, reduce public exposure, verify removal requests.

These are relevant content targets, not measured search-volume estimates or promises of ranking. Existing URLs retain their canonicals and sitemap inclusion. FAQ structured data follows visible answers. The generators preserve the changes on production builds; source JSON and bundled copies are updated together.

## Validation
- Production static build completed on the current production base. This Windows checkout needed temporary filesystem retries for intermittent UNKNOWN write errors; the retry helper is not part of the patch.
- SEO discovery, editorial quality and editorial evidence suites: 15/15 passed after the build. These are repository assertions, not an actual Lighthouse report or Google ranking score.
- Final browser and preview results are recorded in the PR.
- Unrelated generated build outputs were excluded; no new routes require sitemap additions.

## Release and measurement
Await explicit maintainer merge approval under CONTRIBUTING.md. Local checks do not mean production deployment, indexing or ranking.
After deployment, verify the five public pages return successful responses with the updated headings, canonicals and structured data. Then use Search Console URL Inspection on those exact canonical URLs and request indexing where eligible. Do not repeatedly submit unchanged URLs.
Compare equal 28-day windows after Google recrawls: query impressions, clicks, CTR, average position, and which landing page received each query. Segment by country/device before drawing conclusions. Review both existing screenshot queries and newly appearing related queries. Small samples may fluctuate substantially; there is no fixed indexing or ranking timetable.

Guidance consulted: https://developers.google.com/search/docs/essentials and https://developers.google.com/search/docs/appearance/title-link

## Current production integration
Rebuilt on current origin/main to exclude three unrelated unpublished commits inherited from the original local checkout. Preserved editorial consolidation: username-versus-email content lives on /guides/search-usernames-across-social-platforms, and email footprint content uses /blog/digital-footprint-checker.html. Retired URLs remain redirected. No new duplicate discovery routes or backend changes are included. The validation section applies to this production-based patch.

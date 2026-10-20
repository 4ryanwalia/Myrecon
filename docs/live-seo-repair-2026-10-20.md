# Live SEO repair: October 20, 2026

The live www.myrecon.xyz aliases resolve to Vercel production deployment dpl_652SrqPq3ZveiTP5QsLe2NpJLiWi, which has no gitSource metadata. Its pages match the shared a1c52649-era build, while GitHub main still points to d60c964a. A routine deployment of main or PR14 would replace parts of the live page set. These repairs are therefore based on the shared branch and preserve its changes.

## Verified live failures
Eleven previously published URLs return 404: best-username-search-tools, digital-footprint-checker, free-osint-tools-for-beginners, instagram-osint-public-profile-guide, instagram-stalking-and-privacy, instagram-username-search, osint-tools-for-journalists, reverse-username-search, sherlock-vs-maigret-vs-myrecon, social-media-osint-tools, social-media-username-search (all under /blog/ with .html).

Their original article sources are restored from origin/main, along with the footprint worksheet. Tables use the existing table-wrap container for mobile scrolling. The top-10-osint-tools URL remains intentionally redirected to the comparison article; it is not restored.

The live watch page lacks VideoObject because its generator appends the entity after serializing the graph. The fix serializes after the entity is added. YouTube metadata for JysZLBTrdc4 reports 60 seconds and publication 2026-10-13T11:44:41+05:30, not the old 135-second duration or October18 date. Invented chapters and the false email k-anonymity claim are removed. The player embed remains; contentUrl is omitted because a YouTube webpage is not a video file.

## Validation
- Full static build completed; XML sitemap has419 URLs including all11 restored articles.
- 20 checks pass across SEO discovery and watch-metadata suites. One existing unrelated test fails because it reads web_main.py, absent from this checked-in branch. It was not weakened or removed.
- 12 pages (11 articles and watch) checked in headless Edge at390px and1440px: one H1 each, no page overflow. External resources were blocked for local layout review; this does not test YouTube playback.
- Existing source links and required local assets resolve. No new search ranking is claimed.

## Release state
Prepared in an isolated worktree, with no changes to Gemini's checkout. This is a follow-up to PR13, not a replacement by PR14. Production promotion needs explicit user approval; Google recrawl and ranking remain external outcomes. Browser access to Search Console is currently disabled in Work settings, so URL Inspection/indexing submissions are unverified.

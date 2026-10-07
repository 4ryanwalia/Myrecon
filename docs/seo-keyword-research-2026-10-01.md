# MyRecon search intent and implementation

Research date: October 1, 2026. Evidence comes from public search results and tool pages, not Search Console, paid keyword data or measured monthly volume. Priority below reflects product fit and observed search wording, not proven traffic demand.

| Search wording | Intent | Destination |
| --- | --- | --- |
| username checker, username search, username lookup | Check a known public handle | Homepage tool and `/username-checker.html` |
| social media username checker, search username across platforms | Review supported public profile leads | `/username-checker.html` and `/find/` |
| username availability checker | Choose a registrable handle | Availability explanation on `/username-checker.html`; direct users to official signup |
| Instagram username lookup, TikTok username search | Understand platform-specific public visibility | Existing `/find/instagram-account` and `/find/tiktok-profile` |
| GitHub profile lookup, Reddit username search | Public developer and community profiles | Existing `/find/github-profile` and `/find/reddit-activity` |
| find my old social media accounts | Recover one's own forgotten accounts | `/blog/find-your-own-old-accounts.html` |
| digital footprint checker, digital footprint audit | Review personal public exposure | Homepage and existing audit checklist |
| email breach checker, check email data breach | Review breach exposure and limits | Homepage email tool and `/guides/check-email-data-breach.html` |
| Sherlock alternative, Maigret alternative, WhatsMyName comparison | Compare methods and coverage | Existing `/vs/` library and published benchmark |
| MyRecon, MyRecon OSINT, MyRecon username checker | Brand and product navigation | Homepage entity metadata, about page and tool landing page |

Public research sources:

- [Namechk](https://namechk.com/) uses username and domain name checker wording and targets availability intent.
- [MiniWebtool social media username checker](https://miniwebtool.com/social-media-username-checker/) provides a current example of cross-platform availability wording. This is evidence of search-result terminology, not evidence for its accuracy claims.
- [Digital Footprint Check username search](https://www.digitalfootprintcheck.com/free-username-search) illustrates public username search and digital footprint terminology. MyRecon does not adopt its claims about identifying people or finding all accounts.
- [Google's guide to generative AI optimization](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) supports useful original content, crawlable internal links and standard SEO. Special AI markup and llms.txt are not prerequisites for Google AI features.
- [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) supports canonical absolute URLs, XML escaping and accurate modification dates.

Implemented: improved homepage title, summary and visible keyword context; three additional FAQs with matching structured answers; a substantive username checker page with breadcrumbs, visible questions and JSON-LD; internal links from the homepage and shared footer; corrected llms.txt product summary; sitemap regeneration and handling of reordered noindex directives, external canonicals, refresh pages and XML characters. The build regenerates the landing page before asset versioning and sitemap generation.

The existing library already has unique document titles, metadata and valid JSON-LD. Avoid adding multiple pages that repeat the same answer with a different keyword. No fabricated ratings, search volume, ownership certainty or availability guarantees were added. FAQ markup describes visible content; it does not promise a Google FAQ rich result.

After deployment, submit `https://www.myrecon.xyz/sitemap.xml` in Search Console and inspect the homepage and username-checker page. Measure query impressions, clicks and indexing over time, then improve pages that receive relevant impressions. Local checks cannot establish live indexing, AI citations or ranking gains.

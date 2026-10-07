# MyRecon OSINT search-content release

Twelve new sourced articles cover OSINT tool selection, free tools, social media research, Instagram username lookup, reverse username search, digital-footprint reviews, journalism and privacy. MyRecon appears third in the top-ten list with a visible publisher disclosure and no independent ranking claim.

The blog now groups articles by topic and provides direct answers before the contents navigation, review dates, related reading, accessible comparison tables and matching Article, Breadcrumb, FAQ and tool-list structured data. The homepage, shared footer and username-checker page link into the new content.

Crawler discovery improvements include documented search and AI agents, public-resource access, exclusions for API/source/operator routes, validated canonical targets, XML escaping, honest modification dates, a stable sitemap index and generated canonical article navigation in llms.txt. The breach hub preserves links to earlier archive entries separately from current-feed totals.

## Validation

- Production static build passes and emits 194 canonical sitemap URLs and 21 blog articles.
- Twenty focused publication, crawler, sitemap, IndexNow, editorial and full internal-link discovery tests pass.
- Fifteen affected routes pass browser checks at 375px and 1280px for visible headings, schema parsing, answer placement, contents links, table accessibility and horizontal overflow.
- Source metadata and references were reviewed on 8 October 2026. Candidate keywords are recorded in `seo-osint-keywords-2026-10-08.md`; no measured search-volume data was available.

## Provider limits

Search Console did not respond through the available browser connection. Its sitemap-processing state and Search generative AI control have not been verified for this release. The existing stable sitemap index remains the submission target; IndexNow notification runs after a successful production deployment.

Google's current guidance treats SEO fundamentals as the basis for generative search and does not guarantee crawling, indexing, ranking or serving. llms.txt is an optional navigation convention, and FAQ markup is not a promise of a Google rich result.

References: [Google generative search guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide), [Search generative AI control](https://support.google.com/webmasters/answer/16908024?hl=en), [sitemap requirements](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap), [OpenAI crawler documentation](https://developers.openai.com/api/docs/bots), [Anthropic crawler documentation](https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler).

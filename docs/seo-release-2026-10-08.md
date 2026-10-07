# MyRecon OSINT search-content release

Twelve new sourced articles cover OSINT tool selection, free tools, social media research, Instagram username lookup, reverse username search, digital-footprint reviews, journalism and privacy. MyRecon appears third in the top-ten list with a visible publisher disclosure and no independent ranking claim.

The blog now groups articles by topic and provides direct answers before the contents navigation, review dates, related reading, accessible comparison tables and matching Article, Breadcrumb, FAQ and tool-list structured data. Article navigation and editorial-page footers link into the new content. The follow-up media release restores the homepage byte for byte to its pre-SEO version and preserves tool code.

Crawler discovery improvements include documented search and AI agents, public-resource access, exclusions for API/source/operator routes, validated canonical targets, XML escaping, honest modification dates, a stable sitemap index and generated canonical article navigation in llms.txt. The breach hub preserves links to earlier archive entries separately from current-feed totals.

## Validation

- Production static build passes and emits 194 canonical sitemap URLs and 21 blog articles.
- Twenty-two focused publication, crawler, sitemap, IndexNow, editorial, media and full internal-link discovery tests pass.
- Fifteen affected routes pass browser checks at 375px and 1280px for visible headings, schema parsing, answer placement, contents links, table accessibility and horizontal overflow.
- All twelve new articles include an illustrative photo and an original 32-second MP4 explainer with captions, poster, transcript, VideoObject metadata and image/video sitemap records. Local browser checks verify loaded images and actual video playback at both widths. See `seo-media-release-2026-10-08.md` for assets and prompts.
- Source metadata and references were reviewed on 8 October 2026. Candidate keywords are recorded in `seo-osint-keywords-2026-10-08.md`; no measured search-volume data was available.
- Production deployment for `da41b15573b4d72f35fa4040596aaaa4724eb969` is Ready at `www.myrecon.xyz`. The live browser audit passed the same fifteen routes at both widths, and IndexNow accepted 194 URLs with HTTP 200.
- The repository secret scan passed. Its separate backend CI suite reported 20 failures and 507 passes. Backend code, backend tests, CI configuration and platform catalogue fixtures are unchanged by this release; the failures remain unresolved and are not represented as successful validation.

## Provider limits

Search Console did not respond through the available browser connection. Its sitemap-processing state and Search generative AI control have not been verified for this release. The existing stable sitemap index remains the submission target; IndexNow notification runs after a successful production deployment.

Google's current guidance treats SEO fundamentals as the basis for generative search and does not guarantee crawling, indexing, ranking or serving. llms.txt is an optional navigation convention, and FAQ markup is not a promise of a Google rich result.

References: [Google generative search guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide), [Search generative AI control](https://support.google.com/webmasters/answer/16908024?hl=en), [sitemap requirements](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap), [OpenAI crawler documentation](https://developers.openai.com/api/docs/bots), [Anthropic crawler documentation](https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler).

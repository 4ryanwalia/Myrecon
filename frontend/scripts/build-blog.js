/* Build the MyRecon blog from its hand-written article sources.
 *
 * Source files live in content/blog/<slug>.html. Each starts with a JSON
 * comment containing its title, description, section, and publication dates;
 * the rest is the article body. Output pages are complete, indexable HTML
 * documents in /blog/, with canonical URLs, article metadata, breadcrumbs,
 * and links back into the tool and guide library.
 *
 * Run from frontend/: node scripts/build-blog.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const SOURCE = path.join(ROOT, "content", "blog");
const OUT = path.join(ROOT, "blog");
const SITE = "https://www.myrecon.xyz";
const MEDIA = JSON.parse(fs.readFileSync(path.join(ROOT, 'content/blog-media.json'), 'utf8'));
const PHOTO_ALT = {
  'research-workspace': 'Illustrative research desk with a laptop, phone, camera and notebook.',
  'social-profile-research': 'Illustrative smartphone with a generic public-profile layout beside a laptop and notes.',
  'privacy-workspace': 'Illustrative privacy workspace with a face-down phone, closed laptop and notebook.',
};
const BLOG_CSS_VERSION = require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(ROOT, 'assets/css/blog.css'))).digest('hex').slice(0, 10);

const esc = (value) => String(value == null ? "" : value)
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

const json = (value) => JSON.stringify(value).replace(/</g, "\\u003c");
const textOnly = (value) => String(value).replace(/<[^>]*>/g, " ")
  .replace(/&(?:amp|quot|apos|lt|gt|nbsp);/g, entity => ({'&amp;':'&', '&quot;':'"', '&apos;':"'", '&lt;':'<', '&gt;':'>', '&nbsp;':' '})[entity])
  .replace(/\s+/g, " ").trim();

function validateArticle(meta, body, file) {
  for (const field of ["title", "headline", "description", "category", "datePublished", "dateModified"]) {
    if (typeof meta[field] !== 'string' || !meta[field].trim()) throw new Error(`${file}: missing ${field}`);
  }
  for (const field of ['datePublished', 'dateModified']) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(meta[field]) || new Date(`${meta[field]}T00:00:00Z`).toISOString().slice(0, 10) !== meta[field]) {
      throw new Error(`${file}: invalid ${field}`);
    }
  }
  if (meta.dateModified < meta.datePublished) throw new Error(`${file}: modification precedes publication`);
  if (!body || !/<h2\b/i.test(body) || /<h1\b/i.test(body)) throw new Error(`${file}: article needs section headings and no extra h1`);
  const visible = textOnly(body);
  if (meta.faq !== undefined) {
    if (!Array.isArray(meta.faq) || !meta.faq.length) throw new Error(`${file}: faq must be a nonempty array`);
    for (const item of meta.faq) {
      if (!item.question || !item.answer || !visible.includes(textOnly(item.question)) || !visible.includes(textOnly(item.answer))) {
        throw new Error(`${file}: FAQ metadata must match visible questions and answers`);
      }
    }
  }
  if (meta.tools !== undefined) {
    if (!Array.isArray(meta.tools) || !meta.tools.length) throw new Error(`${file}: tools must be a nonempty array`);
    for (const tool of meta.tools) {
      const url = new URL(tool.url);
      if (url.protocol !== 'https:' || !tool.name || !tool.description || !visible.includes(textOnly(tool.name)) || !body.includes(tool.url)) {
        throw new Error(`${file}: tool metadata must match visible linked tools`);
      }
    }
  }
}

function articleContent(body) {
  const headings = [];
  const ids = new Set([...body.matchAll(/\bid=["']([^"']+)["']/g)].map(match => match[1]));
  const content = body.replace(/<h2\b([^>]*)>([\s\S]*?)<\/h2>/gi, (all, attributes, title) => {
    const existing = attributes.match(/\bid=["']([^"']+)["']/i);
    let id = existing?.[1];
    if (!id) {
      const base = textOnly(title).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'section';
      id = base;
      for (let suffix = 2; ids.has(id); suffix++) id = `${base}-${suffix}`;
      ids.add(id);
    }
    headings.push({ id, title: textOnly(title) });
    return `<h2${attributes}${existing ? '' : ` id="${id}"`}>${title}</h2>`;
  }).replace(/<table\b[\s\S]*?<\/table>/gi, table => `<div class="blog-table-wrap" tabindex="0" role="region" aria-label="Scrollable comparison table">${table}</div>`);
  const toc = headings.length < 3 ? '' : `<nav class="blog-toc" aria-label="On this page"><strong>On this page</strong><ul>${headings.map(heading => `<li><a href="#${esc(heading.id)}">${esc(heading.title)}</a></li>`).join('')}</ul></nav>`;
  return { content, toc };
}

function readArticles() {
  if (!fs.existsSync(SOURCE)) return [];
  return fs.readdirSync(SOURCE)
    .filter((file) => file.endsWith(".html"))
    .map((file) => {
      const slug = file.replace(/\.html$/, "");
      const raw = fs.readFileSync(path.join(SOURCE, file), "utf8");
      const match = raw.match(/^\s*<!--\s*(\{[\s\S]*?\})\s*-->/);
      if (!match) throw new Error(`${file}: expected a JSON metadata comment at the top`);
      let meta;
      try { meta = JSON.parse(match[1]); }
      catch (error) { throw new Error(`${file}: invalid metadata JSON (${error.message})`); }
      const body = raw.slice(match[0].length).trim();
      validateArticle(meta, body, file);
      if (MEDIA[slug]) {
        const media = MEDIA[slug];
        if (!PHOTO_ALT[media.photo] || !media.title || !media.description || !Array.isArray(media.steps) || media.steps.length !== 4 || !Number.isFinite(new Date(media.uploadDate).getTime())) throw new Error(`${file}: invalid article media metadata`);
        for (const asset of [`assets/img/blog/${media.photo}.webp`, `assets/media/blog/${slug}.mp4`, `assets/media/blog/${slug}-poster.jpg`, `assets/media/blog/${slug}.vtt`]) {
          if (!fs.existsSync(path.join(ROOT, asset))) throw new Error(`${file}: missing media asset ${asset}`);
        }
      }
      return { ...meta, slug, body, media: MEDIA[slug], url: `${SITE}/blog/${slug}.html` };
    })
    .sort((a, b) => b.datePublished.localeCompare(a.datePublished) || a.headline.localeCompare(b.headline));
}

function schema(article) {
  const value = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: article.headline,
    description: article.description,
    datePublished: article.datePublished,
    dateModified: article.dateModified,
    articleSection: article.category,
    inLanguage: "en",
    author: { "@type": "Organization", name: "MyRecon", url: `${SITE}/about.html` },
    publisher: { "@type": "Organization", "@id": `${SITE}/#organization`, name: "MyRecon", url: `${SITE}/` },
    isPartOf: { "@id": `${SITE}/#website` },
    mainEntityOfPage: article.url,
    ...(article.media ? { image: `${SITE}/assets/img/blog/${article.media.photo}.webp`, video: {'@id': `${article.url}#explainer`} } : {}),
  };
  return json(value);
}

function additionalSchema(article) {
  const values = [];
  if (article.media) values.push({
    '@context': 'https://schema.org', '@type': 'VideoObject', '@id': `${article.url}#explainer`,
    name: article.media.title, description: article.media.description, uploadDate: article.media.uploadDate,
    thumbnailUrl: `${SITE}/assets/media/blog/${article.slug}-poster.jpg`, contentUrl: `${SITE}/assets/media/blog/${article.slug}.mp4`,
    duration: 'PT32S', inLanguage: 'en', isFamilyFriendly: true, isPartOf: {'@id': `${article.url}`},
    transcript: article.media.steps.map(([heading, text]) => `${heading}. ${text}`).join(' '),
    publisher: {'@type': 'Organization', name: 'MyRecon', url: `${SITE}/`},
  });
  if (article.faq?.length) values.push({
    '@context': 'https://schema.org', '@type': 'FAQPage', '@id': `${article.url}#faq`,
    mainEntity: article.faq.map(item => ({ '@type': 'Question', name: item.question, acceptedAnswer: { '@type': 'Answer', text: item.answer } })),
  });
  if (article.tools?.length) values.push({
    '@context': 'https://schema.org', '@type': 'ItemList', name: article.headline,
    description: 'Publisher-selected editorial list by MyRecon. The order is not an independent accuracy or performance ranking.',
    numberOfItems: article.tools.length, itemListOrder: 'https://schema.org/ItemListOrderAscending',
    itemListElement: article.tools.map((tool, i) => ({ '@type': 'ListItem', position: i + 1, item: { '@type': 'Thing', name: tool.name, url: tool.url, description: tool.description } })),
  });
  return values.map(value => `  <script type="application/ld+json">${json(value)}</script>\n`).join('');
}

function breadcrumb(article) {
  const value = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "MyRecon", item: `${SITE}/` },
      { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE}/blog/` },
      { "@type": "ListItem", position: 3, name: article.headline, item: article.url },
    ],
  };
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

function shellHead({ title, description, url, article, crumbs }) {
  const ogType = article ? "article" : "website";
  const blogCurrent = article ? "" : ' aria-current="page"';
  return `<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-3L8YYC6NKF"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    var analyticsPage = new URL(window.location.href);
    var analyticsReferrer = document.referrer ? new URL(document.referrer).origin : '';
    gtag('config', 'G-3L8YYC6NKF', {
      page_location: analyticsPage.origin + analyticsPage.pathname,
      page_referrer: analyticsReferrer
    });
  </script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${esc(title)}</title>
  <meta name="description" content="${esc(description)}">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
  <meta name="theme-color" content="#f7f7f4">
  <link rel="canonical" href="${esc(url)}">
  <meta property="og:type" content="${ogType}">
  <meta property="og:site_name" content="MyRecon">
  <meta property="og:title" content="${esc(title)}">
  <meta property="og:description" content="${esc(description)}">
  <meta property="og:url" content="${esc(url)}">
  <meta property="og:image" content="${SITE}/assets/img/${article?.media ? `blog/${article.media.photo}.webp` : 'og-image.png'}">
  <meta property="og:image:width" content="${article?.media ? 1600 : 1200}">
  <meta property="og:image:height" content="${article?.media ? 900 : 630}">
  <meta property="og:image:alt" content="${article?.media ? PHOTO_ALT[article.media.photo] : 'MyRecon: public-source research and online privacy'}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="${esc(title)}">
  <meta name="twitter:description" content="${esc(description)}">
  <meta name="twitter:image" content="${SITE}/assets/img/${article?.media ? `blog/${article.media.photo}.webp` : 'og-image.png'}">
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg?v=2">
  <link rel="apple-touch-icon" href="/assets/img/favicon.svg?v=2">
  <link rel="manifest" href="/site.webmanifest">
  <style>*{box-sizing:border-box;margin:0;padding:0}</style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/styles.css?v=16">
  <link rel="stylesheet" href="/assets/css/fx.css?v=10">
  <link rel="stylesheet" href="/assets/css/blog.css${article?.media ? `?v=${BLOG_CSS_VERSION}` : ''}">
  <meta name="google-adsense-account" content="ca-pub-6109270472398539">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6109270472398539" crossorigin="anonymous"></script>
${article ? `  <meta property="article:published_time" content="${esc(article.datePublished)}T00:00:00Z">\n  <meta property="article:modified_time" content="${esc(article.dateModified)}T00:00:00Z">\n  <meta property="article:section" content="${esc(article.category)}">\n  <script type="application/ld+json">${schema(article)}</script>\n  <script type="application/ld+json">${breadcrumb(article)}</script>\n${additionalSchema(article)}` : `  <script type="application/ld+json">${crumbs}</script>\n`}</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav">
    <div class="container nav-inner">
      <a class="brand" href="/" aria-label="MyRecon OSINT: home"><img class="logo" src="/assets/img/logo.svg?v=2" alt="" width="32" height="32"> MyRecon <small>OSINT</small></a>
      <nav class="nav-links" id="navLinks" aria-label="Primary"><a href="/#tool">Tool</a><a href="/services.html">Services</a><a href="/breaches/">Breaches</a><a href="/guides/">Guides</a><a href="/blog/"${blogCurrent}>Blog</a><a href="/vs/">Compare</a><a href="/pricing.html">Pricing</a></nav>
      <button class="icon-btn" id="themeToggle" type="button" aria-label="Toggle theme"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" stroke-linejoin="round"/></svg></button>
      <button class="icon-btn nav-toggle" id="navToggle" type="button" aria-label="Toggle menu"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round"/></svg></button>
    </div>
  </header>`;
}

function shellFoot() {
  return `
  <footer class="footer"><div class="container"><div class="footer-bottom">
    <span>&copy; 2026 MyRecon · myrecon.xyz</span>
    <span><a href="/blog/" style="color:var(--text-dim)">Blog</a> · <a href="/guides/" style="color:var(--text-dim)">Guides</a> · <a href="/vs/" style="color:var(--text-dim)">Compare</a> · <a href="/services.html" style="color:var(--text-dim)">Removal service</a> · <a href="/privacy.html" style="color:var(--text-dim)">Privacy</a> · <a href="/terms.html">Terms</a></span>
  </div></div></footer>
  <script src="/assets/js/env.js?v=10"></script>
  <script src="/assets/js/config.js?v=10"></script>
  <script src="/assets/js/app.js?v=23"></script>
  <script src="/assets/js/consent.js?v=10"></script>
  <script src="/assets/js/fx.js?v=8" defer></script>
</body>
</html>
`;
}

function articlePage(article, articles = []) {
  const displayDate = new Date(`${article.dateModified}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
  const {content, toc} = articleContent(article.body);
  const firstHeading = content.search(/<h2\b/i);
  const firstIsQuickAnswer = firstHeading >= 0 && /^<h2\b[^>]*id="quick-answer"/i.test(content.slice(firstHeading));
  const tocPosition = firstIsQuickAnswer ? content.indexOf('<h2', firstHeading + 4) : firstHeading;
  const photo = article.media ? `<figure class="blog-photo"><img src="/assets/img/blog/${article.media.photo}.webp" alt="${PHOTO_ALT[article.media.photo]}" width="1600" height="900" loading="lazy" decoding="async"><figcaption>AI-created editorial image. The devices and profile layout are illustrative.</figcaption></figure>` : '';
  const navigableContent = tocPosition >= 0 ? `${content.slice(0, tocPosition)}${photo}${toc}\n${content.slice(tocPosition)}` : content;
  const explainer = article.media ? `<section class="blog-explainer" aria-labelledby="videoHeading"><span class="kicker">Watch the workflow</span><h2 id="videoHeading">${esc(article.media.title)}</h2><p>${esc(article.media.description)}</p><video controls playsinline preload="none" width="1280" height="720" poster="/assets/media/blog/${article.slug}-poster.jpg" aria-label="${esc(article.media.title)}"><source src="/assets/media/blog/${article.slug}.mp4" type="video/mp4"><track kind="captions" src="/assets/media/blog/${article.slug}.vtt" srclang="en" label="English" default><p><a href="/assets/media/blog/${article.slug}.mp4">Download the explainer video</a>.</p></video><p class="blog-media-note">32 seconds · Silent video with on-screen text and English captions.</p><details class="blog-transcript"><summary>Read the video transcript</summary><ol>${article.media.steps.map(([heading, text]) => `<li><strong>${esc(heading)}.</strong> ${esc(text)}</li>`).join('')}</ol></details></section>` : '';
  const related = articles.filter(item => item.slug !== article.slug).sort((a, b) => Number(b.category === article.category) - Number(a.category === article.category)).slice(0, 3);
  return `${shellHead({ title: article.title, description: article.description, url: article.url, article })}
  <main id="main" class="container">
    <article class="article">
      <nav class="blog-breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <a href="/blog/">OSINT and privacy articles</a></nav>
      <span class="kicker">${esc(article.category)}</span>
      <h1>${esc(article.headline)}</h1>
      <p class="meta">Updated <time datetime="${esc(article.dateModified)}">${displayDate}</time> · <a href="/about.html">MyRecon editorial</a></p>
      ${navigableContent}${explainer ? `\n      ${explainer}` : ''}
      <div class="callout">
        <p><strong>Use these checks for your own accounts or work you are authorised to do.</strong> MyRecon reports public-source results; a matching handle is not proof that two accounts belong to the same person. See our <a href="/terms.html">terms</a> and <a href="/privacy.html">privacy policy</a>.</p>
      </div>
      ${related.length ? `<aside class="blog-related" aria-label="Related articles"><h2>Continue your research</h2><ul>${related.map(item => `<li><a href="/blog/${item.slug}.html">${esc(item.headline)}</a></li>`).join('')}</ul></aside>` : ''}
      <p><a href="/blog/">More from the MyRecon blog</a> · <a href="/guides/">Browse all guides</a></p>
    </article>
  </main>
${shellFoot()}`;
}

function indexPage(articles) {
  const url = `${SITE}/blog/`;
  const description = "Compare OSINT tools, search social media usernames, understand Instagram public profiles and check your digital footprint with sourced MyRecon articles.";
  const collection = JSON.stringify({
    "@context": "https://schema.org", "@type": "CollectionPage", name: "MyRecon Blog: OSINT Tools, Username Search and Privacy",
    description, url, isPartOf: { "@id": `${SITE}/#website` }, publisher: { "@id": `${SITE}/#organization` },
  }).replace(/</g, "\\u003c");
  const list = JSON.stringify({
    "@context": "https://schema.org", "@type": "ItemList", name: "MyRecon OSINT and privacy articles",
    itemListElement: articles.map((article, i) => ({ "@type": "ListItem", position: i + 1, name: article.headline, url: article.url })),
  }).replace(/</g, "\\u003c");
  const categories = [...new Set(articles.map(article => article.category))];
  const categoryId = category => `topic-${category.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  const html = `${shellHead({ title: "OSINT Tools, Username Search and Privacy Blog | MyRecon", description, url, crumbs: collection })}
  <main id="main" class="container prose" style="padding-top:44px;padding-bottom:56px">
    <span class="kicker" style="color:var(--accent);font-weight:700;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase">MyRecon Blog</span>
    <h1 style="font-size:clamp(1.9rem,4vw,2.6rem);font-weight:800;letter-spacing:-.02em;margin:8px 0 10px">OSINT tools, username search and online privacy</h1>
    <p class="sub" style="max-width:70ch">Choose a research workflow, compare public-source tools, search social media usernames and reduce your own digital footprint. Our articles explain what a result supports, what remains unknown and how to check the original source.</p>
    <section class="guide-card" style="margin:24px 0">
      <p><strong>Start with your own footprint.</strong> MyRecon's username search checks public profile pages; it does not reveal private content or prove identity. For cleanup help, our service works only on your own footprint or one you are formally authorised to manage.</p>
      <p><a href="/#tool">Run a username self-audit</a> · <a href="/services.html">Learn about footprint removal support</a> · <a href="/vs/">Compare MyRecon with other tools</a></p>
    </section>
    <script type="application/ld+json">${list}</script>
    <nav class="blog-topics" aria-label="Article topics">${categories.map(category => `<a href="#${categoryId(category)}">${esc(category)}</a>`).join('')}</nav>
${categories.map(category => `<section class="blog-category" aria-labelledby="${categoryId(category)}"><h2 id="${categoryId(category)}">${esc(category)}</h2><div class="guide-grid">${articles.filter(article => article.category === category).map(article => `<a class="guide-card" href="/blog/${article.slug}.html"><h3>${esc(article.headline)}</h3><p>${esc(article.description)}</p><span class="read">Read article →</span></a>`).join('\n')}</div></section>`).join('\n')}
    <h2 style="font-size:1.2rem;font-weight:700;margin:40px 0 10px">Explore MyRecon</h2>
    <p><a href="/guides/">Privacy and security guides</a> · <a href="/vs/">Tool comparisons</a> · <a href="/breaches/">Breach archive</a> · <a href="/services.html">Removal service</a></p>
  </main>
${shellFoot()}`;
  // Add ItemList after the schema script in the document head for crawlers.
  return html.replace(`  <script type="application/ld+json">${collection}</script>\n</head>`, `  <script type="application/ld+json">${collection}</script>\n  <script type="application/ld+json">${list}</script>\n</head>`)
    .replace(`    <script type="application/ld+json">${list}</script>\n`, "");
}

function main() {
  const articles = readArticles();
  if (articles.length < 8) throw new Error(`Expected at least 8 complete articles; found ${articles.length}`);
  fs.mkdirSync(OUT, { recursive: true });
  const expected = new Set(["index.html", ...articles.map((article) => `${article.slug}.html`)]);
  for (const file of fs.readdirSync(OUT)) {
    if (file.endsWith(".html") && !expected.has(file)) fs.unlinkSync(path.join(OUT, file));
  }
  for (const article of articles) fs.writeFileSync(path.join(OUT, `${article.slug}.html`), articlePage(article, articles), "utf8");
  fs.writeFileSync(path.join(OUT, "index.html"), indexPage(articles), "utf8");
  console.log(`[blog] ${articles.length} original articles and /blog/ index written`);
}

if (require.main === module) main();
module.exports = { validateArticle, articleContent, additionalSchema, readArticles };

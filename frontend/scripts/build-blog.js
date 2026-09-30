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

const esc = (value) => String(value == null ? "" : value)
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

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
      for (const field of ["title", "headline", "description", "category", "datePublished", "dateModified"]) {
        if (!meta[field]) throw new Error(`${file}: missing ${field}`);
      }
      if (!body || !/<h2\b/i.test(body)) throw new Error(`${file}: article needs body text and section headings`);
      return { ...meta, slug, body, url: `${SITE}/blog/${slug}.html` };
    })
    .sort((a, b) => a.headline.localeCompare(b.headline));
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
    author: { "@type": "Organization", name: "MyRecon" },
    publisher: { "@id": `${SITE}/#organization` },
    isPartOf: { "@id": `${SITE}/#website` },
    mainEntityOfPage: article.url,
  };
  return JSON.stringify(value).replace(/</g, "\\u003c");
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
  <meta name="robots" content="index, follow">
  <meta name="theme-color" content="#f7f7f4">
  <link rel="canonical" href="${esc(url)}">
  <meta property="og:type" content="${ogType}">
  <meta property="og:site_name" content="MyRecon">
  <meta property="og:title" content="${esc(title)}">
  <meta property="og:description" content="${esc(description)}">
  <meta property="og:url" content="${esc(url)}">
  <meta property="og:image" content="${SITE}/assets/img/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="MyRecon: public-source research and online privacy">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="${esc(title)}">
  <meta name="twitter:description" content="${esc(description)}">
  <meta name="twitter:image" content="${SITE}/assets/img/og-image.png">
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg?v=2">
  <link rel="apple-touch-icon" href="/assets/img/favicon.svg?v=2">
  <link rel="manifest" href="/site.webmanifest">
  <style>*{box-sizing:border-box;margin:0;padding:0}</style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/styles.css?v=16">
  <link rel="stylesheet" href="/assets/css/fx.css?v=10">
  <meta name="google-adsense-account" content="ca-pub-6109270472398539">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6109270472398539" crossorigin="anonymous"></script>
${article ? `  <script type="application/ld+json">${schema(article)}</script>\n  <script type="application/ld+json">${breadcrumb(article)}</script>\n` : `  <script type="application/ld+json">${crumbs}</script>\n`}</head>
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

function articlePage(article) {
  const displayDate = new Date(`${article.datePublished}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
  return `${shellHead({ title: article.title, description: article.description, url: article.url, article })}
  <main id="main" class="container">
    <article class="article">
      <span class="kicker">${esc(article.category)}</span>
      <h1>${esc(article.headline)}</h1>
      <p class="meta"><time datetime="${esc(article.datePublished)}">${displayDate}</time> · MyRecon editorial</p>
      ${article.body}
      <div class="callout">
        <p><strong>Use these checks for your own accounts or work you are authorised to do.</strong> MyRecon reports public-source results; a matching handle is not proof that two accounts belong to the same person. See our <a href="/terms.html">terms</a> and <a href="/privacy.html">privacy policy</a>.</p>
      </div>
      <p><a href="/blog/">More from the MyRecon blog</a> · <a href="/guides/">Browse all guides</a></p>
    </article>
  </main>
${shellFoot()}`;
}

function indexPage(articles) {
  const url = `${SITE}/blog/`;
  const description = "Practical MyRecon articles on online privacy, public-profile self-audits, account deletion and safer username habits. Written for people managing their own digital footprint.";
  const collection = JSON.stringify({
    "@context": "https://schema.org", "@type": "CollectionPage", name: "MyRecon Blog: Privacy and Account Cleanup",
    description, url, isPartOf: { "@id": `${SITE}/#website` }, publisher: { "@id": `${SITE}/#organization` },
  }).replace(/</g, "\\u003c");
  const list = JSON.stringify({
    "@context": "https://schema.org", "@type": "ItemList", name: "MyRecon privacy and account cleanup articles",
    itemListElement: articles.map((article, i) => ({ "@type": "ListItem", position: i + 1, name: article.headline, url: article.url })),
  }).replace(/</g, "\\u003c");
  const html = `${shellHead({ title: "MyRecon Blog: Privacy, Instagram and Account Cleanup", description, url, crumbs: collection })}
  <main id="main" class="container prose" style="padding-top:44px;padding-bottom:56px">
    <span class="kicker" style="color:var(--accent);font-weight:700;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase">MyRecon Blog</span>
    <h1 style="font-size:clamp(1.9rem,4vw,2.6rem);font-weight:800;letter-spacing:-.02em;margin:8px 0 10px">Privacy, public profiles and account cleanup</h1>
    <p class="sub" style="max-width:70ch">Practical guides for understanding your own public footprint, protecting accounts you control, and closing profiles you no longer need. These articles focus on consent-based self-audits and verifiable public information.</p>
    <section class="guide-card" style="margin:24px 0">
      <p><strong>Start with your own footprint.</strong> MyRecon's username search checks public profile pages; it does not reveal private content or prove identity. For cleanup help, our service works only on your own footprint or one you are formally authorised to manage.</p>
      <p><a href="/#tool">Run a username self-audit</a> · <a href="/services.html">Learn about footprint removal support</a> · <a href="/vs/">Compare MyRecon with other tools</a></p>
    </section>
    <script type="application/ld+json">${list}</script>
    <div class="guide-grid">
${articles.map((article) => `      <a class="guide-card" href="/blog/${article.slug}.html"><span class="kicker">${esc(article.category)}</span><h2>${esc(article.headline)}</h2><p>${esc(article.description)}</p><span class="read">Read article →</span></a>`).join("\n")}
    </div>
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
  for (const article of articles) fs.writeFileSync(path.join(OUT, `${article.slug}.html`), articlePage(article), "utf8");
  fs.writeFileSync(path.join(OUT, "index.html"), indexPage(articles), "utf8");
  console.log(`[blog] ${articles.length} original articles and /blog/ index written`);
}

main();

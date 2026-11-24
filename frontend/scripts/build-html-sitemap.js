/* Build the complete HTML Directory / Sitemap page for crawlers and users.
 *
 * Why this is crucial for crawl throughput:
 * Search engines (especially Googlebot) discover pages primarily through in-document
 * hyperlinks from high-authority pages. While XML sitemaps provide an advisory list,
 * an HTML directory with crawlable <a> tags provides direct DOM pathways for Googlebot
 * to crawl and index public pages. Crawl frequency and indexing remain decisions made by search engines.
 *
 * Run from frontend/: node scripts/build-html-sitemap.js
 */

const fs = require('fs');
const path = require('path');
const { attribute, decodeHtml, isNoindex } = require('./build-sitemap');

const ROOT = path.resolve(__dirname, '..');
const SITE = 'https://www.myrecon.xyz';
const TITLE = 'MyRecon Directory | OSINT Tools, Guides and Breaches';
const DESCRIPTION = 'Find MyRecon’s OSINT tools, profile guides, privacy checklists and breach reports. Search the directory by topic, platform or incident name.';

function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function getPageMetadata(file) {
  const html = fs.readFileSync(file, 'utf8');
  if (isNoindex(html)) return null;
  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const title = titleMatch ? decodeHtml(titleMatch[1]).trim().replace(/\s*\|\s*MyRecon\s*$/i, '') : path.basename(file, '.html');
  
  const cm = html.match(/<link[^>]*rel=["']canonical["'][^>]*href=["']([^"']*)["']/i)
    || html.match(/<link[^>]*href=["']([^"']*)["'][^>]*rel=["']canonical["']/i);
  let url = cm ? cm[1].replace(SITE, '') : '/' + path.relative(ROOT, file).replace(/\\/g, '/');
  if (url === '/index.html') url = '/';

  const descTag = (html.match(/<meta\b[^>]*>/gi) || [])
    .find(tag => attribute(tag, 'name')?.toLowerCase() === 'description');
  const desc = decodeHtml(attribute(descTag || '', 'content') || '').trim();

  return { title, url, desc, file };
}

function walkDir(dir, relPrefix = '') {
  const pages = [];
  if (!fs.existsSync(dir)) return pages;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (['node_modules', '.git', '.vercel', 'content', 'data', 'scripts', 'tests', 'assets', 'worker-console'].includes(entry.name)) continue;
      pages.push(...walkDir(path.join(dir, entry.name), path.join(relPrefix, entry.name)));
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      if (['404.html', 'ops.html', 'directory.html', 'sitemap.html'].includes(entry.name)) continue;
      const full = path.join(dir, entry.name);
      const metadata = getPageMetadata(full);
      if (metadata) pages.push(metadata);
    }
  }
  return pages;
}

function main() {
  const allPages = walkDir(ROOT);

  // Group pages by directory / topic
  const categories = {
    core: {
      name: 'Core OSINT Intelligence & Audit Tools',
      jump: 'Tools',
      description: 'Zero-install browser tools for username sweeps, breach detection, password audits, and digital footprint analysis.',
      pages: [],
    },
    breaches: {
      name: 'Data Breach Analyses & Incident Archive',
      jump: 'Breach archive',
      description: 'Technical analyses and credential exposure breakdown across 50+ major public data breaches.',
      pages: [],
    },
    caseFiles: {
      name: 'Breach Case Files & Historical Studies',
      jump: 'Case files',
      description: 'In-depth historical investigations covering attack vectors, regulatory outcomes, and defense lessons.',
      pages: [],
    },
    find: {
      name: 'Social Media & Platform Lookup Guides',
      jump: 'Platform lookups',
      description: 'Platform-specific guides to discovering accounts, handles, and public profile visibility.',
      pages: [],
    },
    guides: {
      name: 'OSINT & Cybersecurity Investigation Guides',
      jump: 'Guides',
      description: 'Defensive methodologies, source verification protocols, and personal security workflows.',
      pages: [],
    },
    privacy: {
      name: 'Privacy Protection & Data Broker Opt-Outs',
      jump: 'Privacy',
      description: 'Step-by-step removal guides for people-search sites, data brokers, and public search records.',
      pages: [],
    },
    vs: {
      name: 'OSINT Tool Technical Comparisons',
      jump: 'Comparisons',
      description: 'Benchmark comparisons and feature evaluations against CLI scripts and commercial scanners.',
      pages: [],
    },
    blog: {
      name: 'Investigative Blog & Research Articles',
      jump: 'Articles',
      description: 'Original research articles on digital privacy, threat intelligence, and OSINT techniques.',
      pages: [],
    },
    videos: {
      name: 'OSINT Video Walkthroughs & Explainers',
      jump: 'Videos',
      description: 'Short captioned video walkthroughs covering public username checks, profile verification, and digital footprint cleanup.',
      pages: [],
    },
  };

  for (const page of allPages) {
    const u = page.url;
    if (u.startsWith('/breaches/case-files/')) {
      categories.caseFiles.pages.push(page);
    } else if (u.startsWith('/breaches/')) {
      categories.breaches.pages.push(page);
    } else if (u.startsWith('/find/')) {
      categories.find.pages.push(page);
    } else if (u.startsWith('/guides/')) {
      categories.guides.pages.push(page);
    } else if (u.startsWith('/privacy/')) {
      categories.privacy.pages.push(page);
    } else if (u.startsWith('/vs/')) {
      categories.vs.pages.push(page);
    } else if (u.startsWith('/blog/')) {
      categories.blog.pages.push(page);
    } else if (u.startsWith('/videos/') || u === '/watch.html') {
      categories.videos.pages.push(page);
    } else {
      categories.core.pages.push(page);
    }
  }

  // Sort each category by title
  for (const cat of Object.values(categories)) {
    cat.pages.sort((a, b) => a.title.localeCompare(b.title));
  }

  const populatedCategories = Object.entries(categories).filter(([, cat]) => cat.pages.length > 0);
  const categoryLinks = populatedCategories
    .map(([key, cat]) => `<a class="btn btn-ghost btn-sm" href="#${esc(key)}">${esc(cat.jump)}</a>`)
    .join('\n');
  const categoryCards = populatedCategories
    .map(([key, cat]) => {
      const items = cat.pages
        .map(
          (p) =>
            `<li class="directory-item"><a href="${esc(p.url)}">${esc(p.title)}</a>${
              p.desc ? `<p class="directory-item-desc">${esc(p.desc)}</p>` : ''
            }</li>`
        )
        .join('\n');

      return `
    <section class="directory-section" id="${esc(key)}">
      <h2>${esc(cat.name)} <span class="directory-count">(${cat.pages.length})</span></h2>
      <p class="directory-section-desc">${esc(cat.description)}</p>
      <ul class="directory-grid">
        ${items}
      </ul>
    </section>`;
    })
    .join('\n');

  const jsonLd = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'WebPage',
        '@id': `${SITE}/directory.html#page`,
        url: `${SITE}/directory.html`,
        name: TITLE,
        description: DESCRIPTION,
        dateModified: '2026-11-23',
        inLanguage: 'en',
        isPartOf: { '@id': `${SITE}/#website` },
        publisher: {
          '@type': 'Organization',
          '@id': `${SITE}/#organization`,
          name: 'MyRecon',
          url: `${SITE}/`,
          logo: {
            '@type': 'ImageObject',
            url: `${SITE}/assets/img/og-image.png`,
            width: 1200,
            height: 630,
          },
        },
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'MyRecon', item: `${SITE}/` },
          { '@type': 'ListItem', position: 2, name: 'Directory', item: `${SITE}/directory.html` },
        ],
      },
      {
        '@type': 'CollectionPage',
        '@id': `${SITE}/directory.html#collection`,
        name: 'MyRecon Public Intelligence Directory',
        hasPart: Object.values(categories).flatMap((c) =>
          c.pages.map((p) => ({
            '@type': 'WebPage',
            name: p.title,
            url: `${SITE}${p.url}`,
          }))
        ),
      },
    ],
  };

  const html = `<!DOCTYPE html>
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
  <title>${esc(TITLE)}</title>
  <meta name="description" content="${esc(DESCRIPTION)}">
  <meta name="robots" content="noindex, follow">
  <meta name="theme-color" content="#f7f7f4">
  <link rel="canonical" href="${SITE}/directory.html">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">
  <link rel="manifest" href="/site.webmanifest">
  <style>*{box-sizing:border-box;margin:0;padding:0}</style>
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="MyRecon">
  <meta property="og:locale" content="en_US">
  <meta property="og:title" content="${esc(TITLE)}">
  <meta property="og:description" content="${esc(DESCRIPTION)}">
  <meta property="og:url" content="${SITE}/directory.html">
  <meta property="og:image" content="${SITE}/assets/img/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="${esc(TITLE)}">
  <meta name="twitter:description" content="${esc(DESCRIPTION)}">
  <meta name="twitter:image" content="${SITE}/assets/img/og-image.png">
  <link rel="stylesheet" href="/assets/css/styles.css">
  <link rel="stylesheet" href="/assets/css/fx.css">
  <link rel="stylesheet" href="/assets/css/site-footer.css">
  <link rel="stylesheet" href="/assets/css/discovery.css">
  <style>
    .directory-hero { padding: 48px 0 24px; text-align: left; }
    .directory-hero h1 { font-size: 2.2rem; font-weight: 700; margin-bottom: 12px; color: var(--text); }
    .directory-hero p { font-size: 1.1rem; color: var(--text-dim); max-width: 800px; line-height: 1.6; }
    .directory-filter { margin: 0 0 20px; max-width: 36rem; }
    .directory-filter label { display: block; font-weight: 650; margin-bottom: 6px; }
    .directory-filter-row { display: flex; gap: 8px; }
    .directory-filter-row input { flex: 1; min-width: 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); font: inherit; }
    .directory-filter-row input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .directory-filter [role="status"] { color: var(--text-dim); margin-top: 8px; }
    .directory-jump { display: flex; flex-wrap: wrap; gap: 8px; }
    .directory-filter[hidden], .directory-jump[hidden], .directory-section[hidden], .directory-item[hidden] { display: none; }
    .directory-section { margin-top: 32px; border-top: 1px solid var(--border); padding-top: 24px; scroll-margin-top: 85px; }
    .directory-section h2 { font-size: 1.5rem; font-weight: 600; margin-bottom: 6px; color: var(--text); }
    .directory-count { font-size: 1rem; color: var(--text-dim); font-weight: 400; }
    .directory-section-desc { font-size: 0.95rem; color: var(--text-dim); margin-bottom: 20px; }
    .directory-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); gap: 16px; list-style: none; padding: 0; margin: 0; }
    .directory-item { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; transition: border-color 0.2s, box-shadow 0.2s; }
    .directory-item:hover { border-color: var(--accent); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
    .directory-item a { font-weight: 600; color: var(--accent); text-decoration: none; display: block; margin-bottom: 6px; line-height: 1.4; }
    .directory-item a:hover { text-decoration: underline; }
    .directory-item-desc { font-size: 0.85rem; color: var(--text-dim); line-height: 1.4; margin: 0; }
  </style>
  <script type="application/ld+json">${JSON.stringify(jsonLd).replace(/</g, '\\u003c')}</script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav">
    <div class="container nav-inner">
      <a class="brand" href="/" aria-label="MyRecon OSINT: home"><img class="logo" src="/assets/img/logo.svg" alt="" width="32" height="32"> MyRecon <small>OSINT</small></a>
      <nav class="nav-links" id="navLinks" aria-label="Primary"><a href="/#tool">Tool</a><a href="/services.html">Services</a><a href="/breaches/">Breaches</a><a href="/guides/">Guides</a><a href="/app.html">App</a><a href="/blog/">Blog</a><a href="/pricing">Pricing</a><a href="/about.html">About</a></nav>
      <button class="icon-btn" id="themeToggle" type="button" aria-label="Toggle theme"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" stroke-linejoin="round"/></svg></button>
      <button class="icon-btn nav-toggle" id="navToggle" type="button" aria-label="Toggle menu"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round"/></svg></button>
    </div>
  </header>
  <main id="main" class="container">
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="/">MyRecon</a> / <span aria-current="page">Site Directory</span>
    </nav>
    <header class="directory-hero">
      <h1>MyRecon directory</h1>
      <p>Find an OSINT tool, a guide for a specific platform, or a report about a data breach.</p>
    </header>
    <form class="directory-filter" role="search" aria-label="MyRecon directory" autocomplete="off" hidden>
      <label for="directory-filter">Filter by topic or name</label>
      <div class="directory-filter-row">
        <input id="directory-filter" type="search" placeholder="e.g. GitHub, Ashley Madison">
        <button class="btn btn-ghost btn-sm" type="button">Clear</button>
      </div>
      <p role="status"></p>
    </form>
    <nav class="directory-jump" aria-label="Directory categories">${categoryLinks}</nav>

    ${categoryCards}
  </main>
  <script src="/assets/js/editorial-shell.js" defer></script>
  <script src="/assets/js/directory-filter.js" defer></script>
  <script src="/assets/js/consent.js"></script>
  <script src="/assets/js/fx.js" defer></script>
</body>
</html>
`;

  fs.writeFileSync(path.join(ROOT, 'directory.html'), html, 'utf8');
  const legacySitemapHtml = path.join(ROOT, 'sitemap.html');
  if (fs.existsSync(legacySitemapHtml)) fs.unlinkSync(legacySitemapHtml);
  console.log(`[html-sitemap] Built directory.html with ${allPages.length} public URLs across 9 categories`);
}

if (require.main === module) main();
module.exports = { main, getPageMetadata };

/* sitemap.xml, generated from what is actually on disk.
 *
 * WHY THIS EXISTS
 * The sitemap used to be hand-maintained, with build-breaches.js rewriting a
 * marked-off block in the middle of it. That works right up until somebody
 * adds a page and forgets the sitemap, which had already happened: 27 of the
 * 40 entries carried no <lastmod> at all, so every one of them told crawlers
 * nothing about freshness.
 *
 * Walking the output directory instead means a new .html file is in the
 * sitemap the moment it ships, and a deleted one leaves. There is no list to
 * keep in step because there is no list.
 *
 * WHERE <lastmod> COMES FROM:
 *   The latest valid, non-future date from the page's JSON-LD, its tracked
 *   content commit, or the build's changed-content date. Checkout and build
 *   mtimes are not content dates. When no reliable date exists, omit lastmod.
 *
 * Stamping today's date on everything would be the easy version and is worse
 * than useless: a sitemap where all 40 pages changed today is a sitemap a
 * crawler learns to disregard.
 *
 * WHAT IS LEFT OUT
 * Anything carrying a noindex robots meta, redirect/duplicate canonicals,
 * the operator console, the 404 page, and /content/,
 * which holds editorial fragments that get inlined into generated articles,
 * not pages meant to stand on their own.
 *
 * Run: node scripts/build-sitemap.js
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.join(__dirname, "..");
const SITE = "https://www.myrecon.xyz";

/** Directories that never contain indexable pages. */
const EXCLUDE_DIRS = new Set(["node_modules", ".git", ".vercel", "content", "data", "scripts", "tests", "worker-console"]);

/** Individual files that are real pages but must not be indexed. */
const EXCLUDE_FILES = new Set(["404.html"]);

/**
 * Section hints are retained for compatibility. Google ignores both;
 * they are not signals that a page will rank above another page.
 */
const SECTIONS = [
  { test: (u) => u === "/", changefreq: "weekly", priority: "1.0" },
  { test: (u) => u === "/breaches/", changefreq: "daily", priority: "0.8" },
  { test: (u) => u.startsWith("/breaches/"), changefreq: "monthly", priority: "0.6" },
  { test: (u) => u === "/guides/", changefreq: "weekly", priority: "0.9" },
  { test: (u) => u.startsWith("/guides/"), changefreq: "monthly", priority: "0.8" },
  { test: (u) => u === "/blog/", changefreq: "weekly", priority: "0.9" },
  { test: (u) => u.startsWith("/blog/"), changefreq: "monthly", priority: "0.8" },
  { test: (u) => u === "/services.html" || u === "/app.html" || u === "/deep-search.html", changefreq: "monthly", priority: "0.9" },
  { test: (u) => u === "/pricing" || u === "/features" || u === "/privacy-audit" || u === "/enterprise-osint-api", changefreq: "monthly", priority: "0.9" },
  // The three explainer pages. High-intent search targets ("is X legit",
  // "X vs Y"), so they sit above About and below the tool pages. Without an
  // entry here they would fall through to the 0.3 catch-all, which is where
  // legal boilerplate lives.
  { test: (u) => u === "/is-myrecon-legit.html"
      || u === "/how-myrecon-compares.html"
      || u === "/username-sweep-vs-deep-search.html",
    changefreq: "monthly", priority: "0.8" },
  // Named head-to-head comparisons. Same intent class as the explainers.
  { test: (u) => u.startsWith("/vs/"), changefreq: "monthly", priority: "0.8" },
  { test: (u) => u === "/founder.html", changefreq: "monthly", priority: "0.7" },
  { test: (u) => u === "/about.html", changefreq: "monthly", priority: "0.6" },
  { test: (u) => u === "/contact.html", changefreq: "yearly", priority: "0.5" },
  { test: () => true, changefreq: "yearly", priority: "0.3" },
];

function walk(dir, acc = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".") || EXCLUDE_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, acc);
    else if (entry.name.endsWith(".html") && !EXCLUDE_FILES.has(entry.name)) acc.push(full);
  }
  return acc;
}

/** Prefer a page's canonical URL; this also supports clean URLs backed by .html files. */
function attribute(tag, name) {
  const match = tag.match(new RegExp(`(?:\\s|<)${name}\\s*=\\s*(?:"([^\"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
  return match ? (match[1] ?? match[2] ?? match[3]) : null;
}

function decodeHtml(value) {
  return value.replace(/&(?:amp|quot|apos|lt|gt|#\d+|#x[\da-f]+);/gi, entity => {
    const named = { '&amp;': '&', '&quot;': '"', '&apos;': "'", '&lt;': '<', '&gt;': '>' };
    if (named[entity.toLowerCase()]) return named[entity.toLowerCase()];
    const number = entity.toLowerCase().startsWith('&#x') ? parseInt(entity.slice(3, -1), 16) : parseInt(entity.slice(2, -1), 10);
    return number > 0 && number <= 0x10ffff && !(number >= 0xd800 && number <= 0xdfff) ? String.fromCodePoint(number) : entity;
  });
}

function toUrlPath(file, html, root = ROOT) {
  const tags = [...html.matchAll(/<link\b[^>]*>/gi)]
    .map(match => match[0]).filter(tag => (attribute(tag, 'rel') || '').split(/\s+/).some(token => token.toLowerCase() === 'canonical'));
  if (tags.length) {
    const urls = new Set();
    for (const tag of tags) {
      const href = attribute(tag, 'href');
      if (!href || !href.trim()) return null;
      try {
        const canonical = new URL(decodeHtml(href.trim()), SITE);
        if (![SITE, 'https://myrecon.xyz'].includes(canonical.origin) || canonical.username || canonical.password || canonical.search || canonical.hash) return null;
        urls.add(canonical.pathname || '/');
      } catch { return null; }
    }
    return urls.size === 1 ? [...urls][0] : null;
  }
  const rel = path.relative(root, file).split(path.sep).join("/");
  return "/" + (rel.endsWith("index.html") ? rel.slice(0, -"index.html".length) : rel);
}

function gitDate(file, root = ROOT) {
  try {
    const out = execFileSync("git", ["log", "-1", "--format=%cs", "--", file], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return /^\d{4}-\d{2}-\d{2}$/.test(out) ? out : "";
  } catch {
    return ""; // no git, shallow clone, or the file is untracked
  }
}

function publishingDate() {
  // Article dates and source commits use the publisher's India calendar.
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  return ['year', 'month', 'day'].map(type => parts.find(part => part.type === type).value).join('-');
}

function validDate(value, today = publishingDate()) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?$/.test(value)) return '';
  if (value.length > 10 && !Number.isFinite(new Date(value).getTime())) return '';
  const date = typeof value === 'string' ? value.slice(0, 10) : '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date > today) return '';
  const parsed = new Date(`${date}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date ? date : '';
}

function renderedChangeDates(environment = process.env, today) {
  const date = validDate(environment.MYRECON_SITEMAP_CHANGED_DATE, today);
  if (!date) return new Map();
  try {
    const files = JSON.parse(environment.MYRECON_SITEMAP_CHANGED_FILES || '[]');
    if (!Array.isArray(files)) return new Map();
    return new Map(files.filter(file => typeof file === 'string').map(file => [file, date]));
  } catch {
    return new Map();
  }
}

function lastmod(file, html, changedDates, { root = ROOT, today, gitDateFor = gitDate } = {}) {
  const relative = path.relative(root, file).split(path.sep).join('/');
  const dates = [changedDates.get(relative), gitDateFor(file, root)];
  function collect(value) {
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      if (key === 'dateModified' || key === 'datePublished') dates.push(child);
      else if (typeof child === 'object') collect(child);
    }
  }
  for (const [, attrs, content] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    if ((attribute(`<script ${attrs}>`, 'type') || '').toLowerCase() !== 'application/ld+json') continue;
    try { collect(JSON.parse(content)); } catch { /* Invalid JSON-LD is not a freshness source. */ }
  }
  return dates.map(date => validDate(date, today)).filter(Boolean).sort().at(-1) || '';
}

function fileForUrl(url, root = ROOT) {
  let decoded;
  try { decoded = decodeURIComponent(url); } catch { return null; }
  const base = path.resolve(root, `.${decoded}`);
  const relative = path.relative(root, base);
  if (relative.startsWith('..') || path.isAbsolute(relative)) return null;
  const candidates = url.endsWith('/') ? [path.join(base, 'index.html')] : [base, `${base}.html`, path.join(base, 'index.html')];
  return candidates.find(candidate => candidate.endsWith('.html') && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) || null;
}

function collectEntries({ root = ROOT, environment = process.env, today, gitDateFor = gitDate } = {}) {
  const entries = [];
  const skipped = [];
  const changedDates = renderedChangeDates(environment, today);
  const config = fs.existsSync(path.join(root, 'vercel.json')) ? JSON.parse(fs.readFileSync(path.join(root, 'vercel.json'), 'utf8')) : {};
  const redirected = new Set((config.redirects || []).filter(rule => !rule.source.includes(':') && !rule.has && !rule.missing).map(rule => rule.source));

  for (const file of walk(root)) {
    const html = fs.readFileSync(file, "utf8");
    const url = toUrlPath(file, html, root);

    if (url === null) {
      skipped.push(`${path.relative(root, file)} (invalid or external canonical)`);
      continue;
    }
    const noindex = [...html.matchAll(/<meta\b[^>]*>/gi)].some(([tag]) =>
      /^(?:robots|googlebot|bingbot|applebot)$/i.test(attribute(tag, 'name') || '') &&
      /\b(?:noindex|none)\b/i.test(attribute(tag, 'content') || ''));
    const refresh = [...html.matchAll(/<meta\b[^>]*>/gi)].some(([tag]) => /^refresh$/i.test(attribute(tag, 'http-equiv') || ''));
    if (noindex || refresh) {
      skipped.push(`${url} (noindex)`);
      continue;
    }
    // A page with no <title> is a fragment, not a document.
    if (!/<title\b[^>]*>[^<]+<\/title\s*>/i.test(html)) {
      skipped.push(`${url} (no <title>, fragment)`);
      continue;
    }

    if (redirected.has(url) || fileForUrl(url, root) !== file) {
      skipped.push(`${url} (redirect, duplicate or missing canonical target)`);
      continue;
    }

    const section = SECTIONS.find((s) => s.test(url));
    entries.push({ url, lastmod: lastmod(file, html, changedDates, { root, today, gitDateFor }), ...section });
  }

  // Homepage first, then alphabetically, deterministic output, so a rebuild
  // that changed nothing produces no diff.
  entries.sort((a, b) => (a.url === "/" ? -1 : b.url === "/" ? 1 : a.url.localeCompare(b.url)));

  const unique = [];
  const canonicalPaths = new Set();
  for (const entry of entries) {
    if (canonicalPaths.has(entry.url)) {
      skipped.push(`${entry.url} (duplicate canonical)`);
      continue;
    }
    canonicalPaths.add(entry.url);
    unique.push(entry);
  }

  return { entries: unique, skipped };
}

const xmlEscape = value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');

function renderSitemap(entries) {
  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    entries
      .map(
        (e) =>
          `  <url><loc>${xmlEscape(SITE + e.url)}</loc>${e.lastmod ? `<lastmod>${e.lastmod}</lastmod>` : ''}` +
          `<changefreq>${e.changefreq}</changefreq><priority>${e.priority}</priority></url>`,
      )
      .join("\n") +
    `\n</urlset>\n`);
}

function buildSitemap(options = {}) {
  const root = options.root || ROOT;
  const { entries, skipped } = collectEntries(options);
  const xml = renderSitemap(entries);
  // Fail before replacing the deployed artifact if protocol limits are exceeded.
  if (entries.length > 50000 || Buffer.byteLength(xml, 'utf8') > 50 * 1024 * 1024) {
    throw new Error('[sitemap] exceeds 50,000 URLs or 50MB; split into child sitemaps');
  }

  function writeIfChanged(filename, contents) {
    const target = path.join(root, filename);
    if (!fs.existsSync(target) || fs.readFileSync(target, 'utf8') !== contents) fs.writeFileSync(target, contents, 'utf8');
  }

  // .gitattributes normalises the repo to LF; writing CRLF back would show the
  // whole file as changed on every build.
  writeIfChanged('sitemap.xml', xml.replace(/\r\n/g, '\n'));

  // A stable index can accommodate additional sitemaps as the library grows.
  // Omit lastmod here: a build does not necessarily change the child sitemap.
  writeIfChanged('sitemap-index.xml',
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    `  <sitemap><loc>${SITE}/sitemap.xml</loc></sitemap>\n` +
    `</sitemapindex>\n`);

  console.log(`[sitemap] ${entries.length} URLs written`);
  if (skipped.length) console.log(`[sitemap] skipped ${skipped.length}: ${skipped.join(", ")}`);

  return { entries, skipped };
}

if (require.main === module) buildSitemap();
module.exports = { attribute, toUrlPath, validDate, lastmod, fileForUrl, collectEntries, renderSitemap, buildSitemap };

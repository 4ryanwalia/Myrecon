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
 * WHERE <lastmod> COMES FROM, in order of preference:
 *   1. The source commit date when this build changed a rendered page. This
 *      covers generated pages whose HTML is not separately committed.
 *   2. JSON-LD dateModified / datePublished on the page itself. The breach
 *      articles carry HIBP's ModifiedDate here, which is the real date the
 *      underlying record changed, better than anything the filesystem knows,
 *      since these files are regenerated on every build and their mtime is
 *      always "now".
 *   3. The last commit that touched the file. For hand-written pages this is
 *      the honest answer: it is the date the content actually changed.
 *   4. File mtime, for a file git has never seen (a fresh, uncommitted page).
 *
 * Stamping today's date on everything would be the easy version and is worse
 * than useless: a sitemap where all 40 pages changed today is a sitemap a
 * crawler learns to disregard.
 *
 * WHAT IS LEFT OUT
 * Anything carrying a noindex robots meta, the 404 page, and /content/,
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
const EXCLUDE_DIRS = new Set(["node_modules", ".git", ".vercel", "content", "data", "scripts"]);

/** Individual files that are real pages but must not be indexed. */
const EXCLUDE_FILES = new Set(["404.html"]);

/**
 * changefreq/priority by section. Google has said publicly it ignores both;
 * Bing and Yandex still read them, and they cost two attributes, so they stay.
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
function toUrlPath(file, html) {
  const canonicalTag = [...html.matchAll(/<link\b[^>]*>/gi)]
    .map((match) => match[0])
    .find((tag) => /\brel=["']canonical["']/i.test(tag));
  const canonicalHref = canonicalTag && canonicalTag.match(/\bhref=["']([^"']+)["']/i)?.[1];
  if (canonicalHref) {
    try {
      const canonical = new URL(canonicalHref, SITE);
      if (["myrecon.xyz", "www.myrecon.xyz"].includes(canonical.hostname)) {
        return canonical.pathname || "/";
      }
    } catch {
      // Fall through to the path on disk when a page has a malformed canonical.
    }
  }
  const rel = path.relative(ROOT, file).split(path.sep).join("/");
  return "/" + (rel.endsWith("index.html") ? rel.slice(0, -"index.html".length) : rel);
}

function gitDate(file) {
  try {
    const out = execFileSync("git", ["log", "-1", "--format=%cs", "--", file], {
      cwd: ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return /^\d{4}-\d{2}-\d{2}$/.test(out) ? out : "";
  } catch {
    return ""; // no git, shallow clone, or the file is untracked
  }
}

function renderedChangeDates() {
  const date = process.env.MYRECON_SITEMAP_CHANGED_DATE || '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return new Map();
  try {
    const files = JSON.parse(process.env.MYRECON_SITEMAP_CHANGED_FILES || '[]');
    if (!Array.isArray(files)) return new Map();
    return new Map(files.filter(file => typeof file === 'string').map(file => [file, date]));
  } catch {
    return new Map();
  }
}

function lastmod(file, html, changedDates) {
  const relative = path.relative(ROOT, file).split(path.sep).join('/');
  // Generated HTML can change because its tracked source changed. In that
  // case the build supplies the source commit date, which is more truthful
  // than the older Git date of the generated file.
  if (changedDates.has(relative)) return changedDates.get(relative);
  const ld = html.match(/"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})/) || html.match(/"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})/);
  if (ld) return ld[1];
  return gitDate(file) || fs.statSync(file).mtime.toISOString().slice(0, 10);
}

function main() {
  const entries = [];
  const skipped = [];
  const changedDates = renderedChangeDates();

  for (const file of walk(ROOT)) {
    const html = fs.readFileSync(file, "utf8");
    const url = toUrlPath(file, html);

    const robots = html.match(/<meta\s+name=["']robots["']\s+content=["']([^"']*)["']/i);
    if (robots && /noindex|none/i.test(robots[1])) {
      skipped.push(`${url} (noindex)`);
      continue;
    }
    // A page with no <title> is a fragment, not a document.
    if (!/<title>/i.test(html)) {
      skipped.push(`${url} (no <title>, fragment)`);
      continue;
    }

    const section = SECTIONS.find((s) => s.test(url));
    entries.push({ url, lastmod: lastmod(file, html, changedDates), ...section });
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

  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    unique
      .map(
        (e) =>
          `  <url><loc>${SITE}${e.url}</loc><lastmod>${e.lastmod}</lastmod>` +
          `<changefreq>${e.changefreq}</changefreq><priority>${e.priority}</priority></url>`,
      )
      .join("\n") +
    `\n</urlset>\n`;

  // .gitattributes normalises the repo to LF; writing CRLF back would show the
  // whole file as changed on every build.
  fs.writeFileSync(path.join(ROOT, "sitemap.xml"), xml.replace(/\r\n/g, "\n"), "utf8");

  // A stable index can accommodate additional sitemaps as the library grows.
  // Omit lastmod here: a build does not necessarily change the child sitemap.
  fs.writeFileSync(path.join(ROOT, "sitemap-index.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    `  <sitemap><loc>${SITE}/sitemap.xml</loc></sitemap>\n` +
    `</sitemapindex>\n`, "utf8");

  console.log(`[sitemap] ${unique.length} URLs written`);
  if (skipped.length) console.log(`[sitemap] skipped ${skipped.length}: ${skipped.join(", ")}`);

  // 50,000 is the per-file ceiling in the protocol. Nowhere near it, but a
  // silent breach of it would be a silently broken sitemap.
  if (entries.length > 50000) {
    console.error("[sitemap] over 50,000 URLs, this must be split into a sitemap index");
    process.exit(1);
  }
}

main();

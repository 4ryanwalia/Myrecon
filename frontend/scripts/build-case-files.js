/* Case Files, the written archive.
 *
 * WHY THIS EXISTS SEPARATELY FROM build-breaches.js
 * /breaches/ is machine-built: it tracks Have I Been Pwned, and every
 * sentence on those pages is derived from a field in the record, which is
 * what makes them trustworthy and also what makes them limited. A record can
 * say 147,900,000 accounts and "Social security numbers". It cannot say that
 * the patch had been available for two months, that the certificate on the
 * inspection appliance had been expired for ten, or that the first number the
 * company gave was not the last one.
 *
 * That is what a case file is for: the account of how a breach actually
 * happened, assembled from the public record, regulatory findings, court
 * filings, company statements and contemporaneous reporting, and written out
 * properly. It is the reporting the record cannot hold.
 *
 * SOURCE FORMAT
 * One file per case in content/case-files/<slug>.html. It opens with an HTML
 * comment containing a JSON metadata block, and everything after it is the
 * article body as plain HTML:
 *
 *   <!--
 *   { "headline": "...", "sortDate": "2017-07-29", ... }
 *   -->
 *   <p class="lead">...</p>
 *   <h2>...</h2>
 *
 * The body inherits the site's styles; no wrapper, no <head>. Everything
 * around it, head, breadcrumbs, fact table, schema, related links, is
 * assembled here, so thirty articles cannot drift apart from one another.
 *
 * Run: node scripts/build-case-files.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const SRC_DIR = path.join(ROOT, "content", "case-files");
const OUT_DIR = path.join(ROOT, "breaches", "case-files");
const DATA_DIR = path.join(ROOT, "assets", "data");
const SITE = "https://www.myrecon.xyz";
const BASE = "/breaches/case-files";

// The same Play custom listing the breach pages use (it leads with breach
// alerts), tagged so Play Console can tell case-file installs apart. Play
// shows the main listing until that custom one exists, and the app reads only
// `invite_code` from the referrer, so the UTM tags can never count as an invite.
const PLAY_ALERTS =
  "https://play.google.com/store/apps/details?id=com.Myrecon.osint&listing=breach-alerts" +
  "&referrer=utm_source%3Dmyrecon.xyz%26utm_medium%3Dcase_file%26utm_campaign%3Dbreach_alerts";

const esc = (s) =>
  String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const num = (n) => Number(n || 0).toLocaleString("en-GB");

/** Titles over ~60 characters get truncated in results; try shorter forms. */
function fitTitle(candidates) {
  const list = candidates.filter(Boolean);
  return list.find((c) => c.length <= 60) || list[list.length - 1];
}

/** Meta descriptions are cut around 158 characters. */
function fitDescription(text) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (clean.length <= 158) return clean;
  const cut = clean.slice(0, 158);
  const stop = cut.lastIndexOf(". ");
  if (stop > 90) return cut.slice(0, stop + 1).trim();
  return cut.slice(0, cut.lastIndexOf(" ")).replace(/[,;:.\s]+$/, "") + "…";
}

function prettyDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

const wordsIn = (html) => html.replace(/<[^>]*>/g, " ").split(/\s+/).filter(Boolean).length;

/**
 * Reading time at 220 words a minute.
 *
 * Printed because these run long and a reader deserves to know that before
 * they start, not because it is a ranking signal. It is not one.
 */
const readingTime = (html) => Math.max(1, Math.round(wordsIn(html) / 220));

// ── Source files ─────────────────────────────────────────────────

function readCases() {
  if (!fs.existsSync(SRC_DIR)) return [];
  return fs
    .readdirSync(SRC_DIR)
    .filter((f) => f.endsWith(".html"))
    .map((f) => {
      const slug = f.replace(/\.html$/, "");
      const raw = fs.readFileSync(path.join(SRC_DIR, f), "utf8");
      const m = raw.match(/^\s*<!--\s*(\{[\s\S]*?\})\s*-->/);
      if (!m) throw new Error(`${f}: no metadata block at the top of the file`);
      let meta;
      try {
        meta = JSON.parse(m[1]);
      } catch (err) {
        throw new Error(`${f}: metadata is not valid JSON, ${err.message}`);
      }
      const body = raw.slice(m[0].length).trim();
      if (!body) throw new Error(`${f}: metadata but no article body`);
      for (const field of ["headline", "description", "sortDate", "published"]) {
        if (!meta[field]) throw new Error(`${f}: missing "${field}"`);
      }
      return { ...meta, slug, body, url: `${SITE}${BASE}/${slug}.html` };
    })
    .sort((a, b) => String(b.sortDate).localeCompare(String(a.sortDate)));
}

// ── Page shell ───────────────────────────────────────────────────

const HEAD = (opts) => `<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${esc(opts.title)}</title>
  <meta name="description" content="${esc(opts.description)}">
  <meta name="robots" content="index, follow">
  <meta name="theme-color" content="#0a0f1a">
  <link rel="canonical" href="${esc(opts.url)}">
  <meta property="og:type" content="${opts.ogType || "website"}">
  <meta property="og:site_name" content="MyRecon">
  <meta property="og:title" content="${esc(opts.ogTitle || opts.title)}">
  <meta property="og:description" content="${esc(opts.description)}">
  <meta property="og:url" content="${esc(opts.url)}">
  <meta property="og:image" content="${SITE}/assets/img/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:type" content="image/png">
  <meta property="og:image:alt" content="MyRecon: investigate any digital footprint">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="${esc(opts.ogTitle || opts.title)}">
  <meta name="twitter:description" content="${esc(opts.description)}">
  <meta name="twitter:image" content="${SITE}/assets/img/og-image.png">
  <meta name="twitter:image:alt" content="MyRecon: investigate any digital footprint">
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg">
  <link rel="apple-touch-icon" href="/assets/img/favicon.svg">
  <link rel="manifest" href="/site.webmanifest">
  <style>/* Inlined so the first paint is already correct. Without it the
     browser paints one frame using its own default body{margin:8px}, then
     drops it when styles.css applies, a whole-page shift measured at
     0.1225 CLS, over Google's 0.1 threshold, on every page. */
  *{box-sizing:border-box;margin:0;padding:0}</style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/styles.css?v=10">
  <link rel="stylesheet" href="/assets/css/fx.css?v=7">
  <link rel="stylesheet" href="/assets/css/breaches.css?v=4">
  <meta name="google-adsense-account" content="ca-pub-6109270472398539">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6109270472398539" crossorigin="anonymous"></script>
${opts.jsonLd ? `  <script type="application/ld+json">${opts.jsonLd}</script>\n` : ""}${opts.extraLd ? `  <script type="application/ld+json">${opts.extraLd}</script>\n` : ""}${opts.faqLd ? `  <script type="application/ld+json">${opts.faqLd}</script>\n` : ""}  <link rel="alternate" type="application/rss+xml" title="MyRecon: The Breach Files" href="${SITE}/breaches/feed.xml">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav">
    <div class="container nav-inner">
      <a class="brand" href="/" aria-label="MyRecon OSINT: home"><img class="logo" src="/assets/img/logo.svg" alt="" width="32" height="32"> MyRecon <small>OSINT</small></a>
      <nav class="nav-links" id="navLinks" aria-label="Primary"><a href="/#tool">Tool</a><a href="/services.html">Services</a><a href="/breaches/">Breaches</a><a href="/guides/">Guides</a><a href="/app.html">App</a><a href="/vs/">Compare</a><a href="/pricing.html">Pricing</a><a href="/about.html">About</a></nav>
      <button class="icon-btn" id="themeToggle" type="button" aria-label="Toggle theme"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" stroke-linejoin="round"/></svg></button>
      <button class="icon-btn nav-toggle" id="navToggle" type="button" aria-label="Toggle menu"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round"/></svg></button>
    </div>
  </header>
`;

const FOOT = `
  <footer class="footer">
    <div class="container"><div class="footer-bottom">
      <span>&copy; 2026 MyRecon · myrecon.xyz</span>
      <span><a href="/breaches/case-files/" style="color:var(--text-dim)">Case Files</a> · <a href="/breaches/" style="color:var(--text-dim)">Breaches</a> · <a href="/guides/" style="color:var(--text-dim)">Guides</a> · <a href="/privacy.html" style="color:var(--text-dim)">Privacy</a> · <a href="/cookies.html">Cookies</a> · <a href="/terms.html">Terms</a> · <a href="/cookies.html#manage" data-cookie-settings>Cookie policy</a></span>
    </div></div>
  </footer>
  <script src="/assets/js/env.js?v=10"></script>
  <script src="/assets/js/config.js?v=10"></script>
  <script src="/assets/js/app.js?v=10"></script>
  <script src="/assets/js/breach-check.js?v=2"></script>
  <script src="/assets/js/consent.js?v=10"></script>
  <script src="/assets/js/fx.js?v=7" defer></script>
</body>
</html>
`;

// ── Article ──────────────────────────────────────────────────────

const factRow = (label, value) =>
  value ? `        <div class="cf-fact"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>` : "";

/**
 * Three outbound links per case file.
 *
 * Hand-picked where the metadata names them, because "what to read after
 * Equifax" is an editorial judgement. Topped up by rotating through the
 * archive from this article's own position, which gives every case file
 * roughly the same number of inbound links instead of pointing all of them
 * at whichever three sort first.
 */
function relatedFor(c, all) {
  const bySlug = new Map(all.map((x) => [x.slug, x]));
  const picked = [];
  (c.related || []).forEach((s) => {
    const hit = bySlug.get(s);
    if (hit && hit.slug !== c.slug && !picked.includes(hit)) picked.push(hit);
  });
  if (picked.length < 3) {
    const pool = all.filter((x) => x.slug !== c.slug && !picked.some((p) => p.slug === x.slug));
    const start = Math.max(0, all.findIndex((x) => x.slug === c.slug));
    for (let i = 0; picked.length < 3 && i < pool.length; i += 1) {
      picked.push(pool[(start + i) % pool.length]);
    }
  }
  return picked.slice(0, 3);
}

function article(c, all) {
  const related = relatedFor(c, all);
  const mins = readingTime(c.body);

  const crumbs = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "MyRecon", item: SITE },
      { "@type": "ListItem", position: 2, name: "The Breach Files", item: `${SITE}/breaches/` },
      { "@type": "ListItem", position: 3, name: "Case Files", item: `${SITE}${BASE}/` },
      { "@type": "ListItem", position: 4, name: c.subject || c.headline, item: c.url },
    ],
  });

  const jsonLd = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Article",
    headline: c.headline,
    description: c.description,
    datePublished: c.published,
    dateModified: c.updated || c.published,
    author: { "@type": "Organization", name: "MyRecon" },
    publisher: { "@type": "Organization", name: "MyRecon" },
    mainEntityOfPage: c.url,
    articleSection: "Case Files",
    ...(c.subject ? { about: { "@type": "Thing", name: c.subject } } : {}),
    wordCount: wordsIn(c.body),
  });

  const faqLd = (c.faq || []).length
    ? JSON.stringify({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: c.faq.map((f) => ({
          "@type": "Question",
          name: f.q,
          acceptedAnswer: { "@type": "Answer", text: f.a.replace(/<[^>]*>/g, "") },
        })),
      })
    : "";

  const facts = [
    factRow("People affected", c.records),
    factRow("When it happened", c.occurred),
    factRow("Made public", c.disclosed),
    factRow("How they got in", c.vector),
    factRow("Attributed to", c.actor),
    factRow("What it cost", c.cost),
  ]
    .filter(Boolean)
    .join("\n");

  return (
    HEAD({
      title: fitTitle([
        c.seoTitle ? `${c.seoTitle} | MyRecon` : "",
        c.seoTitle,
        `${c.headline} | MyRecon`,
        c.headline,
      ]),
      description: fitDescription(c.description),
      url: c.url,
      ogType: "article",
      ogTitle: c.seoTitle || c.headline,
      jsonLd,
      extraLd: crumbs,
      faqLd,
    }) +
      `  <main id="main" class="container">
    <article class="article breach-article cf-article">
      <p class="bx-crumb"><a href="${BASE}/">← Case Files</a> · <a href="/breaches/">The Breach Files</a></p>

      <header class="bx-head">
        <div>
          <span class="kicker">${esc(c.kicker || "Case file")}</span>
          <h1>${esc(c.headline)}</h1>
          <p class="meta">Case file · ${mins} min read · ${c.updated && c.updated !== c.published ? `Updated ${esc(prettyDate(c.updated))}` : `Published ${esc(prettyDate(c.published))}`}</p>
        </div>
      </header>

${facts ? `      <dl class="cf-facts">\n${facts}\n      </dl>\n` : ""}${c.exposed && c.exposed.length ? `      <p class="cf-exposed"><b>What was exposed:</b> ${esc(c.exposed.join(" · "))}</p>\n` : ""}
${c.body}

      <!-- After the reporting, not before it. Somebody who has just read how a
           breach unfolded is far likelier to want the check than someone who
           landed here and was asked for an address in the first screen. -->
      <form class="bx-check" data-breach-check>
        <label for="cfEmail">Check whether your own address is in a known breach</label>
        <div class="bx-check-row">
          <input id="cfEmail" type="email" name="email" inputmode="email" autocomplete="email"
                 placeholder="you@example.com" required aria-describedby="cfEmailNote">
          <button class="btn btn-sm" type="submit">Check my address</button>
        </div>
        <p class="bx-check-note" id="cfEmailNote">Checked against every breach on record, against public breach data only. Your address is not sent to us as a form and is not stored, it is handed straight to the lookup tool in your own browser. See the <a href="/privacy.html#forms">privacy policy</a>.</p>
      </form>

${(c.faq || []).length ? `      <h2>Questions people ask</h2>
      <div class="bx-faq">
${c.faq.map((f) => `        <h3>${esc(f.q)}</h3>\n        <p>${f.a}</p>`).join("\n\n")}
      </div>\n` : ""}
      <!-- After the questions, before the sources. A case file explains a
           breach that is over; the one thing it cannot do is tell the reader
           about the next one. The note keeps the app's two alerts apart: only
           the per-address one sends anything. -->
      <aside class="bx-offer">
        <h3>Hear about the next breach</h3>
        <p>MyRecon for Android checks once a day for newly published breaches and tells you who was hit and how many accounts were exposed. The comparison runs on your phone: nothing is sent to do it, and there is no account to make.</p>
        <p class="bx-offer-note">A separate switch can watch your own address as well. That check has to send the address to a breach lookup service, and the app says so before you turn it on.</p>
        <p><a class="btn btn-sm" href="${esc(PLAY_ALERTS)}" target="_blank" rel="noopener">Get breach alerts on Google Play →</a></p>
      </aside>

${(c.sources || []).length ? `      <h2>Sources</h2>
      <ul class="cf-sources">
${c.sources.map((s) => `        <li>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener nofollow">${esc(s.label)}</a>` : `<b>${esc(s.label)}</b>`}${s.note ? `, ${esc(s.note)}` : ""}</li>`).join("\n")}
      </ul>\n` : ""}${related.length ? `      <h2>Read next</h2>
      <ul class="bx-related">
${related.map((r) => `        <li><a href="${BASE}/${r.slug}.html">${esc(r.headline)}</a></li>`).join("\n")}
      </ul>\n` : ""}
      <p class="bx-method">Case files are written from the public record: regulatory findings, court filings, company disclosures and contemporaneous reporting, cited above. Figures are the ones the organisation or its regulator finally settled on, which is often not the number first reported, where that differs, the page says so. Disputed accounts are marked as disputed rather than resolved in either direction.</p>

      <p style="margin-top:28px"><a class="btn btn-ghost" href="${BASE}/">← All case files</a> <a class="btn btn-ghost" href="/breaches/">Breach archive →</a></p>
    </article>
  </main>` +
      FOOT
  );
}

// ── Index ────────────────────────────────────────────────────────

/** Era buckets, newest first. A flat list of thirty long articles is a wall. */
const ERAS = [
  {
    from: 2024,
    to: 2100,
    name: "2024 onwards",
    blurb:
      "The third-party era. The intrusion is rarely at the company whose name ends up in the headline, it is at a supplier, a cloud tenant, or on an employee's home computer.",
  },
  {
    from: 2019,
    to: 2023,
    name: "2019 – 2023",
    blurb:
      "Cloud misconfiguration, ransomware crews with a publicity operation, and the first breaches measured in whole national populations.",
  },
  {
    from: 2014,
    to: 2018,
    name: "2014 – 2018",
    blurb:
      "The years that produced the regulation. Mega-breaches that ended careers, moved share prices and wrote the rules everyone now works under.",
  },
  {
    from: 1990,
    to: 2013,
    name: "Before 2014",
    blurb:
      "The foundational cases. Almost everything the industry believes about passwords, card data and disclosure was learned here, expensively.",
  },
];

function index(all) {
  const url = `${SITE}${BASE}/`;
  const description =
    "In-depth case files on the data breaches that mattered: how the attackers actually got in, what was taken, what it cost, and what changed afterwards.";

  const buckets = ERAS.map((era) => ({
    ...era,
    items: all.filter((c) => {
      const y = Number(String(c.sortDate).slice(0, 4));
      return y >= era.from && y <= era.to;
    }),
  })).filter((b) => b.items.length);

  // Deliberately NOT a sum of the affected populations. Adding them produces a
  // number larger than the world, because the same people appear in breach
  // after breach, and these pages spend their time telling readers to
  // distrust exactly that kind of headline figure.
  const sourceCount = all.reduce((s, c) => s + (c.sources || []).length, 0);
  const earliest = Math.min(...all.map((c) => Number(String(c.sortDate).slice(0, 4))));

  const card = (c) => `          <a class="guide-card cf-card" href="${BASE}/${c.slug}.html">
            <span class="cf-card-kicker">${esc(c.kicker || "Case file")}</span>
            <h3>${esc(c.headline)}</h3>
            <p>${esc(c.cardBlurb || c.description)}</p>
${c.records ? `            <span class="cf-card-count">${esc(c.records)}</span>\n` : ""}            <span class="read">Read the case file →</span>
          </a>`;

  const itemList = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "MyRecon Case Files",
    itemListElement: all.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.headline,
      url: c.url,
    })),
  });

  return (
    HEAD({
      title: fitTitle([
        "Data Breach Case Files: How They Actually Happened",
        "Data Breach Case Files | MyRecon",
      ]),
      description,
      url,
      jsonLd: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: "Case Files",
        description,
        url,
      }),
      extraLd: itemList,
    }) +
      `  <main id="main" class="section">
    <div class="container bx-page">
      <p class="bx-crumb"><a href="/breaches/">← The Breach Files</a></p>
      <span class="kicker">Case Files</span>
      <h1 class="bx-title">How the breaches that mattered actually happened</h1>
      <p class="sub">The archive tells you what was taken. These tell you how, the unpatched server, the contractor's password, the API nobody put a login on, and what happened to the people in the file afterwards. Written from regulatory findings, court records and company disclosures, and sourced at the foot of every page.</p>

      <div class="bx-summary">
        <div class="bx-stat"><b>${all.length}</b><span>Case files</span></div>
        <div class="bx-stat"><b>${new Date().getUTCFullYear() - earliest}</b><span>Years covered</span></div>
${sourceCount ? `        <div class="bx-stat"><b>${num(sourceCount)}</b><span>Sources cited</span></div>\n` : ""}
      </div>

${buckets
  .map(
    (b) => `      <section class="cf-era">
        <h2 class="bx-h2">${esc(b.name)}</h2>
        <p class="cf-era-blurb">${esc(b.blurb)}</p>
        <div class="guide-grid">
${b.items.map(card).join("\n")}
        </div>
      </section>`,
  )
  .join("\n\n")}

      <p class="bx-method">Every case file is sourced. Where a headline figure was later revised, and it usually is, these pages use the number the organisation or its regulator finally settled on, and say what it was first reported as. Claims that remain disputed are labelled as disputed.</p>

      <p style="margin-top:28px"><a class="btn btn-ghost" href="/breaches/">The live breach archive →</a> <a class="btn btn-ghost" href="/guides/">Guides →</a></p>
    </div>
  </main>` +
      FOOT
  );
}

// ── App feed ─────────────────────────────────────────────────────

/**
 * assets/data/case-files.json, what the Android app reads.
 *
 * Deliberately the metadata and not the body. The article bodies run to
 * forty-odd thousand words and rendering long-form HTML inside a Compose
 * screen would be a worse read than the page it came from, so the app shows
 * the facts, who, when, how they got in, what it cost, what was exposed,
 * and opens the site for the reporting itself. That is the same bargain
 * /assets/data/breaches.json already strikes for the archive: enough to be
 * genuinely useful offline of the browser, with the full piece one tap away.
 *
 * Every field here already exists in the source file's metadata block, so the
 * feed cannot disagree with the page. Nothing is computed twice except the
 * reading time, which is derived from the body the app is not being sent.
 */
function feed(all) {
  return JSON.stringify(
    {
      generated: new Date().toISOString(),
      // Named so the app can show attribution without hardcoding it.
      source: "MyRecon Case Files",
      index: `${SITE}${BASE}/`,
      count: all.length,
      words: all.reduce((s, c) => s + wordsIn(c.body), 0),
      cases: all.map((c) => ({
        slug: c.slug,
        url: c.url,
        headline: c.headline,
        kicker: c.kicker || "Case file",
        subject: c.subject || null,
        // The card blurb is written to stand alone in a list; the description
        // is written for a search result. The app is a list, so blurb first.
        blurb: c.cardBlurb || c.description,
        description: c.description,
        records: c.records || null,
        people_count: c.peopleCount || 0,
        occurred: c.occurred || null,
        disclosed: c.disclosed || null,
        vector: c.vector || null,
        actor: c.actor || null,
        cost: c.cost || null,
        exposed: c.exposed || [],
        sort_date: c.sortDate,
        published: c.published,
        updated: c.updated || c.published,
        reading_minutes: readingTime(c.body),
        word_count: wordsIn(c.body),
        sources: (c.sources || []).length,
      })),
    },
    null,
    2,
  );
}

// ── Build ────────────────────────────────────────────────────────

function main() {
  const all = readCases();
  if (!all.length) {
    console.log("[case-files] nothing in content/case-files, skipping");
    return;
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });

  // Drop pages whose source file has gone, so a deleted case file cannot
  // linger as an orphan that the sitemap keeps advertising.
  const expected = new Set([...all.map((c) => `${c.slug}.html`), "index.html"]);
  for (const f of fs.readdirSync(OUT_DIR)) {
    if (f.endsWith(".html") && !expected.has(f)) fs.unlinkSync(path.join(OUT_DIR, f));
  }

  all.forEach((c) => {
    fs.writeFileSync(path.join(OUT_DIR, `${c.slug}.html`), article(c, all), "utf8");
  });
  fs.writeFileSync(path.join(OUT_DIR, "index.html"), index(all), "utf8");

  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(path.join(DATA_DIR, "case-files.json"), feed(all), "utf8");

  console.log(
    `[case-files] ${all.length} case files written, ${num(all.reduce((s, c) => s + wordsIn(c.body), 0))} words, feed written`,
  );
}

main();

/*
 * Render the published records in docs/nextjs-seo-kit as static pages for the
 * existing MyRecon frontend. The React/Next.js output remains a separate kit;
 * this renderer keeps production on the site's current static Vercel stack.
 */
const fs = require("fs");
const path = require("path");

const FRONTEND = path.resolve(__dirname, "..");
const REPO_CONTENT = path.resolve(FRONTEND, "..", "docs", "nextjs-seo-kit", "data", "content");
const BUNDLED_CONTENT = path.join(FRONTEND, "content", "seo-pages");
const MANIFEST = path.join(FRONTEND, ".seo-pages-manifest.json");
const GUIDE_IMAGES = path.join(FRONTEND, "assets", "img", "guides");
const SITE = "https://www.myrecon.xyz";
const CLUSTERS = { target: "find", comparison: "vs", guide: "guides", deletion: "privacy" };
const LABELS = { target: "Platform lookups", comparison: "Comparisons", guide: "Guides", deletion: "Privacy guides" };
const PRESERVED = new Map([
  ["/", "index.html"],
  ["/pricing", "pricing.html"],
  ["/vs/maigret", "vs/maigret.html"],
  ["/vs/sherlock", "vs/sherlock.html"],
  ["/vs/whatsmyname", "vs/whatsmyname.html"],
]);

function fail(message) { throw new Error(message); }
function cleanHtml(value) { return value.replace(/[ \t]+$/gm, ""); }
function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function safeJson(value) { return JSON.stringify(value).replace(/</g, "\\u003c"); }
function guideImagePath(record) { return `/assets/img/guides/${record.slug}.svg`; }
function guideMobileImagePath(record) { return `/assets/img/guides/${record.slug}-mobile.svg`; }
function guideTheme(record) {
  const slug = record.slug.toLowerCase();
  const platformPrivacy = {
    "steam-profile-privacy-checklist": ["Steam settings", "Signed-out view", "Recheck exposure"],
    "github-public-profile-privacy-checklist": ["Profile fields", "Public activity", "Email privacy"],
    "discord-profile-privacy-settings": ["Profile preview", "Server context", "Privacy controls"],
    "reddit-profile-visibility-guide": ["Public posts", "Profile settings", "Old content"],
    "youtube-subscriptions-privacy-audit": ["Subscriptions", "Playlist settings", "Public preview"],
    "pinterest-private-profile-guide": ["Board visibility", "Profile preview", "Search footprint"],
    "x-public-post-privacy-audit": ["Audience controls", "Older posts", "Public preview"],
    "linkedin-public-profile-visibility-check": ["Profile settings", "Public preview", "Search visibility"],
  };
  if (platformPrivacy[slug]) return { color: "#a8cfaa", steps: platformPrivacy[slug] };
  const themes = [
    { match: /image/, color: "#84c5d3", steps: ["Reference image", "Reverse search", "Original source"] },
    { match: /impersonation|brand/, color: "#e4ae80", steps: ["Official account", "Lookalike signal", "Report with evidence"] },
    { match: /breach|exposure|email|phone/, color: "#e3b582", steps: ["Known identifier", "Public signal", "Risk review"] },
    { match: /evidence|document|chain|notes/, color: "#c1acd9", steps: ["Source URL", "Date and context", "Supported finding"] },
    { match: /privacy|footprint|family|protect|reuse/, color: "#a8cfaa", steps: ["Public accounts", "Visibility check", "Action list"] },
    { match: /profile|account|social|username|creator|alias|identity|entity/, color: "#91b9dc", steps: ["Known identifier", "Official profile", "Verified context"] },
  ];
  return themes.find((item) => item.match.test(slug)) ||
    { color: "#a7b6d2", steps: ["Narrow question", "Public sources", "Documented result"] };
}
function guideDiagram(record) {
  const theme = guideTheme(record);
  const words = record.h1.split(/\s+/);
  const titleLines = [""];
  for (const word of words) {
    const last = titleLines.length - 1;
    if (titleLines[last] && `${titleLines[last]} ${word}`.length > 38 && titleLines.length < 2) titleLines.push(word);
    else titleLines[last] += `${titleLines[last] ? " " : ""}${word}`;
  }
  const cards = theme.steps.map((step, index) => {
    const x = 54 + index * 374;
    return `<g><rect x="${x}" y="250" width="342" height="151" rx="12" fill="#151c2a" stroke="#394457" stroke-width="2"/><text x="${x + 23}" y="298" fill="${theme.color}" font-size="30" font-weight="700">0${index + 1}</text><text x="${x + 23}" y="354" fill="#f3f6fb" font-size="25" font-weight="600">${esc(step)}</text></g>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="450" viewBox="0 0 1200 450" role="img" aria-labelledby="title desc">
<title id="title">${esc(record.h1)}: visual workflow</title><desc id="desc">${theme.steps.map(esc).join("; ")}</desc>
<rect width="1200" height="450" fill="#0d1320"/><rect x="1" y="1" width="1198" height="448" rx="16" fill="none" stroke="#394457" stroke-width="2"/>
<rect x="54" y="50" width="8" height="128" rx="4" fill="${theme.color}"/>
<text x="84" y="85" fill="${theme.color}" font-size="18" font-weight="700" letter-spacing="3">MYRECON GUIDE</text>
${titleLines.map((line, index) => `<text x="84" y="${132 + index * 48}" fill="#f3f6fb" font-size="38" font-weight="700">${esc(line)}</text>`).join("")}
<path d="M396 326h42m332 0h42" stroke="${theme.color}" stroke-width="4" stroke-linecap="round"/>
${cards}
<text x="54" y="430" fill="#a8b3c7" font-size="17">Use public sources · Verify each lead · Record uncertainty</text>
</svg>\n`;
}
function guideMobileDiagram(record) {
  const theme = guideTheme(record);
  const titleWords = record.h1.split(/\s+/);
  const lines = [""];
  for (const word of titleWords) {
    const last = lines.length - 1;
    if (lines[last] && `${lines[last]} ${word}`.length > 27 && lines.length < 3) lines.push(word);
    else lines[last] += `${lines[last] ? " " : ""}${word}`;
  }
  const cards = theme.steps.map((step, index) => {
    const y = 280 + index * 162;
    return `<g><rect x="38" y="${y}" width="564" height="134" rx="12" fill="#151c2a" stroke="#394457" stroke-width="2"/><text x="65" y="${y + 55}" fill="${theme.color}" font-size="31" font-weight="700">0${index + 1}</text><text x="65" y="${y + 103}" fill="#f3f6fb" font-size="30" font-weight="600">${esc(step)}</text></g>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="850" viewBox="0 0 640 850" role="img" aria-labelledby="title desc">
<title id="title">${esc(record.h1)}: visual workflow</title><desc id="desc">${theme.steps.map(esc).join("; ")}</desc>
<rect width="640" height="850" fill="#0d1320"/><rect x="1" y="1" width="638" height="848" rx="16" fill="none" stroke="#394457" stroke-width="2"/>
<rect x="38" y="46" width="8" height="167" rx="4" fill="${theme.color}"/>
<text x="68" y="80" fill="${theme.color}" font-size="19" font-weight="700" letter-spacing="3">MYRECON GUIDE</text>
${lines.map((line, index) => `<text x="68" y="${130 + index * 44}" fill="#f3f6fb" font-size="34" font-weight="700">${esc(line)}</text>`).join("")}
<path d="M320 414v28m0 134v28" stroke="${theme.color}" stroke-width="4" stroke-linecap="round"/>
${cards}
<text x="38" y="814" fill="#a8b3c7" font-size="17">Public sources · Verify leads · Record uncertainty</text>
</svg>\n`;
}
function writeGuideDiagram(record) {
  if (record.kind !== "guide") return;
  if (!/^[a-z0-9-]+$/.test(record.slug)) fail(`Unsafe guide image slug: ${record.slug}`);
  fs.mkdirSync(GUIDE_IMAGES, { recursive: true });
  fs.writeFileSync(path.join(GUIDE_IMAGES, `${record.slug}.svg`), guideDiagram(record), "utf8");
  fs.writeFileSync(path.join(GUIDE_IMAGES, `${record.slug}-mobile.svg`), guideMobileDiagram(record), "utf8");
}
function routeFor(record) {
  if (record.kind === "core") return record.slug === "home" ? "/" : `/${record.slug}`;
  return `/${CLUSTERS[record.kind]}/${record.slug}`;
}
function fileFor(record) {
  const route = routeFor(record);
  if (route === "/") return path.join(FRONTEND, "index.html");
  return path.join(FRONTEND, `${route.slice(1)}.html`);
}
function syncBundledContent() {
  if (!fs.existsSync(REPO_CONTENT)) return BUNDLED_CONTENT;
  fs.mkdirSync(BUNDLED_CONTENT, { recursive: true });
  const expected = new Set();
  for (const folder of fs.readdirSync(REPO_CONTENT, { withFileTypes: true })) {
    if (!folder.isDirectory()) continue;
    const sourceDir = path.join(REPO_CONTENT, folder.name);
    const targetDir = path.join(BUNDLED_CONTENT, folder.name);
    fs.mkdirSync(targetDir, { recursive: true });
    for (const name of fs.readdirSync(sourceDir).filter((file) => file.endsWith(".json"))) {
      const relative = `${folder.name}/${name}`;
      expected.add(relative);
      fs.copyFileSync(path.join(sourceDir, name), path.join(targetDir, name));
    }
  }
  for (const folder of fs.readdirSync(BUNDLED_CONTENT, { withFileTypes: true })) {
    if (!folder.isDirectory()) continue;
    const dir = path.join(BUNDLED_CONTENT, folder.name);
    for (const name of fs.readdirSync(dir).filter((file) => file.endsWith(".json"))) {
      const relative = `${folder.name}/${name}`;
      if (!expected.has(relative)) fs.unlinkSync(path.join(dir, name));
    }
  }
  return REPO_CONTENT;
}
function allRecords(contentRoot) {
  const records = [];
  for (const folder of fs.readdirSync(contentRoot, { withFileTypes: true })) {
    if (!folder.isDirectory()) continue;
    const dir = path.join(contentRoot, folder.name);
    for (const name of fs.readdirSync(dir).filter((file) => file.endsWith(".json"))) {
      const record = JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
      if (record.status === "redirected") {
        if (typeof record.redirect_to !== "string" || !record.redirect_to.startsWith("/")) {
          fail(`${name}: redirected records need a local redirect_to path`);
        }
        continue;
      }
      if (record.status !== "published") fail(`${name}: only published records can be rendered`);
      if (!record.title || record.title.length > 60) fail(`${name}: title must be 1–60 characters`);
      if (!record.description || record.description.length > 160) fail(`${name}: description must be 1–160 characters`);
      if (!Array.isArray(record.faq) || record.faq.length < 3 || record.faq.length > 5) fail(`${name}: expected 3–5 visible FAQs`);
      if (!record.sections?.length) fail(`${name}: at least one content section is required`);
      records.push(record);
    }
  }
  records.sort((a, b) => routeFor(a).localeCompare(routeFor(b)));
  const routes = new Set();
  for (const record of records) {
    const route = routeFor(record);
    if (routes.has(route)) fail(`Duplicate published route: ${route}`);
    routes.add(route);
  }
  if (records.length < 200) fail(`Expected 200+ published records; found ${records.length}`);
  return records;
}
function faqSchema(record) {
  return {
    "@context": "https://schema.org", "@type": "FAQPage",
    mainEntity: record.faq.map((item) => ({
      "@type": "Question", name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
}
function jsonLd(record, route) {
  const url = `${SITE}${route}`;
  const type = record.kind === "core" ? "WebPage" : "Article";
  const graph = [
    {
      "@context": "https://schema.org", "@type": type, name: record.h1,
      headline: record.title, description: record.description, url,
      dateModified: record.modified_at, inLanguage: "en",
      author: { "@type": "Organization", name: "MyRecon" },
      publisher: { "@id": `${SITE}/#organization` }, mainEntityOfPage: url,
    },
    {
      "@context": "https://schema.org", "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MyRecon", item: `${SITE}/` },
        { "@type": "ListItem", position: 2, name: LABELS[record.kind] || "MyRecon", item: record.kind === "core" ? `${SITE}/` : `${SITE}/${CLUSTERS[record.kind]}/` },
        { "@type": "ListItem", position: 3, name: record.h1, item: url },
      ],
    },
    faqSchema(record),
  ];
  return graph.map((item) => `  <script type="application/ld+json">${safeJson(item)}</script>`).join("\n");
}
function renderSections(record) {
  return record.sections.map((section, index) => `
    <section class="seo-section" id="section-${index + 1}">
      <h2>${esc(section.heading)}</h2>
      <p>${esc(section.body)}</p>
    </section>`).join("");
}
function renderSpecific(record) {
  if (record.kind === "target") {
    return `
    <section class="seo-section"><h2>Check it manually</h2><ol>${record.manual_steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol>
      <p>${esc(record.platform.limitations)}</p></section>
    <section class="seo-section"><h2>Privacy and result limits</h2><p>${esc(record.platform.privacy_overview)}</p>
      <p>${esc(record.platform.false_positive_note)}</p></section>`;
  }
  if (record.kind === "deletion") {
    return `
    <section class="seo-section"><h2>Official instructions</h2><p><a href="${esc(record.official_help_url)}" target="_blank" rel="noopener noreferrer">Open ${esc(record.service)}'s official help page</a></p>
      ${record.optout_link ? `<p><a href="${esc(record.optout_link)}" target="_blank" rel="noopener noreferrer">Open the official opt-out form</a></p>` : ""}
      <ol>${record.steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol>
      <p>${esc(record.caveat)}</p></section>
    <section class="seo-section"><h2>Review your remaining public footprint</h2><p>${esc(record.audit_pitch)}</p></section>`;
  }
  if (record.kind === "guide") {
    return `
    <section class="seo-section"><h2>Key takeaways</h2><ul>${record.takeaways.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></section>`;
  }
  if (record.kind === "comparison") {
    const rows = record.capabilities.map((item) => `<tr><th scope="row">${esc(item.name)}</th><td>${esc(item.myrecon)}</td><td>${esc(item.competitor)}</td></tr>`).join("");
    return `
    <section class="seo-section"><h2>Compare the workflows</h2>
      <div class="seo-table-wrap"><table><thead><tr><th>Task</th><th>MyRecon</th><th>${esc(record.competitor.name)}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p>${record.benchmark ? esc(record.benchmark.summary || "Compare results under the same documented conditions.") : "No directly comparable benchmark is published for this page."}</p>
      <h3>MyRecon may suit you when</h3><ul>${record.pros.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
      <h3>Consider the trade-offs</h3><ul>${record.cons.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
      <p>${esc(record.migration_note)}</p>
      <p>Competitor details: <a href="${esc(record.competitor.official_url)}" target="_blank" rel="noopener noreferrer">${esc(record.competitor.name)} official source</a></p>
    </section>`;
  }
  if (record.kind === "core") {
    return `<section class="seo-section"><h2>Product details</h2><ul>${record.product_claims.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></section>`;
  }
  return "";
}
function renderPage(record) {
  const route = routeFor(record);
  const label = LABELS[record.kind] || "MyRecon";
  const categoryRoute = CLUSTERS[record.kind] ? `/${CLUSTERS[record.kind]}/` : "/";
  const sourceList = [...new Set([...(record.sources || []), record.official_help_url, record.optout_link].filter(Boolean))];
  return `<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${esc(record.title)}</title><meta name="description" content="${esc(record.description)}">
  <meta name="robots" content="index, follow"><meta name="theme-color" content="#f7f7f4">
  <link rel="canonical" href="${SITE}${route}">
  <meta property="og:type" content="article"><meta property="og:site_name" content="MyRecon">
  <meta property="og:title" content="${esc(record.title)}"><meta property="og:description" content="${esc(record.description)}">
  <meta property="og:url" content="${SITE}${route}"><meta property="og:image" content="${SITE}/assets/img/og-image.png">
  <meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="${esc(record.title)}">
  <meta name="twitter:description" content="${esc(record.description)}"><meta name="twitter:image" content="${SITE}/assets/img/og-image.png">
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg"><link rel="manifest" href="/site.webmanifest">
  <link rel="stylesheet" href="/assets/css/styles.css?v=12"><link rel="stylesheet" href="/assets/css/fx.css?v=7">
${jsonLd(record, route)}
  <style>
    .seo-page{max-width:900px;padding-top:42px;padding-bottom:56px}.seo-breadcrumb{font-size:.9rem;margin-bottom:18px;color:var(--text-dim)}
    .seo-page h1{line-height:1.14;margin:0 0 16px}.seo-page .seo-intro{font-size:1.1rem;line-height:1.7;max-width:72ch}
    .seo-section{margin:34px 0}.seo-section h2{margin:0 0 12px}.seo-section p,.seo-section li{line-height:1.75}.seo-section li{margin:8px 0}
    .seo-cta{margin:32px 0;padding:24px;border:1px solid var(--border,#394252);border-radius:14px;background:var(--surface,#101722)}
    .seo-cta h2{margin:0 0 8px}.seo-faq{margin-top:42px}.seo-faq details{padding:14px 0;border-bottom:1px solid var(--border,#394252)}
    .seo-faq summary{font-weight:700;cursor:pointer}.seo-faq details p{margin-top:10px;line-height:1.7}.seo-sources{font-size:.92rem}
    .seo-table-wrap{overflow-x:auto}.seo-table-wrap table{width:100%;border-collapse:collapse}.seo-table-wrap th,.seo-table-wrap td{padding:10px;border:1px solid var(--border,#394252);text-align:left;vertical-align:top}
    .seo-link-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.seo-link-grid a{display:block;padding:14px;border:1px solid var(--border,#394252);border-radius:10px}
    .seo-library-link{margin-top:32px}.seo-library-link a{margin-right:12px}${record.kind === "guide" ? `
    .seo-guide-figure{margin:28px 0 34px}.seo-guide-figure img{display:block;width:100%;height:auto;border-radius:12px}.seo-guide-figure figcaption{margin-top:9px;color:var(--text-dim);font-size:.88rem;line-height:1.5}` : ""}
  </style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav"><div class="container nav-inner">
    <a class="brand" href="/" aria-label="MyRecon OSINT: home"><img class="logo" src="/assets/img/logo.svg" alt="" width="32" height="32"> MyRecon <small>OSINT</small></a>
    <nav class="nav-links" aria-label="Primary"><a href="/#tool">Tool</a><a href="/guides/">Guides</a><a href="/find/">Find profiles</a><a href="/privacy/">Privacy</a><a href="/vs/">Compare</a><a href="/pricing.html">Pricing</a></nav>
  </div></header>
  <main id="main" class="container prose seo-page">
    <nav class="seo-breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <a href="${categoryRoute}">${esc(label)}</a></nav>
    <article><span class="kicker">${esc(label)}</span><h1>${esc(record.h1)}</h1><p class="seo-intro">${esc(record.intro)}</p>${record.kind === "guide" ? `
      <figure class="seo-guide-figure"><picture><source media="(max-width: 640px)" srcset="${guideMobileImagePath(record)}" width="640" height="850"><img src="${guideImagePath(record)}" alt="${esc(`${record.h1}: ${guideTheme(record).steps.join(', then ')}.`)}" width="1200" height="450" decoding="async"></picture><figcaption>A practical overview of the public-source review described below.</figcaption></figure>` : ""}
      ${renderSpecific(record)}${renderSections(record)}
      <section class="seo-cta"><h2>Check a public username</h2><p>Use accounts and identifiers you own or are authorized to review. A matching username is a lead, not proof of identity.</p>
        <username-search-input></username-search-input></section>
      <section class="seo-faq"><h2>Frequently asked questions</h2>${record.faq.map((item) => `<details><summary>${esc(item.question)}</summary><p>${esc(item.answer)}</p></details>`).join("")}</section>
      <nav class="seo-library-link" aria-label="Related libraries"><a href="/find/">Platform lookups</a><a href="/guides/">OSINT guides</a><a href="/privacy/">Privacy guides</a><a href="/vs/">Tool comparisons</a></nav>
      ${sourceList.length ? `<section class="seo-section seo-sources"><h2>Sources</h2><ul>${sourceList.map((source) => `<li><a href="${esc(source)}" target="_blank" rel="noopener noreferrer">${esc(source)}</a></li>`).join("")}</ul></section>` : ""}
    </article>
  </main>
  <footer class="footer"><div class="container"><div class="footer-bottom"><span>&copy; 2026 MyRecon</span><span><a href="/privacy.html">Privacy policy</a> · <a href="/terms.html">Terms</a> · <a href="/contact.html">Contact</a></span></div></div></footer>
  <script src="/assets/js/username-search-input.js" defer></script>
</body></html>
`;
}
function renderHub(kind, records) {
  const section = CLUSTERS[kind];
  const title = ({ target: "Username Search by Platform | MyRecon", comparison: "OSINT Tool Comparisons | MyRecon", guide: "OSINT & Digital Footprint Guides | MyRecon", deletion: "Account Deletion & Online Privacy Guides | MyRecon" })[kind];
  const description = `Browse ${records.length} ${LABELS[kind].toLowerCase()} from MyRecon. Review public information, official sources, and the limits of each workflow.`;
  const route = `/${section}/`;
  const list = records.map((record) => `      <a href="${esc(routeFor(record))}"><strong>${esc(record.h1)}</strong><br><span>${esc(record.description)}</span></a>`).join("\n");
  const pageRecord = { title, h1: title, description, intro: `Browse the MyRecon ${LABELS[kind].toLowerCase()} library. Each page explains a specific task, its evidence limits, and appropriate public-source steps.`, kind, modified_at: new Date().toISOString().slice(0, 10), faq: [] };
  const hubSchema = safeJson({ "@context": "https://schema.org", "@type": "CollectionPage", name: title, description, url: `${SITE}${route}`, mainEntity: { "@type": "ItemList", itemListElement: records.map((record, index) => ({ "@type": "ListItem", position: index + 1, name: record.h1, url: `${SITE}${routeFor(record)}` })) } });
  return `<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title><meta name="description" content="${esc(description)}"><meta name="robots" content="index, follow"><meta name="theme-color" content="#f7f7f4"><link rel="canonical" href="${SITE}${route}"><link rel="stylesheet" href="/assets/css/styles.css?v=12"><link rel="stylesheet" href="/assets/css/fx.css?v=7"><script type="application/ld+json">${hubSchema}</script><style>.seo-page{max-width:1100px;padding:42px 0 56px}.seo-link-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.seo-link-grid a{display:block;padding:14px;border:1px solid var(--border,#394252);border-radius:10px}.seo-link-grid span{font-size:.92rem;color:var(--text-dim)}</style></head><body><a class="skip-link" href="#main">Skip to content</a><header class="nav"><div class="container nav-inner"><a class="brand" href="/">MyRecon <small>OSINT</small></a><nav class="nav-links" aria-label="Primary"><a href="/#tool">Tool</a><a href="/guides/">Guides</a><a href="/find/">Find profiles</a><a href="/privacy/">Privacy</a><a href="/vs/">Compare</a><a href="/pricing.html">Pricing</a></nav></div></header><main id="main" class="container prose seo-page"><span class="kicker">MyRecon library</span><h1>${esc(title)}</h1><p>${esc(pageRecord.intro)}</p><div class="seo-link-grid">\n${list}\n</div></main><footer class="footer"><div class="container"><div class="footer-bottom"><span>&copy; 2026 MyRecon</span><span><a href="/privacy.html">Privacy policy</a> · <a href="/terms.html">Terms</a></span></div></div></footer></body></html>`;
}
function setAttr(tag, attr, value) {
  const escaped = esc(value);
  const re = new RegExp(`\\b${attr}\\s*=\\s*(["']).*?\\1`, "i");
  return re.test(tag) ? tag.replace(re, `${attr}="${escaped}"`) : tag.replace(/\s*\/?>(\s*)$/, ` ${attr}="${escaped}">$1`);
}
function syncPreservedPage(record) {
  const route = routeFor(record);
  const relative = PRESERVED.get(route);
  if (!relative) return;
  const file = path.join(FRONTEND, relative);
  let html = fs.readFileSync(file, "utf8");
  html = html.replace(/<title\b[^>]*>[\s\S]*?<\/title>/i, `<title>${esc(record.title)}</title>`);
  for (const [selector, attr, value] of [
    ["name", "description", record.description],
    ["property", "og:title", record.title], ["property", "og:description", record.description],
    ["property", "og:url", `${SITE}${route}`], ["name", "twitter:title", record.title],
    ["name", "twitter:description", record.description],
  ]) {
    const re = new RegExp(`<meta\\b(?=[^>]*\\b${selector}=["']${attr.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}["][^>]*)([^>]*>)`, "i");
    html = html.replace(re, (tag) => setAttr(tag, "content", value));
  }
  const canonical = `<link rel="canonical" href="${SITE}${route}">`;
  if (/<link\b[^>]*\brel=["']canonical["'][^>]*>/i.test(html)) {
    html = html.replace(/<link\b[^>]*\brel=["']canonical["'][^>]*>/i, canonical);
  } else html = html.replace(/<\/head>/i, `  ${canonical}\n</head>`);
  html = html.replaceAll(`${SITE}${relative.replace(/\\/g, "/")}`, `${SITE}${route}`);
  html = html.replaceAll(`/${relative.replace(/\\/g, "/")}`, route);
  const faqBlock = `<section class="container" style="margin:30px auto;padding:20px;border:1px solid var(--border,#394252);border-radius:12px"><h2>Frequently asked questions</h2>${record.faq.map((item) => `<details style="padding:12px 0;border-bottom:1px solid var(--border,#394252)"><summary style="font-weight:700;cursor:pointer">${esc(item.question)}</summary><p style="margin-top:10px;line-height:1.65">${esc(item.answer)}</p></details>`).join("")}</section>`;
  if (!record.faq.every((item) => html.includes(esc(item.question)))) {
    if (!/<\/main>/i.test(html)) fail(`${relative}: cannot place visible FAQs because main is missing`);
    html = html.replace(/<\/main>/i, `${faqBlock}</main>`);
  }
  let replacedFaq = false;
  html = html.replace(/<script\b(?=[^>]*\btype=["']application\/ld\+json["'])[^>]*>([\s\S]*?)<\/script>/gi, (whole, body) => {
    let value;
    try { value = JSON.parse(body); } catch { return whole; }
    let changed = false;
    if (value && value["@type"] === "FAQPage") { value = faqSchema(record); changed = true; }
    if (value && Array.isArray(value["@graph"])) {
      value["@graph"] = value["@graph"].map((entry) => {
        if (entry && entry["@type"] === "FAQPage") { changed = true; return faqSchema(record); }
        return entry;
      });
    }
    if (changed) replacedFaq = true;
    return changed ? `<script type="application/ld+json">${safeJson(value)}</script>` : whole;
  });
  if (!replacedFaq) html = html.replace(/<\/head>/i, `  <script type="application/ld+json">${safeJson(faqSchema(record))}</script>\n</head>`);
  if (route !== "/" && !/<username-search-input\b/i.test(html)) {
    const cta = `<section class="container" style="margin:30px auto;padding:20px;border:1px solid var(--border,#394252);border-radius:12px"><h2>Search a public username</h2><p>Use usernames you own or are authorized to review; a match is not proof of identity.</p><username-search-input></username-search-input></section>`;
    if (!/<\/main>/i.test(html)) fail(`${relative}: cannot place the username search because main is missing`);
    html = html.replace(/<\/main>/i, `${cta}</main>`);
    if (!/username-search-input\.js/i.test(html)) html = html.replace(/<\/body>/i, `  <script src="/assets/js/username-search-input.js" defer></script>\n</body>`);
  }
  fs.writeFileSync(file, html, "utf8");
}
function safeGeneratedFile(relative) {
  const file = path.resolve(FRONTEND, relative);
  const rel = path.relative(FRONTEND, file);
  if (rel.startsWith(`..${path.sep}`) || path.isAbsolute(rel) || !rel.endsWith(".html")) fail(`Unsafe generated path: ${relative}`);
  return file;
}
function addLibraryLinks(section, html) {
  const start = "<!-- seo-library-links:start -->";
  const end = "<!-- seo-library-links:end -->";
  const block = `${start}<section class="container" style="margin:28px auto;padding:18px;border:1px solid var(--border,#394252);border-radius:10px"><h2>Explore more MyRecon libraries</h2><p><a href="/find/">Username lookup pages</a> · <a href="/privacy/">Privacy and deletion guides</a> · <a href="/guides/">OSINT guides</a> · <a href="/vs/">Tool comparisons</a></p></section>${end}`;
  html = html.replace(new RegExp(`${start}[\\s\\S]*?${end}`, "g"), "");
  if (!html.includes("</main>")) fail(`${section}/index.html has no main element for library links`);
  return html.replace("</main>", `${block}</main>`);
}
function main() {
  const contentRoot = syncBundledContent();
  if (!fs.existsSync(contentRoot)) fail(`Content directory is missing: ${contentRoot}`);
  const records = allRecords(contentRoot);
  const previous = fs.existsSync(MANIFEST) ? JSON.parse(fs.readFileSync(MANIFEST, "utf8")) : { files: [] };
  const previousFiles = new Set(previous.files || []);
  const generated = new Set();
  const byKind = new Map();
  let rendered = 0;
  for (const record of records) {
    writeGuideDiagram(record);
    const route = routeFor(record);
    const preserved = PRESERVED.get(route);
    if (preserved) { syncPreservedPage(record); continue; }
    const file = fileFor(record);
    const relative = path.relative(FRONTEND, file).split(path.sep).join("/");
    if (fs.existsSync(file) && !previousFiles.has(relative)) fail(`Refusing to overwrite an existing page not owned by this generator: ${relative}`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, cleanHtml(renderPage(record)), "utf8");
    generated.add(relative);
    byKind.set(record.kind, [...(byKind.get(record.kind) || []), record]);
    rendered++;
  }
  for (const kind of ["target", "deletion"]) {
    const relative = `${CLUSTERS[kind]}/index.html`;
    const file = safeGeneratedFile(relative);
    if (fs.existsSync(file) && !previousFiles.has(relative)) fail(`Refusing to overwrite an existing library index: ${relative}`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, cleanHtml(renderHub(kind, byKind.get(kind) || [])), "utf8");
    generated.add(relative);
  }
  for (const [kind, relative] of [["guide", "guides/index.html"], ["comparison", "vs/index.html"]]) {
    const file = safeGeneratedFile(relative);
    const html = fs.readFileSync(file, "utf8");
    fs.writeFileSync(file, addLibraryLinks(kind, html), "utf8");
  }
  for (const stale of previousFiles) {
    if (generated.has(stale)) continue;
    const file = safeGeneratedFile(stale);
    if (fs.existsSync(file)) fs.unlinkSync(file);
  }
  fs.writeFileSync(MANIFEST, JSON.stringify({ generated_by: "frontend/scripts/build-seo-pages.js", files: [...generated].sort() }, null, 2) + "\n", "utf8");
  console.log(`[seo-pages] ${records.length} published records; rendered ${rendered} pages plus 2 hubs; reused ${records.length - rendered} existing canonical pages`);
}

main();

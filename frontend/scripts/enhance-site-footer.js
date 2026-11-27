/* Replace legacy footers with the same responsive site navigation everywhere. */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ROOT = path.resolve(__dirname, "..");
const logoHash = crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "assets/img/logo.svg"))).digest("hex").slice(0, 10);
const footerHash = crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "assets/css/site-footer.css"))).digest("hex").slice(0, 10);
// Sitewide links are the strongest internal signal the site sends, so they go
// to the pages people search for (the tools and their landing pages), not to
// utility pages. The HTML sitemap and badge page are noindexed and linked
// from the pages that need them instead.
const GROUPS = [
  ["Tools", [
    ["Username search", "/#tool"], ["Reverse email lookup", "/reverse-email-lookup.html"],
    ["Reverse username lookup", "/reverse-username-lookup.html"], ["Username checker", "/username-checker.html"], ["Discord ID lookup", "/discord-id-lookup.html"],
    ["Digital footprint checker", "/digital-footprint-checker.html"], ["Free OSINT tools", "/free-osint-tool.html"],
    ["Deep Search", "/deep-search.html"], ["Footprint tools", "/footprint"], ["All features", "/features.html"], ["Android app", "/app.html"],
    ["Plans", "/pricing.html"], ["API", "/developers.html"],
  ]],
  ["Explore", [
    ["OSINT guides", "/guides/"], ["OSINT glossary", "/osint-glossary.html"], ["Blog", "/blog/"], ["Breach archive", "/breaches/"], ["Breach case files", "/breaches/case-files/"],
    ["Platform lookups", "/find/"], ["Instagram username lookup", "/find/instagram-account"], ["GitHub profile lookup", "/find/github-profile"], ["Discord user lookup", "/find/discord-user"], ["Privacy guides", "/privacy/"], ["Free templates", "/templates/"],
  ]],
  ["Compare", [
    ["Upcoming OSINT tools 2026-2027", "/upcoming-osint-tools-2027.html"],
    ["MyRecon vs Sherlock", "/vs/sherlock"],
    ["WhatsMyName alternatives", "/whatsmyname-alternatives.html"],
    ["Best free OSINT tools", "/blog/best-free-osint-tools-for-investigators.html"],
    ["OSINT tool prices", "/osint-tool-pricing.html"],
    ["Choose a research workflow", "/vs/"],
  ]],
  ["Company", [
    ["About MyRecon", "/about.html"], ["Founder", "/founder.html"],
    ["Services", "/services.html"], ["Contact", "/contact.html"],
  ]],
  ["Legal", [
    ["Privacy policy", "/privacy.html"], ["Terms of use", "/terms.html"],
    ["Refund policy", "/refunds.html"], ["Cookie settings", "/cookies.html#manage", " data-cookie-settings"],
  ]],
];

function esc(value) { return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])); }

function renderFooter() {
  const groups = GROUPS.map(([heading, links]) => `<nav class="site-footer__group" aria-label="${esc(heading)}">
  <p class="site-footer__heading">${esc(heading)}</p>
  <ul>${links.map(([label, href, attr = ""]) => `<li><a href="${href}"${attr}>${esc(label)}</a></li>`).join("")}</ul>
</nav>`).join("\n");
  return `<footer class="site-footer">
  <div class="site-footer__panel">
    <div class="site-footer__top">
      <div class="site-footer__identity">
        <a class="site-footer__brand" href="/" aria-label="MyRecon home"><img src="/assets/img/logo.svg?v=${logoHash}" width="36" height="36" alt=""> <span>MyRecon</span></a>
        <p>Public-source research tools for personal audits and authorized work.</p>
        <a class="site-footer__email" href="mailto:aryan@bugsnaps.in">aryan@bugsnaps.in</a>
        <p><a class="site-footer__email" data-preferred-source href="https://www.google.com/preferences/source?q=myrecon.xyz" target="_blank" rel="noopener noreferrer" style="margin-top:0">Add MyRecon as a preferred source on Google <span aria-hidden="true">↗</span></a></p>
      </div>
      ${groups}
    </div>
    <div class="site-footer__bottom">
      <span>© ${new Date().getFullYear()} MyRecon. Built by Aryan Walia.</span>
      <span class="site-footer__note">Public sources. Careful review.</span>
      <div class="site-footer__social"><a href="https://github.com/4ryanwalia/Myrecon" target="_blank" rel="noopener noreferrer" aria-label="MyRecon on GitHub">GitHub <span aria-hidden="true">↗</span></a><a href="mailto:aryan@bugsnaps.in" aria-label="Email MyRecon">Email</a></div>
    </div>
  </div>
</footer>`;
}

function deduplicateAssetTags(html) {
  const seenCss = new Set();
  html = html.replace(
    /(?:^[ \t]*<link\b(?=[^>]*\brel=["']stylesheet["'])[^>]*\bhref=["']\/assets\/(?:optimized\/)?css\/([\w-]+)(?:\.[a-f0-9]{12})?\.css(?:\?[^"']*)?["'][^>]*>[ \t]*\r?\n|<link\b(?=[^>]*\brel=["']stylesheet["'])[^>]*\bhref=["']\/assets\/(?:optimized\/)?css\/([\w-]+)(?:\.[a-f0-9]{12})?\.css(?:\?[^"']*)?["'][^>]*>)/gim,
    (match, nameLine, nameInline) => {
      const key = (nameLine || nameInline).toLowerCase();
      if (seenCss.has(key)) return "";
      seenCss.add(key);
      return match;
    }
  );
  const seenJs = new Set();
  html = html.replace(
    /(?:^[ \t]*<script\b[^>]*\bsrc=["']\/assets\/(?:optimized\/)?js\/([\w-]+)(?:\.[a-f0-9]{12})?\.js(?:\?[^"']*)?["'][^>]*><\/script>[ \t]*\r?\n|<script\b[^>]*\bsrc=["']\/assets\/(?:optimized\/)?js\/([\w-]+)(?:\.[a-f0-9]{12})?\.js(?:\?[^"']*)?["'][^>]*><\/script>)/gim,
    (match, nameLine, nameInline) => {
      const key = (nameLine || nameInline).toLowerCase();
      if (seenJs.has(key)) return "";
      seenJs.add(key);
      return match;
    }
  );
  return html;
}

function enhance(file) {
  let html = fs.readFileSync(file, "utf8");
  const before = html;
  if (!/<html\b/i.test(html) || !/<\/body>/i.test(html)) return false;
  if (file !== path.join(ROOT, 'index.html')) {
    const footer = renderFooter();
    if (/<footer\b[^>]*>[\s\S]*?<\/footer>/i.test(html)) {
      html = html.replace(/<footer\b[^>]*>[\s\S]*?<\/footer>/i, footer);
    } else {
      html = html.replace(/<\/body>/i, `${footer}\n</body>`);
    }
    if (!/\/assets\/(?:optimized\/)?css\/site-footer(?:\.[a-f0-9]{12})?\.css/.test(html)) {
      html = html.replace(/<\/head>/i, `  <link rel="stylesheet" href="/assets/css/site-footer.css?v=${footerHash}">\n</head>`);
    }
  }
  html = deduplicateAssetTags(html);
  if (html === before) return false;
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      fs.writeFileSync(file, html, "utf8");
      return true;
    } catch (error) {
      if (error.code !== "UNKNOWN" || attempt === 4) throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 150 * (attempt + 1));
    }
  }
  return false;
}

let count = 0;
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (["assets", "content", "data", "scripts", "node_modules", ".vercel"].includes(entry.name)) continue;
      walk(path.join(dir, entry.name));
    } else if (entry.isFile() && entry.name.endsWith(".html") && enhance(path.join(dir, entry.name))) count++;
  }
}
walk(ROOT);
console.log(`Updated shared footer on ${count} HTML pages`);

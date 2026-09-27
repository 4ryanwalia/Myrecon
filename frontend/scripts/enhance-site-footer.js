/* Replace legacy footers with the same responsive site navigation everywhere. */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const GROUPS = [
  ["Products", [
    ["Username search", "/#tool"], ["Features", "/features.html"], ["Android app", "/app.html"],
    ["Plans", "/pricing.html"], ["API", "/developers.html"],
  ]],
  ["Explore", [
    ["Platform directory", "/find/"], ["OSINT guides", "/guides/"], ["Privacy guides", "/privacy/"],
    ["Breach archive", "/breaches/"], ["Breach case files", "/breaches/case-files/"],
  ]],
  ["Compare", [
    ["MyRecon vs Sherlock", "/vs/sherlock"], ["MyRecon vs Maigret", "/vs/maigret"],
    ["MyRecon vs WhatsMyName", "/vs/whatsmyname"], ["MyRecon vs HIBP", "/vs/have-i-been-pwned"],
    ["All comparisons", "/vs/"],
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
  <h2 class="site-footer__heading">${esc(heading)}</h2>
  <ul>${links.map(([label, href, attr = ""]) => `<li><a href="${href}"${attr}>${esc(label)}</a></li>`).join("")}</ul>
</nav>`).join("\n");
  return `<footer class="site-footer">
  <div class="site-footer__panel">
    <div class="site-footer__top">
      <div class="site-footer__identity">
        <a class="site-footer__brand" href="/" aria-label="MyRecon home"><img src="/assets/img/logo.svg" width="36" height="36" alt=""> <span>MyRecon</span></a>
        <p>Public-source research tools for personal audits and authorized work.</p>
        <a class="site-footer__email" href="mailto:aryan@bugsnaps.in">aryan@bugsnaps.in</a>
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

function enhance(file) {
  let html = fs.readFileSync(file, "utf8");
  if (!/<html\b/i.test(html) || !/<\/body>/i.test(html)) return false;
  if (!html.includes("site-footer__panel")) {
    const footer = renderFooter();
    if (/<footer\b[^>]*>[\s\S]*?<\/footer>/i.test(html)) {
      html = html.replace(/<footer\b[^>]*>[\s\S]*?<\/footer>/i, footer);
    } else {
      html = html.replace(/<\/body>/i, `${footer}\n</body>`);
    }
  }
  if (!html.includes("/assets/css/site-footer.css")) {
    html = html.replace(/<\/head>/i, `  <link rel="stylesheet" href="/assets/css/site-footer.css">\n</head>`);
  }
  fs.writeFileSync(file, html, "utf8");
  return true;
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

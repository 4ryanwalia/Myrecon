/* Put the Android app nudge (assets/js/app-nudge.js) on every public page.
 *
 * Runs from build-site.js after the homepage restore, like
 * enhance-article-promotion, so index.html gets it too. The tag carries a
 * hash of the script as ?v=, so a changed nudge reaches open browsers on the
 * next build without touching version-site-assets.js. Idempotent: a page
 * that already has the current tag is not rewritten.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '..');
const SCRIPT = '/assets/js/app-nudge.js';
const SKIP_DIRS = new Set(['assets', 'content', 'data', 'scripts', 'node_modules', '.vercel', 'tests', 'worker-console', 'api', 'downloads']);
// Pages where a promo would be noise or would sit inside someone else's page:
// the app page itself, checkout, and the embeddable badge.
const EXCLUDED = new Set(['app.html', 'pricing.html', 'badge.html']);
// The editorial pages AdSense reviews (the same folders install-adsense-tag.js
// tags). Kept popup-free while the review is pending (resubmit ~2026-11-25),
// so reviewers see the writing without a promo on top. On wide screens these
// pages already carry the sticky Android sidebar. Empty this list once
// AdSense approves the site.
const EXCLUDED_PREFIXES = ['blog/', 'guides/', 'breaches/case-files/'];

function excluded(rel) {
  return EXCLUDED.has(rel) || EXCLUDED_PREFIXES.some((prefix) => rel.startsWith(prefix));
}
const TAG_RE = /[ \t]*<script src="\/assets\/js\/app-nudge\.js(?:\?v=[^"]*)?" defer><\/script>\r?\n?/g;

function tag() {
  const hash = crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, SCRIPT.slice(1)))).digest('hex').slice(0, 10);
  return `<script src="${SCRIPT}?v=${hash}" defer></script>`;
}

function write(file, content) {
  for (let attempt = 0; attempt < 10; attempt++) {
    try { fs.writeFileSync(file, content, 'utf8'); return; } catch (error) {
      if (!['UNKNOWN', 'EBUSY', 'EPERM'].includes(error.code) || attempt === 9) throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
    }
  }
}

function run(root = ROOT) {
  const current = tag();
  let installed = 0;
  let removed = 0;
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name)) walk(full);
        continue;
      }
      if (!entry.isFile() || !entry.name.endsWith('.html')) continue;
      const rel = path.relative(root, full).replace(/\\/g, '/');
      const before = fs.readFileSync(full, 'utf8');
      if (!/<\/body>/i.test(before)) continue; // fragments and partials
      const stripped = before.replace(TAG_RE, '');
      let after = stripped;
      if (!excluded(rel)) {
        const at = stripped.toLowerCase().lastIndexOf('</body>');
        after = `${stripped.slice(0, at)}${current}\n${stripped.slice(at)}`;
      }
      if (after === before) continue;
      write(full, after);
      if (excluded(rel)) removed++; else installed++;
    }
  };
  walk(root);
  console.log(`[app-nudge] ${installed} page(s) updated, ${removed} removed`);
  return { installed, removed };
}

module.exports = { run, EXCLUDED, EXCLUDED_PREFIXES };
if (require.main === module) run();

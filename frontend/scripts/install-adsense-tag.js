const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PUB_ID = 'ca-pub-6109270472398539';
const TAG = `<!-- Google AdSense -->
<meta name="google-adsense-account" content="${PUB_ID}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${PUB_ID}" crossorigin="anonymous"></script>`;

const ADSENSE_REGEX = /<!-- Google AdSense -->\s*<meta name="google-adsense-account"[^>]*>\s*<script async src="https:\/\/pagead2\.googlesyndication\.com\/pagead\/js\/adsbygoogle\.js[^"]*" crossorigin="anonymous"><\/script>\s*/gi;
const ADSENSE_META_ONLY = /<meta name="google-adsense-account"[^>]*>\s*/gi;
const ADSENSE_SCRIPT_ONLY = /<script async src="https:\/\/pagead2\.googlesyndication\.com\/pagead\/js\/adsbygoogle\.js[^"]*" crossorigin="anonymous"><\/script>\s*/gi;

// The tag goes only on pages whose main content is original writing. After
// the fifth "low value content" notice (2026-11-17) this list was inverted:
// it used to cover the HIBP-derived breach pages and the tool, app-promo and
// services pages, while skipping the hand-written case files and guides.
// Tool screens, promos, legal pages and record-derived archive pages stay
// tag-free ("ads on screens without publisher content").
//
// 24 Nov 2026 (owner's choice): no ad script on pages whose first screen is a
// live search tool either. The homepage keeps only the account meta tag, the
// AdSense site-verification method, so the property stays verified.
const ALLOWED_ROOT_FILES = new Set([
  'about.html',
  'osint-tool-pricing.html',
  'username-sweep-vs-deep-search.html',
]);
const VERIFY_ONLY = new Set(['index.html']);
const META_TAG = `<meta name="google-adsense-account" content="${PUB_ID}">`;
// Promotional or thin pages inside otherwise editorial folders.
const EXCLUDED = new Set([
  'guides/myrecon-black-friday-sale-2026.html',
]);

function shouldHaveAdSense(relPath) {
  const norm = relPath.replace(/\\/g, '/');
  if (EXCLUDED.has(norm)) return false;
  if (!norm.includes('/')) return ALLOWED_ROOT_FILES.has(norm);
  // Long-form original writing: blog articles, guides, and the case files.
  if (norm.startsWith('blog/') || norm.startsWith('guides/')) return true;
  if (norm.startsWith('breaches/case-files/')) return true;
  // Everything else (breach archive entries built from the HIBP record,
  // generated /find/ /vs/ /privacy/ pages, videos, templates, legal and
  // utility pages) MUST NOT carry the tag.
  return false;
}

function safeWrite(file, content) {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      fs.writeFileSync(file, content, 'utf8');
      return true;
    } catch (err) {
      if (attempt === 4) throw err;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100 * (attempt + 1));
    }
  }
  return false;
}

let installedCount = 0;
let removedCount = 0;
let checkedCount = 0;

function visit(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!['assets', 'content', 'data', 'scripts', 'tests', 'node_modules', '.vercel'].includes(entry.name)) {
        visit(path.join(directory, entry.name));
      }
      continue;
    }
    if (!entry.isFile() || !entry.name.endsWith('.html')) continue;
    checkedCount++;
    const file = path.join(directory, entry.name);
    const relPath = path.relative(ROOT, file);
    let html = fs.readFileSync(file, 'utf8');
    const allowed = shouldHaveAdSense(relPath);

    if (VERIFY_ONLY.has(relPath.split(path.sep).join('/'))) {
      const before = html;
      html = html.replace(ADSENSE_REGEX, META_TAG + '\n');
      html = html.replace(ADSENSE_SCRIPT_ONLY, '');
      if (!html.includes(META_TAG)) {
        const head = /<head\b[^>]*>/i.exec(html);
        if (head) html = html.slice(0, head.index + head[0].length) + '\n' + META_TAG + html.slice(head.index + head[0].length);
      }
      if (html !== before) { safeWrite(file, html); removedCount++; }
    } else if (allowed) {
      if (!html.includes(PUB_ID)) {
        const head = /<head\b[^>]*>/i.exec(html);
        if (head) {
          const insertion = head.index + head[0].length;
          html = html.slice(0, insertion) + '\n' + TAG + html.slice(insertion);
          safeWrite(file, html);
          installedCount++;
        }
      }
    } else {
      if (html.includes(PUB_ID)) {
        html = html.replace(ADSENSE_REGEX, '');
        html = html.replace(ADSENSE_META_ONLY, '');
        html = html.replace(ADSENSE_SCRIPT_ONLY, '');
        safeWrite(file, html);
        removedCount++;
      }
    }
  }
}

visit(ROOT);
console.log(`[adsense-tag] Checked ${checkedCount} HTML pages. Installed on ${installedCount}, Removed from ${removedCount} non-editorial/templated pages.`);

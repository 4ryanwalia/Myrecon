/* Give changed site assets a fresh URL so open browsers fetch the deployed version. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '..');
const ASSETS = [
  '/assets/css/styles.css',
  '/assets/css/fx.css',
  '/assets/css/site-footer.css',
  '/assets/css/trust.css',
  '/assets/css/breaches.css',
  '/assets/css/content-app-promo.css',
  '/assets/css/deep-search-preview.css',
  '/assets/js/trust.js',
  '/assets/js/benchmarks.js',
  '/assets/js/username-benchmark.js',
  '/assets/css/username-benchmark.css',
  '/assets/js/partial-results.js',
  '/assets/js/app.js',
  '/assets/js/breach-check.js',
  '/assets/js/config.js',
  '/assets/js/deep-search.js',
  '/assets/js/fx.js',
  '/assets/js/pricing.js',
  '/assets/js/paypal-checkout.js',
  '/assets/js/username-search-input.js',
  '/assets/img/logo.svg',
  '/assets/img/favicon.svg',
];
const versions = ASSETS.map((url) => {
  const contents = fs.readFileSync(path.join(ROOT, url.slice(1)));
  return [url, crypto.createHash('sha256').update(contents).digest('hex').slice(0, 10)];
});

let updated = 0;
function updatePage(file) {
  const before = fs.readFileSync(file, 'utf8');
  const defaultTheme = /<html\b[^>]*\bdata-theme=["']light["']/i.test(before) ? 'light' : 'dark';
  const themeColor = defaultTheme === 'light' ? '#f7f7f4' : '#111111';
  let after = before.replace(
    /(<meta\s+name=["']theme-color["']\s+content=["'])[^"']*(["']\s*\/?>)/gi,
    `$1${themeColor}$2`,
  );
  for (const [url, version] of versions) {
    const escaped = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    after = after.replace(
      new RegExp(`(["'])${escaped}(?:\\?v=[^"']*)?\\1`, 'g'),
      (_match, quote) => `${quote}${url}?v=${version}${quote}`,
    );
  }
  if (after !== before) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        fs.writeFileSync(file, after, 'utf8');
        break;
      } catch (error) {
        if (error.code !== 'UNKNOWN' || attempt === 2) throw error;
      }
    }
    updated++;
  }
}

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (['assets', 'content', 'data', 'scripts', 'node_modules', '.vercel'].includes(entry.name)) continue;
      walk(path.join(dir, entry.name));
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      updatePage(path.join(dir, entry.name));
    }
  }
}

walk(ROOT);
console.log(`[assets] refreshed URLs on ${updated} HTML pages`);

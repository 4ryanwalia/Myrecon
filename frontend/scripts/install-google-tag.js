const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const TAG_ID = 'G-3L8YYC6NKF';
const ATTRIBUTION = '<script src="/assets/js/recommendation-analytics.js?v=1" defer></script>';
const ATTRIBUTION_SCRIPT = /<script\b[^>]*\bsrc=["']\/assets\/(?:optimized\/)?js\/recommendation-analytics(?:\.[a-f0-9]{12})?\.js(?:\?[^"']*)?["'][^>]*>\s*<\/script>/i;
const OLD_PAGE_VIEW = 'send_page_view: !window.MyReconAnalytics?.isBenchmark()';
const PAGE_VIEW = `send_page_view: !(
        analyticsPage.searchParams.get('mr_benchmark') === '1' ||
        (() => {
          try {
            return Number(sessionStorage.getItem('mr_benchmark_until')) > Date.now();
          } catch {
            return false;
          }
        })()
      )`;
const TAG = `${ATTRIBUTION}
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=${TAG_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  var analyticsPage = new URL(window.location.href);
  var analyticsReferrer = document.referrer ? new URL(document.referrer).origin : '';
  gtag('config', '${TAG_ID}', {
    page_location: analyticsPage.origin + analyticsPage.pathname,
    page_referrer: analyticsReferrer,
    ${PAGE_VIEW}
  });
</script>`;

// Treat this loading and measurement change as the same editorial content.
function normalizeAnalyticsBootstrap(html) {
  return html?.replace(ATTRIBUTION_SCRIPT, '').replace(OLD_PAGE_VIEW, PAGE_VIEW);
}

function updateGoogleTag(html, file) {
  if (/<meta\b[^>]*http-equiv=["']refresh["']/i.test(html)) return html;
  const head = /<head\b[^>]*>/i.exec(html);
  if (!head) return html;
  const insertion = head.index + head[0].length;
  const loaders = (html.match(/googletagmanager\.com\/gtag\/js\?id=/g) || []).length;
  const configs = (html.match(/gtag\(['"]config['"]/g) || []).length;
  if (!loaders && !configs) return html.slice(0, insertion) + '\n' + TAG + html.slice(insertion);
  if (loaders !== 1 || configs !== 1 || !html.includes(`id=${TAG_ID}`) || !html.includes(`'${TAG_ID}'`)) {
    throw new Error(`Unexpected or duplicate Google tag in ${file}`);
  }
  let next = ATTRIBUTION_SCRIPT.test(html)
    ? html.replace(ATTRIBUTION_SCRIPT, tag => /\sdefer(?:\s|=|>)/i.test(tag) ? tag : tag.replace('>', ' defer>'))
    : html.slice(0, insertion) + '\n' + ATTRIBUTION + html.slice(insertion);
  next = next.replace(OLD_PAGE_VIEW, PAGE_VIEW);
  if (!next.includes('send_page_view:')) {
    next = next.replace('page_referrer: analyticsReferrer', `page_referrer: analyticsReferrer,\n    ${PAGE_VIEW}`);
  }
  return next;
}

function visit(directory) {
  let updated = 0;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!['assets', 'content', 'data', 'scripts', 'tests', 'node_modules', '.vercel'].includes(entry.name)) {
        updated += visit(path.join(directory, entry.name));
      }
      continue;
    }
    if (!entry.isFile() || !entry.name.endsWith('.html')) continue;
    const file = path.join(directory, entry.name);
    const html = fs.readFileSync(file, 'utf8');
    const nextHtml = updateGoogleTag(html, path.relative(ROOT, file));
    if (nextHtml === html) continue;
    let written = false;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        fs.writeFileSync(file, nextHtml, 'utf8');
        written = true;
        break;
      } catch (err) {
        if (attempt === 4) throw err;
        const wait = 100 * (attempt + 1);
        const start = Date.now();
        while (Date.now() - start < wait) {}
      }
    }
    if (written) updated++;
  }
  return updated;
}

if (require.main === module) console.log(`[google-tag] updated ${visit(ROOT)} HTML pages`);
module.exports = { updateGoogleTag, normalizeAnalyticsBootstrap };

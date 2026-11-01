const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const TAG_ID = 'G-3L8YYC6NKF';
const ATTRIBUTION = '<script src="/assets/js/recommendation-analytics.js?v=1"></script>';
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
    send_page_view: !window.MyReconAnalytics?.isBenchmark()
  });
</script>`;

let updated = 0;
let checked = 0;

function visit(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!['assets', 'content', 'data', 'scripts', 'tests', 'node_modules', '.vercel'].includes(entry.name)) {
        visit(path.join(directory, entry.name));
      }
      continue;
    }
    if (!entry.isFile() || !entry.name.endsWith('.html')) continue;
    const file = path.join(directory, entry.name);
    const html = fs.readFileSync(file, 'utf8');
    if (/<meta\b[^>]*http-equiv=["']refresh["']/i.test(html)) continue;
    const head = /<head\b[^>]*>/i.exec(html);
    if (!head) continue;
    checked++;
    const loaders = (html.match(/googletagmanager\.com\/gtag\/js\?id=/g) || []).length;
    const configs = (html.match(/gtag\(['"]config['"]/g) || []).length;
    if (loaders || configs) {
      if (loaders !== 1 || configs !== 1 || !html.includes(`id=${TAG_ID}`) || !html.includes(`'${TAG_ID}'`)) {
        throw new Error(`Unexpected or duplicate Google tag in ${path.relative(ROOT, file)}`);
      }
      let next = html;
      if (!/\/assets\/(?:optimized\/)?js\/recommendation-analytics(?:\.[a-f0-9]{12})?\.js/.test(next)) {
        const insertion = head.index + head[0].length;
        next = next.slice(0, insertion) + '\n' + ATTRIBUTION + next.slice(insertion);
      }
      if (!next.includes('send_page_view:')) next = next.replace('page_referrer: analyticsReferrer',
        'page_referrer: analyticsReferrer,\n    send_page_view: !window.MyReconAnalytics?.isBenchmark()');
      if (next !== html) { fs.writeFileSync(file, next, 'utf8'); updated++; }
      continue;
    }
    const insertion = head.index + head[0].length;
    const nextHtml = html.slice(0, insertion) + '\n' + TAG + html.slice(insertion);
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
}

visit(ROOT);
console.log(`[google-tag] checked ${checked} HTML pages; installed on ${updated}`);

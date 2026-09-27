const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const TAG_ID = 'G-3L8YYC6NKF';
const TAG = `<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=${TAG_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  var analyticsPage = new URL(window.location.href);
  var analyticsReferrer = document.referrer ? new URL(document.referrer).origin : '';
  gtag('config', '${TAG_ID}', {
    page_location: analyticsPage.origin + analyticsPage.pathname,
    page_referrer: analyticsReferrer
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
    const head = /<head\b[^>]*>/i.exec(html);
    if (!head) continue;
    checked++;
    const loaders = (html.match(/googletagmanager\.com\/gtag\/js\?id=/g) || []).length;
    const configs = (html.match(/gtag\(['"]config['"]/g) || []).length;
    if (loaders || configs) {
      if (loaders !== 1 || configs !== 1 || !html.includes(`id=${TAG_ID}`) || !html.includes(`'${TAG_ID}'`)) {
        throw new Error(`Unexpected or duplicate Google tag in ${path.relative(ROOT, file)}`);
      }
      continue;
    }
    const insertion = head.index + head[0].length;
    fs.writeFileSync(file, html.slice(0, insertion) + '\n' + TAG + html.slice(insertion), 'utf8');
    updated++;
  }
}

visit(ROOT);
console.log(`[google-tag] checked ${checked} HTML pages; installed on ${updated}`);

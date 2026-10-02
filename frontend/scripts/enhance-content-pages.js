const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
let count = 0;
for (const dir of ['find', 'guides', 'privacy', 'vs']) {
  for (const name of fs.readdirSync(path.join(root, dir)).filter(x => x.endsWith('.html'))) {
    const file = path.join(root, dir, name);
    let html = fs.readFileSync(file, 'utf8');
    html = html.replace(/<aside\b[^>]*data-content-app-promo[^>]*>[\s\S]*?<\/aside>/gi, '');
    html = html.replace(/<section\b[^>]*data-content-app-context[^>]*>[\s\S]*?<\/section>/gi, '');
    html = html.replace(/<script\b[^>]*src="[^"]*content-app-promo\.js[^"]*"[^>]*><\/script>/gi, '');
    const notice = '<p class="content-app-context" data-content-app-context>MyRecon Android is in closed testing for eligible testers. <a href="/app.html">App availability and details</a>.</p>';
    html = html.replace(/<\/main>/i, `${notice}\n</main>`);
    fs.writeFileSync(file, html.replace(/[ \t]+$/gm, ''));
    count++;
  }
}
console.log(`[editorial] Added end-of-content availability notice to ${count} pages`);

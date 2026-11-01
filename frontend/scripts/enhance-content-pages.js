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
    html = html.replace(/\s*<p\b[^>]*data-content-app-context[^>]*>[\s\S]*?<\/p>/gi, '');
    html = html.replace(/<script\b[^>]*src="[^"]*content-app-promo\.js[^"]*"[^>]*><\/script>/gi, '');
    const topics = {
      find: ['Explore public username leads on Android', 'website_find'],
      guides: ['Try MyRecon username search on Android', 'website_guides'],
      privacy: ['Review your digital footprint on Android', 'website_privacy'],
      vs: ['Try MyRecon tools on Android', 'website_comparison'],
    };
    const [message, campaign] = /breach/i.test(name)
      ? ['Follow breach reports and alerts on Android', 'website_guides_breach']
      : topics[dir];
    const referrer = encodeURIComponent(`utm_source=myrecon.xyz&utm_medium=website&utm_campaign=${campaign}`);
    const notice = `<p class="content-app-context" data-content-app-context>${message}. <a href="https://play.google.com/store/apps/details?id=com.Myrecon.osint&amp;referrer=${referrer}">Get it on Google Play</a>.</p>`;
    html = html.replace(/\s*<\/main>/i, `\n${notice}\n</main>`);
    fs.writeFileSync(file, html.replace(/[ \t]+$/gm, ''));
    count++;
  }
}
console.log(`[editorial] Added end-of-content availability notice to ${count} pages`);

/* Resolve consolidated links after every article generator, before sitemap output. */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const redirects = JSON.parse(fs.readFileSync(path.join(root, 'content/editorial-redirects.json'), 'utf8'));
function destination(href) {
  let url;
  try { url = new URL(href, 'https://www.myrecon.xyz'); } catch { return href; }
  if (!['myrecon.xyz', 'www.myrecon.xyz'].includes(url.hostname)) return href;
  const route = redirects[url.pathname] ? url.pathname : url.pathname.replace(/\.html$/, '');
  return redirects[route] || href;
}
function walk(dir) {
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    if (item.name.startsWith('.') || ['node_modules', 'content', 'scripts', 'tests', 'data'].includes(item.name)) continue;
    const file = path.join(dir, item.name);
    if (item.isDirectory()) walk(file);
    else if (/\.(html|txt)$/.test(item.name)) {
      let text = fs.readFileSync(file, 'utf8');
      text = text.replace(/\bhref=(['"])(.*?)\1/g, (all, quote, href) => `href=${quote}${destination(href)}${quote}`);
      text = text.replace(/https:\/\/www\.myrecon\.xyz\/[^\s)<>"']+/g, destination);
      if (/<main\b[^>]*class="[^"]*seo-page/.test(text)) {
        text = text.replace('<header class="nav">', '<header class="nav editorial-nav">');
        if (!text.includes('/assets/css/editorial.css')) text = text.replace('</head>', '<link rel="stylesheet" href="/assets/css/editorial.css"></head>');
      }
      if (item.name === 'is-myrecon-legit.html') {
        text = text.replace(/<main\b[^>]*>[\s\S]*?<\/main>/i, fs.readFileSync(path.join(root, 'content/is-myrecon-legit-main.html'), 'utf8'));
        text = text.replace(/<script\b[^>]*type="application\/ld\+json"[^>]*>[\s\S]*?<\/script>/gi, '');
        const schema = { '@context': 'https://schema.org', '@type': 'Article', headline: 'Is MyRecon legit? Six checks you can review', url: 'https://www.myrecon.xyz/is-myrecon-legit.html', dateModified: '2026-10-03', author: { '@type': 'Organization', name: 'MyRecon' } };
        text = text.replace('</head>', `<script type="application/ld+json">${JSON.stringify(schema)}</script></head>`);
      }
      fs.writeFileSync(file, text.replace(/[ \t]+$/gm, ''));
    }
  }
}
walk(root);
console.log(`[editorial] Resolved links for ${Object.keys(redirects).length} consolidated routes`);

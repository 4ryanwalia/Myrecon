/* Keep visible navigation consistent with existing structured breadcrumbs. */
const fs = require('node:fs');
const path = require('node:path');
const { isNoindex } = require('./build-sitemap');
const root = path.resolve(__dirname, '..');
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
function find(value) {
  if (!value || typeof value !== 'object') return null;
  if (value['@type'] === 'BreadcrumbList') return value;
  for (const child of Object.values(value)) { const match = find(child); if (match) return match; }
  return null;
}
function walk(dir) { return fs.readdirSync(dir, {withFileTypes:true}).flatMap(e => e.name.startsWith('.') || ['node_modules','content','scripts','tests','data','worker-console'].includes(e.name) ? [] : e.isDirectory() ? walk(path.join(dir,e.name)) : e.name.endsWith('.html') ? [path.join(dir,e.name)] : []); }
let count = 0;
for (const file of walk(root)) {
  let html = fs.readFileSync(file, 'utf8');
  if (isNoindex(html) || !/<main\b/.test(html) || /aria-label=["']breadcrumbs?["']/i.test(html)) continue;
  let crumbs;
  for (const [, raw] of html.matchAll(/<script\b[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi)) { crumbs = find(JSON.parse(raw)); if (crumbs) break; }
  if (!crumbs || crumbs.itemListElement.length < 2) continue;
  const items = crumbs.itemListElement;
  const nav = `<nav class="search-breadcrumbs" aria-label="Breadcrumb"><ol>${items.map((item, i) => `<li>${i === items.length - 1 ? `<span aria-current="page">${esc(item.name)}</span>` : `<a href="${esc(item.item)}">${esc(item.name)}</a>`}</li>`).join('')}</ol></nav>`;
  html = html.replace(/(<main\b[^>]*>)/, '$1' + nav);
  if (!html.includes('/assets/css/search-discovery.css')) html = html.replace('</head>', '<link rel="stylesheet" href="/assets/css/search-discovery.css"></head>');
  fs.writeFileSync(file, html); count++;
}
console.log(`[breadcrumbs] Added visible trails to ${count} pages`);

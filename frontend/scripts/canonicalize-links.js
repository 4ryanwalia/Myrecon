/* Link directly to final public URLs without dropping tool fragments or queries. */
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '..');
function canonicalHref(href, redirects) {
  if (!href.startsWith('/') || href.startsWith('//')) return href;
  const url = new URL(href, 'https://www.myrecon.xyz');
  const visited = new Set();
  while (redirects.has(url.pathname)) {
    if (visited.has(url.pathname)) throw new Error(`Redirect cycle: ${href}`);
    visited.add(url.pathname);
    url.pathname = redirects.get(url.pathname);
  }
  return url.pathname + url.search + url.hash;
}
function canonicalizeLinks(root = ROOT) {
  const config = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json')));
  const redirects = new Map(config.redirects.filter(r => !r.source.includes(':') && !r.has && !r.missing && r.destination.startsWith('/')).map(r => [r.source, r.destination]));
  let count = 0;
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith('.') || ['assets', 'content', 'data', 'scripts', 'tests', 'node_modules', 'worker-console'].includes(entry.name)) continue;
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(file);
      else if (entry.name.endsWith('.html')) {
        const before = fs.readFileSync(file, 'utf8');
        const after = before.replace(/(<a\b[^>]*?\bhref=)(['"])([^'"]*)\2/gi, (all, prefix, quote, href) => `${prefix}${quote}${canonicalHref(href, redirects)}${quote}`);
        if (before !== after) { fs.writeFileSync(file, after); count++; }
      }
    }
  }
  walk(root);
  console.log(`[links] Direct canonical links on ${count} pages`);
}
if (require.main === module) canonicalizeLinks();
module.exports = { canonicalHref, canonicalizeLinks };

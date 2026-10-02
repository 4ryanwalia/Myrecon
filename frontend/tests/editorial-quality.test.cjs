const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const redirects = JSON.parse(fs.readFileSync(path.join(root, 'content/editorial-redirects.json')));
const config = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json')));
const sitemap = fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8');
test('consolidated pages are removed, redirected without chains and absent from sitemap', () => {
  for (const [source, destination] of Object.entries(redirects)) {
    assert.ok(!redirects[destination], `chain: ${source}`);
    for (const route of source.endsWith('.html') ? [source] : [source, `${source}.html`]) {
      assert.ok(config.redirects.some(r => r.source === route && r.destination === destination && r.permanent), route);
    }
    assert.ok(!fs.existsSync(path.join(root, source.slice(1) + (source.endsWith('.html') ? '' : '.html'))), source);
    assert.ok(!sitemap.includes(`<loc>https://www.myrecon.xyz${source}</loc>`), source);
  }
});
test('revised pages answer their topic and promotions follow the content', () => {
  const notes = fs.readFileSync(path.join(root, 'guides/protect-researcher-notes.html'), 'utf8');
  const brand = fs.readFileSync(path.join(root, 'guides/brand-impersonation-monitoring.html'), 'utf8');
  assert.match(notes, /Test the permissions/);
  assert.match(notes, /retention log/);
  assert.match(brand, /official baseline/);
  assert.match(brand, /evidence packet/);
  for (const route of ['guides/protect-researcher-notes', 'find/github-profile', 'find/instagram-account', 'find/discord-user', 'vs/sherlock']) {
    const html = fs.readFileSync(path.join(root, `${route}.html`), 'utf8');
    assert.ok(!html.includes('data-content-app-promo'));
    assert.ok(html.indexOf('data-content-app-context') > html.indexOf('</article>'));
    assert.ok(!/best handled as a narrow|100\+ on the web|Free, ad-supported/.test(html));
  }
  assert.ok(!notes.includes('<username-search-input>'));
  assert.match(fs.readFileSync(path.join(root, 'find/discord-user.html'), 'utf8'), /no direct Discord/);
});
test('internal page links resolve after consolidation', () => {
  const failures = new Set();
  function walk(dir) {
    for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
      if (item.name.startsWith('.') || ['content', 'node_modules', 'tests', 'scripts', 'data', 'assets'].includes(item.name)) continue;
      const file = path.join(dir, item.name);
      if (item.isDirectory()) walk(file);
      else if (item.name.endsWith('.html')) {
        const html = fs.readFileSync(file, 'utf8');
        for (const match of html.matchAll(/href=["']([^"']+)["']/g)) {
          const href = match[1];
          if (!href.startsWith('/') || href.startsWith('//') || href.startsWith('/assets/') || href.startsWith('/data/')) continue;
          const route = href.split(/[?#]/)[0];
          const disk = path.join(root, route.slice(1));
          if (!fs.existsSync(disk) && !fs.existsSync(`${disk}.html`) && !fs.existsSync(path.join(disk, 'index.html')) && !config.redirects.some(r => r.source === route)) failures.add(`${path.relative(root, file)} -> ${route}`);
        }
      }
    }
  }
  walk(root);
  assert.deepEqual([...failures], []);
});

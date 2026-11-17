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
// The fifth AdSense "low value content" notice (2026-11-17) came while ~75 of
// ~330 indexed pages were name-swapped copies of each other (best-*-2027
// listicles, Black Friday deal pages, *-username-osint-tool guides, /vs/
// pages) at up to 99% shared text. The renderer's intro check passed them
// all, so this measures the rendered text itself: the share of a page's
// five-word phrases that also appear on another indexed page.
test('no two indexed article pages are near-duplicates of each other', () => {
  const dirs = ['guides', 'vs', 'find', 'privacy', 'blog', 'breaches', 'breaches/case-files', 'templates'];
  const shingles = new Map();
  for (const dir of dirs) {
    const full = path.join(root, dir);
    if (!fs.existsSync(full)) continue;
    for (const name of fs.readdirSync(full)) {
      if (!name.endsWith('.html') || name === 'index.html') continue;
      const html = fs.readFileSync(path.join(full, name), 'utf8');
      if (/<meta[^>]+name="robots"[^>]+noindex/i.test(html)) continue;
      const main = (html.match(/<main\b[^>]*>([\s\S]*)<\/main>/i) || [, html])[1]
        .replace(/<(script|style|svg|nav)\b[\s\S]*?<\/\1>/gi, ' ')
        .replace(/<[^>]+>/g, ' ').replace(/&[a-z#0-9]+;/gi, ' ').toLowerCase();
      const words = main.split(/\s+/).filter(Boolean);
      const set = new Set();
      for (let i = 0; i + 5 <= words.length; i++) set.add(words.slice(i, i + 5).join(' '));
      if (set.size > 50) shingles.set(`${dir}/${name}`, set);
    }
  }
  const pages = [...shingles.keys()];
  const offenders = [];
  for (let i = 0; i < pages.length; i++) {
    for (let j = i + 1; j < pages.length; j++) {
      const a = shingles.get(pages[i]); const b = shingles.get(pages[j]);
      const [small, big] = a.size <= b.size ? [a, b] : [b, a];
      let shared = 0;
      for (const s of small) if (big.has(s)) shared++;
      const overlap = shared / small.size;
      if (overlap > 0.75) offenders.push(`${pages[i]} <> ${pages[j]} ${(overlap * 100).toFixed(0)}%`);
    }
  }
  assert.ok(pages.length > 100, 'expected the article sections to be scanned');
  assert.deepEqual(offenders, [], 'near-duplicate pages: rewrite one or retire it with a redirect');
});

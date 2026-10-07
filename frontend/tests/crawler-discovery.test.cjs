const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { toUrlPath, validDate, lastmod, collectEntries, renderSitemap, buildSitemap } = require('../scripts/build-sitemap.js');
const { buildLlms } = require('../scripts/build-llms.js');

const site = 'https://www.myrecon.xyz';
const today = '2026-10-08';
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'myrecon-crawl-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}
function write(root, relative, contents) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, contents, 'utf8');
  return file;
}
function page(route, extra = '') {
  return `<html><head><title>Public resource</title><link href="${site}${route}" rel="canonical">${extra}</head><body>Public content</body></html>`;
}

test('canonical parsing rejects conflicting, private-host and parameter variants', () => {
  const file = path.join(__dirname, '../example.html');
  assert.equal(toUrlPath(file, '<link REL = "alternate canonical" HREF = "https://myrecon.xyz/example.html">'), '/example.html');
  for (const href of ['https://elsewhere.example/example.html', 'https://www.myrecon.xyz:8443/example.html', 'https://user:pass@www.myrecon.xyz/example.html', 'http://www.myrecon.xyz/example.html', '/example.html?q=one&amp;page=two', '/example.html#section', '', 'http://[invalid']) {
    assert.equal(toUrlPath(file, `<link rel="canonical" href="${href}">`), null, href);
  }
  assert.equal(toUrlPath(file, '<link rel="canonical" href="/a.html"><link rel="canonical" href="/b.html">'), null);
  assert.equal(toUrlPath(file, '<link rel="canonical" href="/a.html"><link rel="canonical" href="/a.html">'), '/a.html');
});

test('lastmod uses validated content dates and never a checkout timestamp', () => {
  assert.equal(validDate('2026-02-30', today), '');
  assert.equal(validDate('2026-10-09', today), '');
  assert.equal(validDate('2026-10-07nonsense', today), '');
  assert.equal(validDate('2026-10-07T99:99:99Z', today), '');
  assert.equal(validDate('2026-10-07T12:30:00Z', today), '2026-10-07');
  const root = path.resolve(os.tmpdir(), 'myrecon-date-example');
  const file = path.join(root, 'article.html');
  const options = { root, today, gitDateFor: () => '2026-10-02' };
  const html = page('/article.html', '<script type="application/ld+json">{"datePublished":"2026-09-20","dateModified":"2026-10-08"}</script>');
  assert.equal(lastmod(file, html, new Map([['article.html', '2026-10-04']]), options), '2026-10-08');
  assert.equal(lastmod(file, page('/article.html', '<script type="application/ld+json">{"dateModified":"2026-10-10"}</script>'), new Map(), options), '2026-10-02');
  assert.equal(lastmod(file, '<p>"dateModified":"2026-10-08"</p>', new Map(), { ...options, gitDateFor: () => '' }), '');
});

test('sitemap contains only public canonical documents and XML-escapes URLs', t => {
  const root = fixture(t);
  write(root, 'index.html', page('/'));
  write(root, 'article.html', page('/article.html', '<script type="application/ld+json">{"dateModified":"2026-10-08"}</script>'));
  write(root, 'features.html', page('/features'));
  write(root, 'alias.html', page('/article.html'));
  write(root, 'redirect.html', page('/redirect.html'));
  write(root, 'private.html', page('/private.html', '<meta content = "none" name = "bingbot">'));
  write(root, 'refresh.html', page('/refresh.html', '<meta content="0;url=/" http-equiv = "refresh">'));
  write(root, 'fragment.html', '<p>Fragment</p>');
  write(root, '404.html', page('/404.html'));
  write(root, 'content/source.html', page('/content/source.html'));
  write(root, 'worker-console/index.html', page('/worker-console/'));
  write(root, 'broken.html', page('/missing.html'));
  write(root, 'a&b.html', page('/a&amp;b.html'));
  write(root, 'vercel.json', JSON.stringify({ redirects: [{ source: '/redirect.html', destination: '/article.html' }] }));
  const { entries } = collectEntries({ root, environment: {}, today, gitDateFor: () => '' });
  assert.deepEqual(entries.map(entry => entry.url), ['/', '/a&b.html', '/article.html', '/features']);
  const xml = renderSitemap(entries);
  assert.match(xml, /<loc>https:\/\/www\.myrecon\.xyz\/a&amp;b\.html<\/loc>/);
  assert.match(xml, /<loc>https:\/\/www\.myrecon\.xyz\/article\.html<\/loc><lastmod>2026-10-08<\/lastmod>/);
  assert.ok(!xml.includes('<loc>https://www.myrecon.xyz/</loc><lastmod>'));
});

test('unchanged sitemap rebuild preserves the child and index artifacts', t => {
  const root = fixture(t);
  write(root, 'index.html', page('/'));
  const options = { root, environment: {}, today, gitDateFor: () => '' };
  buildSitemap(options);
  const targets = ['sitemap.xml', 'sitemap-index.xml'].map(name => path.join(root, name));
  for (const target of targets) fs.utimesSync(target, new Date('2020-01-01'), new Date('2020-01-01'));
  const stamps = targets.map(target => fs.statSync(target).mtimeMs);
  buildSitemap(options);
  assert.deepEqual(targets.map(target => fs.statSync(target).mtimeMs), stamps);
  const index = fs.readFileSync(targets[1], 'utf8');
  assert.match(index, /<loc>https:\/\/www\.myrecon\.xyz\/sitemap\.xml<\/loc>/);
  assert.ok(!index.includes('<lastmod>'));
});

test('llms navigation follows redirects and stays deterministic after article additions', t => {
  const root = fixture(t);
  write(root, 'index.html', page('/'));
  write(root, 'features.html', page('/features'));
  write(root, 'vercel.json', JSON.stringify({ redirects: [{ source: '/old.html', destination: '/features' }] }));
  write(root, 'llms.txt', '# MyRecon\n\n- [Features](https://www.myrecon.xyz/old.html)\n\n<!-- BEGIN GENERATED BLOG LINKS -->\n<!-- END GENERATED BLOG LINKS -->\n');
  for (const [slug, date, title] of [['alpha', '2026-10-01', 'Alpha guide'], ['zeta', '2026-10-08', 'Zeta guide']]) {
    write(root, `content/blog/${slug}.html`, `<!-- ${JSON.stringify({ headline: title, description: 'Public research guide.', dateModified: date })} -->\n<h2>Resource</h2>`);
    write(root, `blog/${slug}.html`, page(`/blog/${slug}.html`));
  }
  const first = buildLlms(root);
  assert.ok(first.includes('[Features](https://www.myrecon.xyz/features)'));
  assert.ok(first.indexOf('Zeta guide') < first.indexOf('Alpha guide'));
  assert.equal(buildLlms(root), first);
  const file = path.join(root, 'llms.txt');
  fs.utimesSync(file, new Date('2020-01-01'), new Date('2020-01-01'));
  buildLlms(root);
  assert.equal(fs.statSync(file).mtimeMs, Date.parse('2020-01-01'));
});

test('all named and future crawlers share public access and protected-path rules', () => {
  const robots = fs.readFileSync(path.resolve(__dirname, '../robots.txt'), 'utf8');
  const groups = [];
  let current = null;
  for (const line of robots.split(/\r?\n/)) {
    const match = line.replace(/#.*/, '').trim().match(/^(User-agent|Allow|Disallow):\s*(.*)$/i);
    if (!match) continue;
    const [, directive, value] = match;
    if (directive.toLowerCase() === 'user-agent') {
      if (!current || current.rules.length) { current = { agents: [], rules: [] }; groups.push(current); }
      current.agents.push(value.toLowerCase());
    } else current.rules.push([directive.toLowerCase(), value]);
  }
  assert.equal(groups.length, 1, 'A new named group must not lose shared exclusions');
  const group = groups[0];
  assert.ok(group.agents.includes('*'));
  for (const agent of ['OAI-SearchBot', 'GPTBot', 'ChatGPT-User', 'Claude-SearchBot', 'Claude-User', 'ClaudeBot', 'Googlebot', 'Google-Extended', 'bingbot', 'Applebot', 'Applebot-Extended', 'PerplexityBot', 'Perplexity-User', 'DuckAssistBot', 'Amazonbot', 'Amzn-SearchBot', 'Amzn-User']) {
    assert.ok(group.agents.includes(agent.toLowerCase()), agent);
  }
  for (const route of ['/api/', '/content/', '/worker-console/']) assert.ok(group.rules.some(([type, value]) => type === 'disallow' && value === route), route);
  assert.ok(group.rules.some(([type, value]) => type === 'allow' && value === '/'));
  assert.ok(!group.rules.some(([type, value]) => type === 'disallow' && (value === '/' || value.includes('?'))));
  assert.match(robots, /^Sitemap: https:\/\/www\.myrecon\.xyz\/sitemap-index\.xml$/m);
});

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { toUrlPath, isNoindex, xmlEscape } = require('../scripts/build-sitemap');
const root = path.resolve(__dirname, '..');

test('sitemap excludes noindex directives regardless of meta attribute order', () => {
  assert.equal(isNoindex('<meta content="noindex, follow" name="robots">'), true);
  assert.equal(isNoindex("<meta name='googlebot' content='none'>"), true);
  assert.equal(isNoindex('<meta name="robots" content="index, follow">'), false);
});
test('sitemap uses local canonical paths and excludes external originals', () => {
  assert.equal(toUrlPath(path.join(root, 'pricing.html'), '<link href="https://www.myrecon.xyz/pricing" rel="canonical">'), '/pricing');
  assert.equal(toUrlPath(path.join(root, 'other.html'), '<link rel="canonical" href="https://example.com/original">'), null);
  assert.equal(xmlEscape('https://example.com/?a=1&b=2'), 'https://example.com/?a=1&amp;b=2');
});
test('homepage FAQ structured answers match visible questions and answers', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const schemas = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1]));
  const faq = schemas.find(s => s['@type'] === 'FAQPage');
  for (const q of faq.mainEntity) {
    assert.ok(html.includes(`<summary>${q.name}</summary>`), q.name);
    assert.ok(html.includes(`<p>${q.acceptedAnswer.text}</p>`), q.name);
  }
});
test('username landing page exposes valid local links and matching FAQ schema', () => {
  const html = fs.readFileSync(path.join(root, 'username-checker.html'), 'utf8');
  assert.equal((html.match(/<h1\b/g) || []).length, 1);
  assert.ok(!/[\u2013\u2014]/.test(html));
  for (const [, href] of html.matchAll(/href="(\/[^"?#]*)(?:[?#][^"]*)?"/g)) {
    const rel = href.slice(1);
    assert.ok([rel, `${rel}.html`, `${rel}index.html`].some(p => fs.existsSync(path.join(root, p))), href);
  }
  const schemas = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1]));
  const faq = schemas.flatMap(s => s['@graph'] || [s]).find(s => s['@type'] === 'FAQPage');
  for (const q of faq.mainEntity) {
    assert.ok(html.includes(`<summary>${q.name}</summary>`));
    assert.ok(html.includes(`<p>${q.acceptedAnswer.text}</p>`));
  }
  assert.ok(fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8').includes('https://www.myrecon.xyz/username-checker.html'));
});

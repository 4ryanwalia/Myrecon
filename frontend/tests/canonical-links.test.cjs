const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { canonicalHref } = require('../scripts/canonicalize-links');
const config = require('../vercel.json');
test('canonical links retain tool state and external destinations', () => {
  const redirects = new Map([['/old', '/middle'], ['/middle', '/final.html']]);
  assert.equal(canonicalHref('/old?q=hello#section', redirects), '/final.html?q=hello#section');
  for (const href of ['/#tool=email', '#section', '//example.com/old', 'https://example.com/old']) assert.equal(canonicalHref(href, redirects), href);
  assert.throws(() => canonicalHref('/old', new Map([['/old', '/old']])), /cycle/);
});
test('canonical sitemap URLs never redirect; alternate routes have one final destination', () => {
  const sitemap = fs.readFileSync(path.join(__dirname, '../sitemap.xml'), 'utf8');
  const routes = new Set([...sitemap.matchAll(/<loc>https:\/\/www.myrecon.xyz([^<]*)<\/loc>/g)].map(m => m[1]));
  const redirects = new Map(config.redirects.filter(r => !r.source.includes(':')).map(r => [r.source, r.destination]));
  assert.equal(redirects.size, config.redirects.filter(r => !r.source.includes(':')).length, 'unique sources');
  for (const route of routes) assert.ok(!redirects.has(route), route);
  for (const [source, dest] of redirects) assert.ok(!redirects.has(dest), `chain: ${source} -> ${dest}`);
});

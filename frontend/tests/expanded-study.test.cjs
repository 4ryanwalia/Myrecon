const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const route = '/blog/username-search-controlled-study-2026.html';
const data = JSON.parse(fs.readFileSync(path.join(root, 'assets/downloads/username-controls-2026-11-01/study.json'), 'utf8'));
const article = fs.readFileSync(path.join(root, route), 'utf8');

test('study renders every measured control without requiring JavaScript', () => {
  const matrix = article.match(/<table id="control-matrix">([\s\S]*?)<\/table>/)[1];
  assert.equal([...matrix.matchAll(/<tr>/g)].length, 36);
  for (const row of data.checks) {
    assert.ok(matrix.includes(row.id + ' · ' + row.platform));
    assert.ok(matrix.includes('<code>' + row.handle + '</code>'));
  }
  for (const tool of ['myrecon','sherlock','maigret']) {
    assert.ok(article.includes(data.tool_metadata[tool].version));
    assert.ok(article.includes(data.tool_metadata[tool].commit));
  }
  assert.match(article, /No definitive false positives were observed/);
  assert.match(article, /Eleven reference checks remained unresolved/);
  assert.match(article, /no newly created owner-controlled positive accounts/);
});

test('published evidence and crawler entry points are usable', () => {
  for (const [, href] of article.matchAll(/href="(\/assets\/downloads\/[^"#]+)"/g)) {
    assert.ok(fs.statSync(path.join(root, href)).size > 0, href);
  }
  for (const file of ['index.html', 'blog/index.html', 'blog/username-search-benchmark-research.html', 'blog/sherlock-vs-maigret-vs-myrecon.html']) {
    assert.ok(fs.readFileSync(path.join(root, file), 'utf8').includes(`href="${route}"`), file);
  }
  assert.ok(fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8').includes('https://www.myrecon.xyz' + route));
  assert.ok(article.includes(`rel="canonical" href="https://www.myrecon.xyz${route}"`));
  assert.equal([...article.matchAll(/<h1\b/g)].length, 1);
  const ids = [...article.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  assert.equal(new Set(ids).size, ids.length, 'anchors must be unique');
});

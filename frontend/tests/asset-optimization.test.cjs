const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const { optimizeAssets } = require('../scripts/optimize-assets');

test('deployment assets preserve behavior, share fingerprints and refresh only after source changes', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'myrecon-assets-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const kind of ['css', 'js']) fs.mkdirSync(path.join(root, 'assets', kind), { recursive: true });
  fs.writeFileSync(path.join(root, 'assets/js/app.js'), '/* explanation */ window.result = 2 + 3;');
  fs.writeFileSync(path.join(root, 'assets/css/style.css'), 'body { color: red; }');
  fs.writeFileSync(path.join(root, 'assets/css/relative.css'), 'body { background: url(../img/test.png); }');
  const html = '<link href="/assets/css/style.css?v=old"><link href="/assets/css/relative.css"><script src="/assets/js/env.js"></script><script defer src="/assets/js/app.js?v=old"></script>';
  for (const page of ['index.html', 'other.html']) fs.writeFileSync(path.join(root, page), html);
  const first = optimizeAssets(root);
  const built = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  assert.equal(built, fs.readFileSync(path.join(root, 'other.html'), 'utf8'));
  assert.match(built, /src="\/assets\/js\/env.js"/);
  assert.match(built, /href="\/assets\/css\/relative.css"/);
  assert.match(built, /script defer/);
  const js = first.assets['/assets/js/app.js'];
  const sandbox = { window: {} };
  vm.runInNewContext(fs.readFileSync(path.join(root, js.output), 'utf8'), sandbox);
  assert.equal(sandbox.window.result, 5);
  assert.deepEqual(optimizeAssets(root), first);
  fs.writeFileSync(path.join(root, 'assets/js/app.js'), 'window.result = 9;');
  const next = optimizeAssets(root);
  assert.notEqual(next.assets['/assets/js/app.js'].output, js.output);
  assert.equal(next.assets['/assets/css/style.css'].output, first.assets['/assets/css/style.css'].output);
  assert.ok(fs.existsSync(path.join(root, js.output)), 'old fingerprint remains valid during local rebuilds');
});

test('head stylesheets are joined in order, never across an inline style, and Google Fonts become self-hosted', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'myrecon-bundle-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const kind of ['css', 'js']) fs.mkdirSync(path.join(root, 'assets', kind), { recursive: true });
  for (const name of ['a', 'b', 'c', 'd']) fs.writeFileSync(path.join(root, `assets/css/${name}.css`), `.${name}{color:red}`);
  fs.writeFileSync(path.join(root, 'assets/css/fonts.css'), '@font-face{font-family:Inter;src:url(/assets/fonts/x.woff2)}');
  fs.writeFileSync(path.join(root, 'index.html'), [
    '<html><head>',
    '  <link rel="preconnect" href="https://fonts.googleapis.com">',
    '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
    '  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">',
    '  <link rel="stylesheet" href="/assets/css/a.css?v=1">',
    '  <link rel="stylesheet" href="/assets/css/b.css">',
    '  <style>.inline{}</style>',
    '  <link rel="stylesheet" href="/assets/css/c.css">',
    '  <link rel="stylesheet" href="/assets/css/d.css" media="print">',
    '</head><body><link rel="stylesheet" href="/assets/css/d.css"></body></html>',
  ].join('\n'));
  fs.writeFileSync(path.join(root, 'other.html'), '<html><head><link href="https://fonts.googleapis.com/css2?family=Inter&family=Roboto" rel="stylesheet"></head></html>');
  optimizeAssets(root);
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  assert.ok(!html.includes('fonts.googleapis.com') && !html.includes('fonts.gstatic.com'));
  assert.match(html, /rel="preload" href="\/assets\/fonts\/[^"]+\.woff2" as="font"/);
  const head = html.slice(0, html.indexOf('</head>'));
  const bundles = [...head.matchAll(/href="(\/assets\/optimized\/css\/bundle\.[a-f0-9]{12}\.css)"/g)].map(m => m[1]);
  assert.equal(bundles.length, 1, 'fonts, a and b share one bundle; c stays alone after the inline style');
  assert.equal(fs.readFileSync(path.join(root, bundles[0]), 'utf8').replace(/\s/g, ''), '@font-face{font-family:Inter;src:url(/assets/fonts/x.woff2)}.a{color:red}.b{color:red}');
  assert.ok(head.indexOf(bundles[0]) < head.indexOf('<style>') && head.indexOf('<style>') < head.indexOf('/c.'));
  assert.match(head, /d\.[a-f0-9]{12}\.css" media="print"/);
  assert.match(html.slice(html.indexOf('<body>')), /\/assets\/optimized\/css\/d\.[a-f0-9]{12}\.css/, 'body stylesheets are left alone');
  assert.match(fs.readFileSync(path.join(root, 'other.html'), 'utf8'), /fonts\.googleapis\.com/, 'other families keep Google Fonts');
});

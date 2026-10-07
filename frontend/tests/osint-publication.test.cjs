const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { validateArticle, articleContent, readArticles } = require('../scripts/build-blog');
const root = path.resolve(__dirname, '..');
const site = 'https://www.myrecon.xyz';

test('article metadata cannot advertise invisible answers or tools', () => {
  const meta = { title: 'Example', headline: 'Example', description: 'Example', category: 'Example', datePublished: '2026-10-08', dateModified: '2026-10-08' };
  const body = '<h2>Visible question?</h2><p>Visible answer.</p>';
  validateArticle({ ...meta, faq: [{question:'Visible question?', answer:'Visible answer.'}] }, body, 'fixture');
  assert.throws(() => validateArticle({ ...meta, faq: [{question:'Visible question?', answer:'Invented answer.'}] }, body, 'fixture'), /match visible/);
  assert.throws(() => validateArticle({ ...meta, tools: [{name:'Invisible tool', url:'https://example.com', description:'Example'}] }, body, 'fixture'), /match visible/);
  assert.throws(() => validateArticle({ ...meta, dateModified:'2026-10-07' }, body, 'fixture'), /precedes publication/);
  assert.throws(() => validateArticle({ ...meta, datePublished:'2026-02-30' }, body, 'fixture'), /invalid datePublished/);
});

test('section links resolve when headings repeat or already have IDs', () => {
  const {content, toc} = articleContent('<h2 id="sources">Sources</h2><h2>Sources</h2><h2>Sources</h2>');
  const ids = [...content.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  assert.equal(new Set(ids).size, 3);
  for (const [, id] of toc.matchAll(/href="#([^"]+)"/g)) assert.ok(ids.includes(id));
});

test('reviewed articles are published with matching canonical, FAQ and date data', () => {
  const articles = readArticles().filter(article => article.datePublished === '2026-10-08');
  assert.equal(articles.length, 12, 'expected the twelve distinct reviewed articles');
  const sitemap = fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8');
  const hub = fs.readFileSync(path.join(root, 'blog/index.html'), 'utf8');
  const titles = new Set();
  for (const article of articles) {
    const html = fs.readFileSync(path.join(root, 'blog', `${article.slug}.html`), 'utf8');
    assert.equal([...html.matchAll(/<h1\b/g)].length, 1, article.slug);
    assert.ok(html.includes(`rel="canonical" href="${article.url}"`), article.slug);
    assert.ok(sitemap.includes(`<loc>${article.url}</loc>`), article.slug);
    assert.ok(hub.includes(`href="/blog/${article.slug}.html"`), article.slug);
    assert.ok(html.includes('2026-10-08'), article.slug);
    assert.ok(html.includes('class="blog-toc"'), article.slug);
    assert.ok(!titles.has(article.title), article.slug);
    titles.add(article.title);
    const schemas = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(match => JSON.parse(match[1]));
    const schema = schemas.find(value => value['@type'] === 'Article');
    assert.equal(schema.mainEntityOfPage, article.url);
    assert.equal(schema.dateModified, article.dateModified);
    if (article.faq?.length) {
      const faq = schemas.find(value => value['@type'] === 'FAQPage');
      assert.equal(faq.mainEntity.length, article.faq.length);
      assert.deepEqual(faq.mainEntity.map(item => item.acceptedAnswer.text), article.faq.map(item => item.answer));
    }
  }
});

test('top ten editorial ordering and publisher disclosure are visible and consistent', () => {
  const html = fs.readFileSync(path.join(root, 'blog/top-10-osint-tools.html'), 'utf8');
  const list = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(match => JSON.parse(match[1])).find(value => value['@type'] === 'ItemList');
  assert.equal(list.numberOfItems, 10);
  assert.equal(list.itemListElement[2].item.name, 'MyRecon');
  assert.match(html, /publisher|publish.*MyRecon/i);
  assert.match(html, /not an independent|not.*performance ranking|not.*benchmark/i);
  assert.ok(html.indexOf('3. MyRecon') !== -1 || /<h[23][^>]*>3[.)].*?MyRecon/.test(html));
});

test('new article media matches visible content and appears in the sitemap', () => {
  const media = JSON.parse(fs.readFileSync(path.join(root, 'content/blog-media.json')));
  assert.equal(Object.keys(media).length, 12);
  const sitemap = fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8');
  assert.equal([...sitemap.matchAll(/<video:video>/g)].length, 12);
  assert.equal([...sitemap.matchAll(/<image:image>/g)].length, 12);
  for (const [slug, item] of Object.entries(media)) {
    const html = fs.readFileSync(path.join(root, 'blog', `${slug}.html`), 'utf8');
    const schemas = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(match => JSON.parse(match[1]));
    const video = schemas.find(value => value['@type'] === 'VideoObject');
    assert.equal(video.name, item.title);
    assert.equal(video.contentUrl, `${site}/assets/media/blog/${slug}.mp4`);
    assert.ok(sitemap.includes(`<video:content_loc>${video.contentUrl}</video:content_loc>`));
    assert.equal(video.duration, 'PT32S');
    assert.ok(html.includes('preload="none"'));
    assert.ok(!/<video[^>]*\bautoplay\b/.test(html));
    const captions = fs.readFileSync(path.join(root, 'assets/media/blog', `${slug}.vtt`), 'utf8');
    for (const [heading, text] of item.steps) {
      assert.ok(video.transcript.includes(heading) && captions.includes(heading));
      assert.ok(video.transcript.includes(text) && captions.includes(text));
    }
  }
});

test('homepage is identical to its pre-SEO version and tools were not edited', () => {
  const {execFileSync} = require('node:child_process');
  const baseline = execFileSync('git', ['show', '92ff85bb:frontend/index.html'], {cwd:root});
  assert.ok(baseline.equals(fs.readFileSync(path.join(root, 'index.html'))), 'homepage must remain unchanged');
  const changedTools = execFileSync('git', ['diff', 'dbdea313', '--name-only', '--', 'frontend/assets/js', 'frontend/assets/css/styles.css', 'frontend/assets/css/fx.css', 'frontend/deep-search.html', 'frontend/pricing.html', 'backend'], {cwd:path.resolve(root, '..'), encoding:'utf8'});
  assert.equal(changedTools.trim(), '');
});

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
test('pricing page FAQ structured answers match visible questions and answers', () => {
  const html = fs.readFileSync(path.join(root, 'pricing.html'), 'utf8');
  const schemas = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1]));
  const faq = schemas.flatMap(s => s['@graph'] || [s]).find(s => s['@type'] === 'FAQPage');
  assert.ok(faq, 'pricing.html should contain a FAQPage schema');
  for (const q of faq.mainEntity) {
    assert.ok(html.includes(q.name), q.name);
    assert.ok(html.includes(q.acceptedAnswer.text), q.name);
  }
});
test('generated SEO and hub pages expose mobile nav, theme toggle, Deep Search footer link, and non-duplicate breadcrumbs', () => {
  const coreHtml = fs.readFileSync(path.join(root, 'features.html'), 'utf8');
  const coreSchemas = [...coreHtml.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1]));
  const crumbs = coreSchemas.find(s => s['@type'] === 'BreadcrumbList');
  assert.equal(crumbs.itemListElement.length, 2, 'core SEO pages should have a 2-step breadcrumb');
  assert.equal(crumbs.itemListElement[0].item, 'https://www.myrecon.xyz/');
  assert.equal(crumbs.itemListElement[1].item, 'https://www.myrecon.xyz/features');

  for (const rel of ['features.html', 'find/index.html', 'find/instagram-account.html']) {
    const html = fs.readFileSync(path.join(root, rel), 'utf8');
    assert.ok(html.includes('id="themeToggle"'), `${rel} should include #themeToggle`);
    assert.ok(html.includes('id="navToggle"'), `${rel} should include #navToggle`);
    assert.ok(html.includes('id="navLinks"'), `${rel} should include #navLinks`);
    assert.ok(html.includes('href="/deep-search.html"'), `${rel} should link to Deep Search in shared footer`);
  }
});
test('username-search-input shell binds theme and mobile menu idempotently', () => {
  const vm = require('node:vm');
  const scriptSource = fs.readFileSync(path.join(root, 'assets/js/username-search-input.js'), 'utf8');
  const store = new Map([['myrecon-theme', 'dark']]);
  const attrs = new Map([['data-theme', 'light']]);
  const meta = { content: '#f7f7f4' };
  const themeListeners = [];
  const navListeners = [];
  const themeBtn = {
    dataset: {},
    attrs: new Map(),
    setAttribute(k, v) { this.attrs.set(k, v); },
    addEventListener(type, fn) { if (type === 'click') themeListeners.push(fn); },
  };
  let menuOpen = false;
  const navLinks = {
    classList: {
      toggle(cls) { if (cls === 'open') menuOpen = !menuOpen; return menuOpen; },
    },
  };
  const navBtn = {
    dataset: {},
    attrs: new Map(),
    setAttribute(k, v) { this.attrs.set(k, v); },
    addEventListener(type, fn) { if (type === 'click') navListeners.push(fn); },
  };
  const context = {
    window: {
      localStorage: {
        getItem: k => store.get(k) ?? null,
        setItem: (k, v) => store.set(k, v),
      },
    },
    document: {
      readyState: 'complete',
      documentElement: {
        getAttribute: k => attrs.get(k),
        setAttribute: (k, v) => attrs.set(k, v),
      },
      querySelector: sel => (sel === 'meta[name="theme-color"]' ? meta : null),
      getElementById: id => ({ themeToggle: themeBtn, navToggle: navBtn, navLinks }[id] || null),
    },
    HTMLElement: class {},
    customElements: { get: () => true, define: () => {} },
  };
  // Run twice to ensure idempotent binding when multiple scripts share the page
  vm.runInNewContext(scriptSource, context);
  vm.runInNewContext(scriptSource, context);

  assert.equal(attrs.get('data-theme'), 'dark');
  assert.equal(meta.content, '#111111');
  assert.equal(themeListeners.length, 1, 'themeToggle should only bind once');
  assert.equal(navListeners.length, 1, 'navToggle should only bind once');

  themeListeners[0]();
  assert.equal(attrs.get('data-theme'), 'light');
  assert.equal(store.get('myrecon-theme'), 'light');
  assert.equal(meta.content, '#f7f7f4');

  assert.equal(navBtn.attrs.get('aria-expanded'), 'false');
  navListeners[0]();
  assert.equal(menuOpen, true);
  assert.equal(navBtn.attrs.get('aria-expanded'), 'true');
});

test('homepage includes Deep Search tab, full-width tool layout, clean benchmark graph, and 3-question FAQ with dropdown', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const appJs = fs.readFileSync(path.join(root, 'assets/js/app.js'), 'utf8');
  const fxCss = fs.readFileSync(path.join(root, 'assets/css/fx.css'), 'utf8');
  const trustCss = fs.readFileSync(path.join(root, 'assets/css/trust.css'), 'utf8');

  // 1. Deep Search tab in TOOLS and 7-column full-width tool layout
  assert.ok(appJs.includes('deepsearch: {'), 'TOOLS should include deepsearch');
  assert.ok(fxCss.includes('grid-template-columns: repeat(7, minmax(0, 1fr))'), 'fx.css should configure 7 tool tabs');
  assert.ok(trustCss.includes('grid-template-columns:repeat(7,minmax(0,1fr))'), 'trust.css should configure 7 tool tabs');

  // 2. Empty state "Ready when you are" removed
  assert.ok(!appJs.includes('Ready when you are'), 'defaultEmpty should not render Ready when you are box');

  // 3. Benchmark section keeps the main case graph and removes expandable evidence/daily rows
  assert.ok(html.includes('id="usernameCaseGraph"'), 'index.html should keep #usernameCaseGraph');
  assert.ok(!html.includes('class="case-evidence"'), 'index.html should remove .case-evidence rows');
  assert.ok(!html.includes('class="case-daily"'), 'index.html should remove .case-daily section');

  // 4. FAQ shows 3 top-level questions and wraps remaining 5 in .faq-more dropdown
  const faqMatch = html.match(/<div class="faq">([\s\S]*?)<details class="faq-more">/);
  assert.ok(faqMatch, 'index.html should have a .faq-more dropdown inside .faq');
  assert.equal((faqMatch[1].match(/<details>/g) || []).length, 3, 'exactly 3 questions should appear before .faq-more');
  const moreMatch = html.match(/<div class="faq-more-list">([\s\S]*?)<\/div>\s*<\/details>/);
  assert.ok(moreMatch, 'index.html should have .faq-more-list');
  assert.equal((moreMatch[1].match(/<details>/g) || []).length, 5, 'remaining 5 questions should be inside .faq-more-list');
});

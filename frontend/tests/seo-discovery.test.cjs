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
  assert.equal(faq.mainEntity.length, 8, 'FAQPage schema should contain all 8 homepage FAQ questions');
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

test('homepage and key public landing pages pass static SEO checks', () => {
  function auditPage(file) {
    const html = fs.readFileSync(file, 'utf8');
    const checks = [];

    // 1. Viewport
    const vp = html.match(/<meta[^>]*name=["\x27]viewport["\x27][^>]*content=["\x27]([^"\x27]*)["\x27]/i);
    checks.push({ name: 'viewport', pass: !!(vp && (vp[1].includes('width') || vp[1].includes('initial-scale'))) });

    // 2. Title
    const tm = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const title = tm ? tm[1].trim() : '';
    checks.push({ name: 'document-title', pass: title.length >= 10 && title.length <= 65 });

    // 3. Meta description
    const dm = html.match(/<meta[^>]*name=["\x27]description["\x27][^>]*content="([^"]*)"/i)
      || html.match(/<meta[^>]*name=["\x27]description["\x27][^>]*content='([^']*)'/i)
      || html.match(/<meta[^>]*content="([^"]*)"[^>]*name=["\x27]description["\x27]/i)
      || html.match(/<meta[^>]*content='([^']*)'[^>]*name=["\x27]description["\x27]/i);
    const desc = dm ? dm[1].trim() : '';
    checks.push({ name: 'meta-description', pass: desc.length >= 50 && desc.length <= 165 });

    // 4. Crawlable anchors
    const anchors = [...html.matchAll(/<a\b([^>]*)>/gi)];
    let badAnchors = 0;
    for (const a of anchors) {
      const hrefMatch = a[1].match(/href=["\x27]([^"\x27]*)["\x27]/i);
      if (hrefMatch && hrefMatch[1] === '#') badAnchors++;
    }
    checks.push({ name: 'crawlable-anchors', pass: badAnchors === 0 });

    // 5. Descriptive link text
    let genericTextAnchors = 0;
    const genericTerms = ['click here', 'here', 'link'];
    const fullAnchors = [...html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)];
    for (const a of fullAnchors) {
      const rawText = a[2].replace(/<[^>]*>/g, '').trim().toLowerCase();
      const ariaLabel = a[1].match(/aria-label=["\x27]([^"\x27]*)["\x27]/i);
      if (!ariaLabel && genericTerms.includes(rawText)) genericTextAnchors++;
    }
    checks.push({ name: 'link-text', pass: genericTextAnchors === 0 });

    // 6. Meta robots
    const rm = html.match(/<meta[^>]*name=["\x27]robots["\x27][^>]*content=["\x27]([^"\x27]*)["\x27]/i);
    const isNoindex = rm && rm[1].toLowerCase().includes('noindex');
    checks.push({ name: 'is-crawlable', pass: !isNoindex });

    // 7. Canonical
    const cm = html.match(/<link[^>]*rel=["\x27]canonical["\x27][^>]*href=["\x27]([^"\x27]*)["\x27]/i)
      || html.match(/<link[^>]*href=["\x27]([^"\x27]*)["\x27][^>]*rel=["\x27]canonical["\x27]/i);
    checks.push({ name: 'canonical', pass: !!(cm && cm[1].startsWith('https://www.myrecon.xyz')) });

    // 8. Image alt
    const imgs = [...html.matchAll(/<img\b([^>]*)>/gi)];
    let missingAlt = 0;
    for (const img of imgs) {
      if (!/\balt=["\x27]/.test(img[1])) missingAlt++;
    }
    checks.push({ name: 'image-alt', pass: missingAlt === 0 });

    // 9. Heading structure (H1 exactly 1, no hierarchy jumps)
    const h1s = [...html.matchAll(/<h1\b[^>]*>/gi)];
    const headings = [...html.matchAll(/<(h[1-6])\b/gi)].map(m => parseInt(m[1][1]));
    let headingJump = false;
    let prev = 0;
    for (const lvl of headings) {
      if (prev === 0 && lvl !== 1) headingJump = true;
      if (lvl > prev + 1 && prev !== 0) headingJump = true;
      prev = lvl;
    }
    checks.push({ name: 'heading-structure', pass: h1s.length === 1 && !headingJump });

    // 10. Structured data validity
    const jsonLdRegex = /<script\b[^>]*type=["\x27]application\/ld\+json["\x27][^>]*>([\s\S]*?)<\/script>/gi;
    let jMatch;
    let jsonLdValid = true;
    let jsonLdCount = 0;
    while ((jMatch = jsonLdRegex.exec(html)) !== null) {
      jsonLdCount++;
      try {
        JSON.parse(jMatch[1]);
      } catch (e) {
        jsonLdValid = false;
      }
    }
    checks.push({ name: 'structured-data', pass: jsonLdCount > 0 && jsonLdValid });

    const passed = checks.filter(c => c.pass).length;
    const score = Math.round((passed / checks.length) * 100);
    return { score, failed: checks.filter(c => !c.pass) };
  }

  const pagesToTest = [
    'index.html',
    'username-checker.html',
    'free-osint-tool.html',
    'digital-footprint-checker.html',
    'reverse-username-lookup.html',
    'deep-search.html',
    'app.html',
    'is-myrecon-legit.html',
    'vs/index.html',
    'features.html',
    'pricing.html',
    'about.html',
    'services.html',
    'guides/index.html',
    'blog/index.html',
    'breaches/index.html'
  ];

  for (const page of pagesToTest) {
    const res = auditPage(path.join(root, page));
    assert.ok(res.score >= 95, `${page} should score at least 95/100, got ${res.score}/100. Failed: ${JSON.stringify(res.failed)}`);
    assert.equal(res.score, 100, `${page} should pass every static SEO check`);
  }
});

test('free OSINT tool landing page exposes valid local links and matching FAQ schema', () => {
  const html = fs.readFileSync(path.join(root, 'free-osint-tool.html'), 'utf8');
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
  assert.ok(fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8').includes('https://www.myrecon.xyz/free-osint-tool.html'));
});

test('digital footprint checker landing page exposes valid local links and matching FAQ schema', () => {
  const html = fs.readFileSync(path.join(root, 'digital-footprint-checker.html'), 'utf8');
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
  assert.ok(fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8').includes('https://www.myrecon.xyz/digital-footprint-checker.html'));
});

test('reverse username lookup landing page exposes valid local links and matching FAQ schema', () => {
  const html = fs.readFileSync(path.join(root, 'reverse-username-lookup.html'), 'utf8');
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
  assert.ok(fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8').includes('https://www.myrecon.xyz/reverse-username-lookup.html'));
});

test('boost, browser, and goal pages are standalone discovery pages with canonical references', () => {
  for (const page of ['boost.html', 'browser.html', 'goal.html']) {
    const html = fs.readFileSync(path.join(root, page), 'utf8');
    assert.ok(html.includes(`canonical" href="https://www.myrecon.xyz/${page}"`));
    assert.ok(!html.includes('http-equiv="refresh"'));
  }
});

test('homepage structured data contains valid Organization, WebApplication, and no fake aggregateRating', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  assert.ok(!html.includes('aggregateRating'), 'homepage should not include unbacked aggregateRating schema');
  assert.ok(html.includes('"@type":"Organization"'), 'homepage must include Organization schema');
  assert.ok(html.includes('"@type":"WebApplication"'), 'homepage must include WebApplication schema');
  assert.ok(html.includes('https://www.myrecon.xyz/founder.html'), 'founder link must be present in Organization schema');
});

test('no public pages contain unbacked aggregateRating schema', () => {
  const pages = [
    'index.html',
    'username-checker.html',
    'free-osint-tool.html',
    'digital-footprint-checker.html',
    'reverse-username-lookup.html',
    'deep-search.html',
    'app.html',
    'is-myrecon-legit.html',
    'vs/index.html',
    'features.html',
    'pricing.html',
    'about.html',
    'services.html',
    'guides/index.html',
    'blog/index.html',
    'breaches/index.html'
  ];
  for (const page of pages) {
    const html = fs.readFileSync(path.join(root, page), 'utf8');
    assert.ok(!html.includes('aggregateRating'), `${page} should not contain unbacked aggregateRating`);
  }
});

function walkAllHtml(dir, out = []) {
  const skipDirs = new Set(['node_modules', 'content', 'scripts', 'tests', 'assets', 'data', '.well-known']);
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.') || skipDirs.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkAllHtml(full, out);
    else if (entry.isFile() && entry.name.endsWith('.html')) out.push(full);
  }
  return out;
}

test('all indexable public HTML pages across the entire site pass static SEO checks', () => {
  const skipRedirect = new Set(['404.html', 'ops.html']);
  const allFiles = walkAllHtml(root);
  let checkedCount = 0;

  for (const file of allFiles) {
    const rel = path.relative(root, file).replace(/\\/g, '/');
    if (skipRedirect.has(rel)) continue;
    const html = fs.readFileSync(file, 'utf8');
    if (isNoindex(html)) continue;
    checkedCount++;

    const vp = html.match(/<meta[^>]*name=["\x27]viewport["\x27][^>]*content=["\x27]([^"\x27]*)["\x27]/i);
    assert.ok(vp && (vp[1].includes('width') || vp[1].includes('initial-scale')), `${rel}: missing viewport`);

    const tm = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const title = tm ? tm[1].trim() : '';
    assert.ok(title.length >= 10 && title.length <= 75, `${rel}: title length ${title.length} out of bounds`);

    const dm = html.match(/<meta[^>]*name=["\x27]description["\x27][^>]*content="([^"]*)"/i)
      || html.match(/<meta[^>]*name=["\x27]description["\x27][^>]*content='([^']*)'/i)
      || html.match(/<meta[^>]*content="([^"]*)"[^>]*name=["\x27]description["\x27]/i);
    const desc = dm ? dm[1].trim() : '';
    assert.ok(desc.length >= 50 && desc.length <= 170, `${rel}: description length ${desc.length} out of bounds`);

    const anchors = [...html.matchAll(/<a\b([^>]*)>/gi)];
    for (const a of anchors) {
      const hrefMatch = a[1].match(/href=["\x27]([^"\x27]*)["\x27]/i);
      assert.notEqual(hrefMatch && hrefMatch[1], '#', `${rel}: non-crawlable href="#" anchor`);
    }

    const cm = html.match(/<link[^>]*rel=["\x27]canonical["\x27][^>]*href=["\x27]([^"\x27]*)["\x27]/i)
      || html.match(/<link[^>]*href=["\x27]([^"\x27]*)["\x27][^>]*rel=["\x27]canonical["\x27]/i);
    assert.ok(cm && cm[1].startsWith('https://www.myrecon.xyz'), `${rel}: missing or non-myrecon canonical`);

    const imgs = [...html.matchAll(/<img\b([^>]*)>/gi)];
    for (const img of imgs) {
      assert.ok(/\balt=["\x27]/.test(img[1]), `${rel}: image missing alt attribute: ${img[0]}`);
    }

    const h1s = [...html.matchAll(/<h1\b[^>]*>/gi)];
    assert.equal(h1s.length, 1, `${rel}: expected exactly 1 H1, got ${h1s.length}`);

    const headings = [...html.matchAll(/<(h[1-6])\b/gi)].map(m => parseInt(m[1][1], 10));
    let prev = 0;
    for (const lvl of headings) {
      assert.ok(!(prev === 0 && lvl !== 1), `${rel}: first heading is H${lvl} instead of H1`);
      assert.ok(!(prev !== 0 && lvl > prev + 1), `${rel}: heading hierarchy jump H${prev} -> H${lvl}`);
      prev = lvl;
    }

    const jsonLds = [...html.matchAll(/<script\b[^>]*type=["\x27]application\/ld\+json["\x27][^>]*>([\s\S]*?)<\/script>/gi)];
    assert.ok(jsonLds.length > 0, `${rel}: missing JSON-LD structured data`);
    for (const j of jsonLds) {
      assert.doesNotThrow(() => JSON.parse(j[1]), `${rel}: invalid JSON-LD`);
    }
  }

  const canonicalCount = [...fs.readFileSync(path.join(root, "sitemap.xml"), "utf8").matchAll(/<loc>/g)].length;
  assert.ok(checkedCount >= canonicalCount, `Expected to audit every canonical public page, audited ${checkedCount} for ${canonicalCount} canonicals`);
});

test('every indexable page is in sitemap.xml with valid hints and zero orphan or single-inbound pages', () => {
  const skipRedirect = new Set(['404.html', 'ops.html']);
  const allFiles = walkAllHtml(root);
  const sitemapXml = fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8');
  const inbound = new Map();
  const aliasToCanon = new Map();

  for (const file of allFiles) {
    const rel = path.relative(root, file).replace(/\\/g, '/');
    if (skipRedirect.has(rel)) continue;
    const html = fs.readFileSync(file, 'utf8');
    if (isNoindex(html)) continue;

    let urlPath = '/' + rel;
    if (urlPath === '/index.html') urlPath = '/';
    else if (urlPath.endsWith('/index.html')) urlPath = urlPath.slice(0, -10);

    const cm = html.match(/<link[^>]*rel=["\x27]canonical["\x27][^>]*href=["\x27]https:\/\/www\.myrecon\.xyz([^"\x27]*)["\x27]/i);
    const canon = cm ? (cm[1] || '/') : urlPath;

    assert.ok(sitemapXml.includes(`<loc>https://www.myrecon.xyz${canon}</loc>`), `${rel} (${canon}) missing from sitemap.xml`);
    inbound.set(canon, new Set());
    aliasToCanon.set(urlPath, canon);
    aliasToCanon.set(urlPath.replace(/\.html$/, ''), canon);
    aliasToCanon.set(canon, canon);
  }

  for (const file of allFiles) {
    const rel = path.relative(root, file).replace(/\\/g, '/');
    if (skipRedirect.has(rel)) continue;
    const html = fs.readFileSync(file, 'utf8');
    const srcKey = '/' + rel;
    for (const [, href] of html.matchAll(/href=["\x27](\/[^"\x27#?]*)(?:[?#][^"\x27]*)?["\x27]/gi)) {
      if (href.startsWith('/assets/') || href.startsWith('/data/') || href === '/site.webmanifest') continue;
      const targetRel = href.slice(1);
      const exists = href === '/' || [targetRel, `${targetRel}.html`, path.join(targetRel, 'index.html')].some(p => fs.existsSync(path.join(root, p)));
      assert.ok(exists, `Broken internal link on ${rel}: ${href}`);

      const targetCanon = aliasToCanon.get(href) || aliasToCanon.get(href.replace(/\.html$/, ''));
      if (targetCanon && inbound.has(targetCanon) && aliasToCanon.get(srcKey) !== targetCanon) {
        inbound.get(targetCanon).add(srcKey);
      }
    }
  }

  const orphans = [...inbound.entries()].filter(([, srcs]) => srcs.size === 0).map(([k]) => k);
  const singleInbound = [...inbound.entries()].filter(([, srcs]) => srcs.size === 1).map(([k]) => k);
  assert.deepEqual(orphans, [], `Found orphan indexable pages with 0 inbound links: ${orphans.join(', ')}`);
  assert.deepEqual(singleInbound, [], `Found weakly linked pages with only 1 inbound link: ${singleInbound.join(', ')}`);

  // Validate optional sitemap hints; their numeric value is not a ranking signal.
  for (const section of ['/find/', '/privacy/', '/guides/', '/vs/', '/blog/', '/breaches/']) {
    const regex = new RegExp(`<loc>https://www\\.myrecon\\.xyz(${section}[^<]*)</loc>\\s*<lastmod>[^<]+</lastmod>\\s*<changefreq>([^<]+)</changefreq>\\s*<priority>([^<]+)</priority>`, 'g');
    let m;
    let count = 0;
    while ((m = regex.exec(sitemapXml)) !== null) {
      count++;
      const prio = parseFloat(m[3]);
      assert.ok(prio >= 0 && prio <= 1, `Sitemap entry ${m[1]} has invalid priority ${prio}`);
    }
    assert.ok(count > 0, `Expected sitemap entries for ${section}`);
  }
});

test('boost, browser, and goal routes and redirect pages are configured across HTML and the Vercel hosting configuration', () => {
  const vercel = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json'), 'utf8'));
  const sitemapXml = fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8');

  const expectedPages = [
    { alias: 'boost', keyword: 'boost osint' },
    { alias: 'browser', keyword: 'browser osint tool' },
    { alias: 'goal', keyword: 'digital footprint goal' },
  ];

  for (const { alias, keyword } of expectedPages) {
    const html = fs.readFileSync(path.join(root, `${alias}.html`), 'utf8');
    assert.ok(html.includes(`canonical" href="https://www.myrecon.xyz/${alias}.html"`), `${alias}.html canonical mismatch`);
    assert.ok(!html.includes('refresh" content="0; url='), `${alias}.html should not have meta refresh`);
    assert.ok(html.toLowerCase().includes(keyword), `${alias}.html should include keyword "${keyword}"`);
    assert.ok(sitemapXml.includes(`/${alias}.html`), `${alias}.html must be in sitemap.xml`);

    const vercelRewrite = vercel.rewrites.find(r => r.source === `/${alias}`);
    assert.ok(vercelRewrite && vercelRewrite.destination === `/${alias}.html`, `vercel.json missing rewrite for /${alias}`);
  }

  // Verify osint-cheat-sheet.html FAQPage schema matches visible FAQ items
  const csHtml = fs.readFileSync(path.join(root, 'osint-cheat-sheet.html'), 'utf8');
  const csSchemas = [...csHtml.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1]));
  const csFaq = csSchemas.flatMap(s => s['@graph'] || [s]).find(s => s['@type'] === 'FAQPage');
  assert.ok(csFaq && csFaq.mainEntity.length === 3, 'osint-cheat-sheet.html should have 3 FAQ items');
  for (const q of csFaq.mainEntity) {
    assert.ok(csHtml.includes(`<summary>${q.name}</summary>`), `osint-cheat-sheet.html missing visible summary for: ${q.name}`);
  }
});

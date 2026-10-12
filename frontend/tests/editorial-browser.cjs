const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../output/editorial');
fs.mkdirSync(output, { recursive: true });
const routes = ['/guides/protect-researcher-notes', '/guides/public-profile-evidence-logging', '/guides/verify-osint-account-matches', '/guides/account-enumeration-false-positives', '/about.html', '/guides/brand-impersonation-monitoring', '/find/github-profile', '/find/instagram-account', '/find/discord-user', '/vs/sherlock', '/privacy/', '/find/', '/guides/', '/vs/'];
const server = http.createServer((req, res) => {
  const route = new URL(req.url, 'http://localhost').pathname;
  let file = path.join(root, route.slice(1));
  if (route.endsWith('/')) file = path.join(file, 'index.html');
  else if (!path.extname(file)) file += '.html';
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) { res.writeHead(404).end(); return; }
  const type = {'.html':'text/html', '.js':'application/javascript', '.css':'text/css', '.svg':'image/svg+xml', '.png':'image/png'}[path.extname(file)];
  if (type) res.setHeader('Content-Type', type);
  res.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: {width, height: 900} });
      await page.route(/googletagmanager\.com|google-analytics\.com|analytics\.google\.com/, route => route.abort());
      for (const route of routes) {
        const response = await page.goto(`${process.env.MYRECON_EDITORIAL_URL || `http://127.0.0.1:${server.address().port}`}${route}`, {waitUntil: 'domcontentloaded'});
        assert.equal(response.status(), 200, route);
        await page.evaluate(() => document.fonts.ready);
        assert.equal(await page.locator('h1').count(), 1, route);
        if (await page.locator('.editorial-nav').count()) {
          const layout = await page.evaluate(() => ({nav: document.querySelector('.editorial-nav').getBoundingClientRect().bottom, title: document.querySelector('h1').getBoundingClientRect().top}));
          assert.ok(layout.title >= layout.nav, `navigation covers heading ${width} ${route}`);
          assert.ok(layout.nav < 180, `oversized navigation ${width} ${route}`);
        }
        assert.equal(await page.locator('[data-content-app-promo]').count(), 0, route);
        const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 2).slice(0,5).map(e => `${e.tagName}.${e.className}: ${e.getBoundingClientRect().right}`));
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), `horizontal overflow ${width} ${route}: ${overflow}`);
        for (const image of await page.locator('main img').all()) {
          await image.scrollIntoViewIfNeeded();
          await image.evaluate(img => img.complete ? null : new Promise(resolve => { img.onload = resolve; img.onerror = resolve; }));
          assert.ok(await image.evaluate(img => img.naturalWidth > 0), `image ${route}`);
        }
        if (route.includes('protect-researcher') || route.includes('github-profile') || route === '/privacy/') {
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.screenshot({path:path.join(output, `${route.replace(/\W/g,'-')}-${width}.png`), fullPage:true});
        }
      }
      await page.close();
    }
    console.log(`Verified ${routes.length} editorial routes at mobile and desktop widths`);
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });

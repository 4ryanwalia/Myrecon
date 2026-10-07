const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { readArticles } = require('../scripts/build-blog');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../output/osint-release');
const articles = readArticles().filter(article => article.datePublished === '2026-10-08');
const routes = ['/', '/blog/', '/username-checker.html', ...articles.map(article => `/blog/${article.slug}.html`)];
const base = process.env.MYRECON_PUBLICATION_URL;
fs.mkdirSync(output, {recursive:true});
const server = http.createServer((req, res) => {
  const route = new URL(req.url, 'http://localhost').pathname;
  let file = path.resolve(root, `.${route}`);
  if (route.endsWith('/')) file = path.join(file, 'index.html');
  else if (!path.extname(file)) file += '.html';
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) {res.writeHead(404).end(); return;}
  const type = {'.html':'text/html', '.js':'application/javascript', '.css':'text/css', '.svg':'image/svg+xml', '.png':'image/png', '.json':'application/json'}[path.extname(file)];
  if (type) res.setHeader('Content-Type', type);
  res.end(fs.readFileSync(file));
});
(async () => {
  if (!base) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    for (const width of [375, 1280]) {
      const page = await browser.newPage({viewport:{width,height:900}});
      await page.route(/googletagmanager\.com|google-analytics\.com|analytics\.google\.com|googlesyndication\.com|doubleclick\.net/, route => route.abort());
      for (const route of routes) {
        const response = await page.goto(`${base || `http://127.0.0.1:${server.address().port}`}${route}`, {waitUntil:'domcontentloaded'});
        assert.equal(response.status(), 200, route);
        await page.evaluate(() => document.fonts.ready);
        assert.equal(await page.locator('h1').count(), 1, route);
        assert.ok(await page.locator('h1').isVisible(), route);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), `horizontal overflow ${width} ${route}`);
        const schemas = await page.locator('script[type="application/ld+json"]').allTextContents();
        schemas.forEach(schema => JSON.parse(schema));
        if (route.startsWith('/blog/') && route !== '/blog/') {
          const text = await page.locator('main').innerText();
          assert.ok(text.indexOf('Quick answer') < text.indexOf('On this page'), `answer must precede contents ${route}`);
          for (const link of await page.locator('.blog-toc a').all()) {
            const href = await link.getAttribute('href');
            assert.equal(await page.locator(href).count(), 1, `${route} ${href}`);
          }
          for (const table of await page.locator('main table').all()) {
            assert.equal(await table.locator('caption').count(), 1, `${route}: accessible table caption`);
            assert.ok(await table.locator('th').count() > 0, `${route}: table headers`);
          }
        }
        if (route === '/blog/top-10-osint-tools.html') {
          assert.ok((await page.locator('main').innerText()).includes('3. MyRecon'));
          await page.screenshot({path:path.join(output, `top-10-osint-tools-${base ? 'live' : 'local'}-${width}-viewport.png`)});
          await page.screenshot({path:path.join(output, `top-10-osint-tools-${base ? 'live' : 'local'}-${width}.png`),fullPage:true});
        }
      }
      await page.close();
    }
    console.log(`Verified ${routes.length} public routes at 375px and 1280px: headings, schema, answer order, contents links, tables and overflow`);
  } finally {await browser.close(); if (!base) server.close();}
})().catch(error => {console.error(error); server.close(); process.exitCode=1;});

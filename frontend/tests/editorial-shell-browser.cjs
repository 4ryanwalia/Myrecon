const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req, res) => {
  const file = path.join(root, new URL(req.url, 'http://localhost').pathname);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
  res.setHeader('Content-Type', {'.html':'text/html', '.js':'application/javascript', '.css':'text/css', '.svg':'image/svg+xml'}[path.extname(file)] || 'application/octet-stream');
  res.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({viewport:{width, height:900}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route(/googletagmanager\.com|google-analytics\.com|analytics\.google\.com/, route => route.abort());
      const liveOrigin = process.env.MYRECON_EDITORIAL_URL;
      const origin = liveOrigin || `http://127.0.0.1:${server.address().port}`;
      const lookups = ['github-profile', 'instagram-account', 'discord-user'].map(slug => `/find/${slug}${liveOrigin ? '' : '.html'}`);
      const routes = ['/blog/best-free-osint-tools-for-investigators.html', '/blog/best-username-search-tools.html', ...lookups,
        liveOrigin ? '/guides/' : '/guides/index.html'];
      for (const route of routes) {
        const response = await page.goto(origin + route + '?mr_benchmark=1', { waitUntil: 'domcontentloaded' });
        assert.equal(response.status(), 200);
        assert.equal(await page.locator('script[src*="/app."]').count(), 0);
        assert.equal(await page.locator('script[src*="editorial-shell"]').count(), 1);
        const before = await page.locator('html').getAttribute('data-theme');
        await page.locator('#themeToggle').click();
        assert.notEqual(await page.locator('html').getAttribute('data-theme'), before);
        await page.reload();
        assert.notEqual(await page.locator('html').getAttribute('data-theme'), before);
        if (width === 390) {
          assert.equal(await page.locator('#navLinks').isVisible(), false);
          const layout = await page.evaluate(() => {
            const header = document.querySelector('header.nav').getBoundingClientRect();
            const content = document.querySelector('main .seo-breadcrumb, main h1').getBoundingClientRect();
            const toggle = document.getElementById('navToggle').getBoundingClientRect();
            return { headerBottom: header.bottom, contentTop: content.top, toggleBottom: toggle.bottom };
          });
          assert.ok(layout.headerBottom <= layout.contentTop + 1, `${route} header overlaps content`);
          assert.ok(layout.toggleBottom <= layout.headerBottom + 1, `${route} menu toggle is outside the header`);
          await page.locator('#navToggle').click();
          assert.equal(await page.locator('#navToggle').getAttribute('aria-expanded'), 'true');
          assert.equal(await page.locator('#navLinks').isVisible(), true);
          await page.keyboard.press('Escape');
          assert.equal(await page.locator('#navToggle').getAttribute('aria-expanded'), 'false');
          assert.equal(await page.locator('#navLinks').isVisible(), false);
          assert.equal(await page.locator('#navToggle').evaluate(node => node === document.activeElement), true);
        } else {
          assert.equal(await page.locator('#navLinks').isVisible(), true);
          assert.equal(await page.locator('#navToggle').isVisible(), false);
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
        if (route.startsWith('/blog/')) assert.ok(await page.locator('main a[href^="/#tool"], main a[href="/free-osint-tool.html"]').count());
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Article navigation, saved theme, mobile layout and tool CTAs passed at both widths.');
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });

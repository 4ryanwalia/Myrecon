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
      for (const slug of ['top-10-osint-tools', 'best-username-search-tools']) {
        const response = await page.goto(`${process.env.MYRECON_EDITORIAL_URL || `http://127.0.0.1:${server.address().port}`}/blog/${slug}.html`);
        assert.equal(response.status(), 200);
        assert.equal(await page.locator('script[src*="/app."]').count(), 0);
        assert.equal(await page.locator('script[src*="editorial-shell"]').count(), 1);
        const before = await page.locator('html').getAttribute('data-theme');
        await page.locator('#themeToggle').click();
        assert.notEqual(await page.locator('html').getAttribute('data-theme'), before);
        await page.reload();
        assert.notEqual(await page.locator('html').getAttribute('data-theme'), before);
        if (width === 390) {
          await page.locator('#navToggle').click();
          assert.equal(await page.locator('#navToggle').getAttribute('aria-expanded'), 'true');
          await page.keyboard.press('Escape');
          assert.equal(await page.locator('#navToggle').getAttribute('aria-expanded'), 'false');
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
        assert.ok(await page.locator('main a[href="/#tool"]').count());
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Article navigation, saved theme, mobile layout and tool CTAs passed at both widths.');
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });

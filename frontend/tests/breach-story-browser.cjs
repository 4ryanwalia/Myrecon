/* Local article journeys using fixture responses, with no real email lookup. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../output/breach-story');
fs.mkdirSync(output, { recursive: true });
let state = 'found';
let calls = 0;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/api/breach-check') {
    let body = '';
    req.on('data', part => body += part);
    req.on('end', () => {
      calls++;
      const data = JSON.parse(body);
      assert.equal(data.email, 'fixture@example.com');
      assert.equal(data.targets.length, 1);
      assert.ok(data.targets[0].name);
      res.setHeader('Content-Type', 'application/json');
      if (state === 'http-error') { res.statusCode = 503; return res.end('{}'); }
      res.end(JSON.stringify({ state, message: state === 'found' ? 'Your email appears in this breach\'s records.' : 'Selected incident: ' + state }));
    });
    return;
  }
  if (pathname === '/assets/js/config.js') {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end('window.MYRECON_API_BASE=location.origin;\n' + fs.readFileSync(path.join(root, 'assets/js/config.js'), 'utf8'));
  }
  let file = path.resolve(root, '.' + pathname);
  if (!file.startsWith(root + path.sep)) { res.statusCode = 403; return res.end(); }
  if (pathname.endsWith('/')) file = path.join(file, 'index.html');
  try {
    res.setHeader('Content-Type', ({'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json'})[path.extname(file)] || 'application/octet-stream');
    res.end(fs.readFileSync(file));
  } catch (_) { res.statusCode = 404; res.end(); }
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: {width, height: 900} });
      await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      for (const article of ['advanceautoparts', 'case-files/adobe-2013']) {
        await page.goto(base + '/breaches/' + article + '.html');
        for (const id of ['story','how','motive','outcome']) assert.equal(await page.locator('#' + id).count(), 1);
        assert.equal(await page.locator('script[src*="adsbygoogle"]').count(), 0);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await page.locator('input[type=email]').fill('fixture@example.com');
        for (state of ['found','not_found','unsupported','rate_limited','unavailable','http-error']) {
          await page.locator('[data-breach-check] button').click();
          await page.waitForFunction(() => !document.querySelector('[data-breach-check] button').disabled);
          assert.ok(!(await page.locator('.bx-check-result').innerText()).includes('Unrelated'));
          assert.equal(new URL(page.url()).search, '');
        }
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({path: path.join(output, article.replace('/','-') + '-' + width + '.png'), fullPage: true});
      }
      await page.goto(base + '/breaches/case-files/wannacry-2017.html');
      await page.locator('input[type=email]').fill('fixture@example.com');
      const before = calls;
      await page.locator('[data-breach-check] button').click();
      assert.equal(calls, before);
      assert.equal(await page.locator('.bx-check-result').getAttribute('data-state'), 'unsupported');
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('PASS: desktop/mobile stories, scoped form results, outages, unsupported incident, no URL email or ads, no overflow or JS errors.');
  } finally { await browser.close(); server.close(); }
})().catch(e => { console.error(e); server.close(); process.exitCode = 1; });

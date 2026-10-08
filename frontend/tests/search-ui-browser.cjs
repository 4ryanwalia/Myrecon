/* Focused UI regression check with local fixtures; no provider requests. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const investigations = [];
const report = {
  mode: 'email', status: 'ok', subject: 'fixture@example.com',
  google_public_profiles: { status: 'found', profiles: [{
    display_name: 'Fixture contributor', url: 'https://www.google.com/maps/contrib/123/',
    review_coverage: { status: 'ok', limited: false, total_reported: 1 },
    reviews: [{ name: 'Fixture place', maps_url: 'https://www.google.com/maps/place/fixture/', rating: 4,
      text: 'Fixture review for layout verification.', address: 'Fixture address' }],
  }] }, source_checks: [], notes: [],
};
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/assets/js/account.js') {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end(`window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>({user:{uid:'fixture'},account:{deep_search_enabled:true,standard_scans_unlimited:true}}),onChange:()=>{},load:async()=>{},refreshAccount:async()=>{},authHeaders:async()=>({Authorization:'Bearer fixture'}),friendly:e=>e.message};`);
  }
  if (pathname === '/assets/js/config.js') {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end('window.MYRECON_API_BASE=location.origin;\n' + fs.readFileSync(path.join(root, 'assets/js/config.js'), 'utf8'));
  }
  if (pathname === '/api/investigate/stream') {
    let raw = '';
    req.on('data', chunk => { raw += chunk; });
    req.on('end', () => {
      investigations.push(JSON.parse(raw));
      res.setHeader('Content-Type', 'application/x-ndjson');
      res.end(JSON.stringify({ type: 'complete', data: report }) + '\n');
    });
    return;
  }
  const file = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.statusCode = 404; return res.end();
  }
  res.setHeader('Content-Type', ({ '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'application/javascript; charset=utf-8', '.svg':'image/svg+xml' })[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
async function assertSharedDeepSearch(page) {
  for (const selector of ['#tool', '#toolTabs', '#queryInput', '#runBtn', '#ds']) {
    assert.equal(await page.locator(selector).isVisible(), true, `${selector} stays visible for Deep Search`);
  }
  assert.equal(await page.locator('#tab-deepsearch').getAttribute('aria-selected'), 'true');
  assert.equal(await page.locator('#queryInput').count(), 1);
  assert.equal(await page.locator('#runBtn').count(), 1);
  assert.equal(await page.locator('#dsInput, #dsRun, .ds-back').count(), 0, 'homepage uses one lookup form');
  assert.equal(await page.evaluate(() => {
    const tool = document.querySelector('#tool'), results = document.querySelector('#ds');
    return !!(tool.compareDocumentPosition(results) & Node.DOCUMENT_POSITION_FOLLOWING);
  }), true, 'Deep Search results follow the existing lookup form');
  assert.equal(new URL(page.url()).pathname, '/');
}
async function submitSharedDeepSearch(page, byEnter = false) {
  await page.locator('#queryInput').fill('fixture@example.com');
  const count = investigations.length;
  const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/investigate/stream');
  if (byEnter) await page.locator('#queryInput').press('Enter');
  else await page.locator('#runBtn').click();
  await response;
  await page.locator('#dsExport').waitFor({ state: 'visible' });
  assert.equal(investigations.length, count + 1, 'shared form submits one Deep Search request');
  assert.equal(investigations.at(-1).query, 'fixture@example.com');
  assert.equal(await page.locator('#queryInput').inputValue(), 'fixture@example.com');
  await assertSharedDeepSearch(page);
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ executablePath: process.env.MYRECON_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless:true });
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport:{ width, height:900 } });
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
      await page.goto(base + '/');
      assert.equal(await page.locator('#ds').isVisible(), false);
      assert.equal(await page.locator('#runBtn').evaluate(el => getComputedStyle(el, '::after').content), '"→"');
      await page.locator('#deepSearchEntry').click();
      await page.locator('#ds').waitFor({ state:'visible' });
      await assertSharedDeepSearch(page);
      const theme = await page.locator('html').getAttribute('data-theme');
      await page.locator('#themeToggle').click();
      assert.notEqual(await page.locator('html').getAttribute('data-theme'), theme);
      await submitSharedDeepSearch(page);
      assert.equal(await page.locator('.ds-google-review').count(), 1);
      assert.equal(await page.locator('.ds-google-review').evaluate(el => getComputedStyle(el).borderTopWidth), '1px');
      assert.equal(await page.evaluate(() => {
        const out = document.querySelector('#dsOut'), status = document.querySelector('#dsConsole'), exports = document.querySelector('.ds-export-row');
        return !!(out.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING) && !!(status.compareDocumentPosition(exports) & Node.DOCUMENT_POSITION_FOLLOWING);
      }), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.locator('#tab-username').click();
      await page.locator('#queryInput').waitFor({ state:'visible' });
      assert.equal(await page.locator('#ds').isVisible(), false);
      assert.equal(await page.locator('#toolTabs').isVisible(), true);
      await page.locator('#tab-deepsearch').click();
      await page.locator('#ds').waitFor({ state:'visible' });
      await assertSharedDeepSearch(page);
      await submitSharedDeepSearch(page, true);
      await page.goto(base + '/#deep-search');
      await page.locator('#ds').waitFor({ state:'visible' });
      await assertSharedDeepSearch(page);
      assert.equal(new URL(page.url()).hash, '#deep-search');
      await page.goto(base + '/deep-search.html');
      await page.locator('#dsInput').waitFor({ state:'visible' });
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('PASS: Deep Search shares the existing visible lookup tabs/form for card, tab, button, Enter and deep-link entry; result order, theme, mobile width and standalone page retained.');
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });

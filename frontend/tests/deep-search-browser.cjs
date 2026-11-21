/* Local browser smoke check. Uses account/provider fixtures, never payments. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../output/deep-search');
fs.mkdirSync(output, { recursive: true });
const result = {
  status: 'ok', mode: 'handle', subject: 'nasa', context: null, partial: true,
  activity: [{ platform: 'GitHub', handle: 'nasa', url: 'https://github.com/nasa', display_name: 'NASA', bio: 'Public space science projects.', stats: { Repos: 42 }, declared: [], posts: [{ text: 'Example public comment for browser layout verification.', url: 'https://github.com/nasa/example/issues/1', context: 'nasa/example', date: '2026-09-30' }], source: 'GitHub public API' }],
  owner_links: [{ label: 'Website', url: 'https://www.nasa.gov', declared_on: 'GitHub · nasa' }],
  people: [], accounts: [], identity: null,
  sections: [{ label: 'Instagram footprint', hits: [{ title: 'NASA indexed page', url: 'https://www.instagram.com/nasa/', snippet: 'Indexed public page mentioning the handle.', query: 'site:instagram.com/nasa', engine: 'Fixture', profile: true }] }],
  source_checks: [{ source: 'GitHub', state: 'checked' }, { source: 'Reddit', state: 'unavailable' }],
  notes: ['Reddit could not be checked.', 'Same handles may belong to unrelated people.'],
  plan: [{ text: 'site:instagram.com/nasa', label: 'Social profiles', google: 'https://www.google.com/search?q=site%3Ainstagram.com%2Fnasa', executed: true }], queries_run: 1,
};
let mode = 'guest';
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (/^\/assets\/(?:optimized\/)?js\/account(?:\.[a-f0-9]{12})?\.js$/.test(pathname)) {
    const state = mode === 'guest' ? { user: null, account: null } : { user: { uid: 'fixture-user' }, account: { deep_search_enabled: mode === 'paid' } };
    res.setHeader('Content-Type', 'application/javascript');
    return res.end(`window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>(${JSON.stringify(state)}),onChange:()=>{},refreshAccount:async()=>{},authHeaders:async()=>({Authorization:'Bearer fixture-token'})};`);
  }
  if (/^\/assets\/(?:optimized\/)?js\/config(?:\.[a-f0-9]{12})?\.js$/.test(pathname)) {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end('window.MYRECON_API_BASE=location.origin;\n' + fs.readFileSync(path.join(root, 'assets/js/config.js'), 'utf8'));
  }
  if (pathname === '/api/investigate/stream') {
    assert.equal(req.headers.authorization, 'Bearer fixture-token');
    res.setHeader('Content-Type', 'application/x-ndjson');
    res.write(JSON.stringify({ type: 'progress', percent: 12, detail: 'Checking sources…' }) + '\n');
    res.write(JSON.stringify({ type: 'partial', data: result }) + '\n');
    return setTimeout(() => res.end(JSON.stringify({ type: 'complete', data: result }) + '\n'), 300);
  }
  const file = path.resolve(root, '.' + pathname);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode = 404; return res.end(); }
  const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };
  res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});

(async () => {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ executablePath: process.env.MYRECON_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    const benchmarkRequests = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/data/username-benchmark.json') benchmarkRequests.push(request.url());
    });
    await page.route('**/*', (route) => route.request().url().startsWith(base) ? route.continue() : route.abort());
    await page.goto(base + '/index.html');
    await page.locator('.case-graph-row').first().waitFor();
    assert.equal(await page.locator('.case-graph-row').count(), 3);
    assert.deepEqual(await page.locator('.case-graph-total strong').allTextContents(), ['12', '18', '35']);
    assert.deepEqual(await page.locator('.case-count-falsePositives').allTextContents(), ['0 observed false positives', '2 observed false positives', '9 observed false positives']);
    await page.locator('#usernameCaseScope').selectOption('shared');
    assert.deepEqual(await page.locator('.case-graph-total strong').allTextContents(), ['8', '11', '10']);
    await page.locator('#usernameCaseScope').selectOption('full');
    assert.deepEqual(benchmarkRequests, [], 'both chart views should use the embedded measurements');
    assert.equal(await page.locator('#tab-deepsearch').count(), 1);
    assert.equal(await page.locator('.quick-link').count(), 0);
    assert.equal(await page.locator('.home-resource-list > a').count(), 3);
    assert.equal(await page.locator('.faq-more').evaluate(el => el.open), false);
    await page.screenshot({ path: path.join(output, 'homepage-dark.png'), fullPage: true });
    await page.locator('#themeToggle').click();
    await page.screenshot({ path: path.join(output, 'homepage-light.png'), fullPage: true });
    for (const width of [375, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'homepage overflow at ' + width);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'homepage-mobile.png'), fullPage: true });
    await page.locator('#tab-deepsearch').click();
    await page.getByRole('heading', { name: 'Run a guest investigation' }).waitFor();
    assert.equal(await page.locator('#runBtn').isEnabled(), true);
    assert.equal(await page.locator('#dsPreview').isVisible(), false);
    await page.screenshot({ path: path.join(output, 'guest-preview-mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1280, height: 900 });
    for (mode of ['guest', 'free', 'paid']) {
      await page.goto(base + '/deep-search.html');
      const accessHeading = { guest: 'Run a guest investigation', free: 'Deep Search requires', paid: 'Deep Search is ready' }[mode];
      await page.locator('#dsAccessTitle').filter({ hasText: accessHeading }).waitFor();
      assert.equal(await page.locator('#dsRun').isDisabled(), mode === 'free');
      assert.equal(await page.locator('#dsPreview').isVisible(), mode === 'free');
      assert.equal(await page.locator('#dsUpgrade').isVisible(), mode === 'free');
      if (mode === 'free') assert.equal(await page.locator('#dsUpgrade').getAttribute('href'), '/pricing');
      if (mode === 'guest') {
        await page.screenshot({ path: path.join(output, 'guest-preview-desktop.png'), fullPage: true });
        for (const width of [375, 390, 768]) {
          await page.setViewportSize({ width, height: 844 });
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'guest preview overflow at ' + width);
        }
        await page.setViewportSize({ width: 1280, height: 900 });
      }
    }
    await page.locator('#dsInput').fill('nasa');
    await page.locator('#dsRun').click();
    await page.waitForFunction(() => document.querySelector('#dsStatus').textContent.includes('Complete with source limits'));
    assert.equal(await page.locator('#dsExport').isVisible(), true);
    assert.equal(await page.getByText('Links declared by account owners', { exact: true }).isVisible(), true);
    await page.screenshot({ path: path.join(output, 'desktop-dark.png'), fullPage: true });
    await page.locator('#themeToggle').click();
    await page.screenshot({ path: path.join(output, 'desktop-light.png'), fullPage: true });
    for (const width of [375, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'horizontal overflow at ' + width);
    }
    await page.screenshot({ path: path.join(output, 'tablet-light.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#themeToggle').click();
    await page.screenshot({ path: path.join(output, 'mobile-dark.png'), fullPage: true });
    const originalPage = page.locator('.ds-result-action a[href="https://www.instagram.com/nasa/"]');
    assert.equal(await originalPage.isVisible(), true);
    const download = page.waitForEvent('download');
    await page.locator('#dsExport').click();
    const report = await download;
    assert.equal(report.suggestedFilename(), 'myrecon-deep-search.json');
    assert.deepEqual(JSON.parse(fs.readFileSync(await report.path(), 'utf8')).plan, result.plan);
    assert.deepEqual(errors, []);
    console.log('Browser checks passed for the homepage chart, guest/free/paid access, upgrade link, streamed results, themes, 375/390/768px widths and report download.');
    console.log('Screenshots: ' + output);
  } finally { await browser.close(); server.close(); }
})().catch((error) => { console.error(error); server.close(); process.exitCode = 1; });

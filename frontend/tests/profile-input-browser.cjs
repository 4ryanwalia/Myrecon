/* Local guest access journey. Account and API fixtures prevent provider calls. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
let signedIn = false;
const scans = [];
let holdStream = false;
let pendingStream = null;
const fixtureProfiles = ['First', 'Second', 'Third', 'Fourth', 'Fifth'].map(platform => ({
  platform, url: `https://${platform.toLowerCase()}.example/fixture`, category: 'profile', confidence: 'high', exists: true,
}));
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const json = (value) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(value)); };
  if ((/^\/assets\/(?:optimized\/)?js\/account(?:\.[a-f0-9]{12})?\.js$/).test(pathname)) {
    res.setHeader('Content-Type', 'application/javascript');
    const state = { user: signedIn ? { uid: 'fixture-user', email: 'fixture@example.com' } : null,
      account: signedIn ? { standard_scans_left: 5, standard_scans_unlimited: false } : null };
    return res.end(`(() => {
      const state = ${JSON.stringify(state)};
      const listeners = [];
      window.fixtureSignIns = 0;
      window.fixtureAccountLoads = 0;
      window.MyReconAccount = {
        enabled: true, ready: Promise.resolve(), state: () => state,
        onChange: callback => { listeners.push(callback); }, refreshAccount: async () => {},
        load: () => { window.fixtureAccountLoads++; return Promise.resolve(); },
        authHeaders: async () => state.user ? { Authorization: 'Bearer fixture-token' } : {},
        signIn: async () => {
          window.fixtureSignIns++;
          state.user = { uid: 'fixture-user', email: 'fixture@example.com' };
          state.account = { standard_scans_left: 5, standard_scans_unlimited: false };
          listeners.forEach(callback => callback(state));
        },
        friendly: error => error.message
      };
    })();`);
  }
  if ((/^\/assets\/(?:optimized\/)?js\/config(?:\.[a-f0-9]{12})?\.js$/).test(pathname)) {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end('window.MYRECON_API_BASE=location.origin;\n' + fs.readFileSync(path.join(root, 'assets/js/config.js'), 'utf8'));
  }
  if (pathname.startsWith('/api/username')) {
    let raw = '';
    req.on('data', chunk => { raw += chunk; });
    req.on('end', () => {
      const body = JSON.parse(raw);
      scans.push({ path: pathname, body, authorization: req.headers.authorization });
      const data = { status: 'ok', query: body, summary: { total: 5, profiles: 5, documents: 0, mentions: 0, checked: body.scope === 'full' ? 561 : 100 }, results: { profiles: fixtureProfiles, documents: [], mentions: [] } };
      const guest = !req.headers.authorization;
      const shown = guest ? { ...data, results: { ...data.results, profiles: fixtureProfiles.slice(0, 2) },
        guest_preview: { visible_cards: 2, hidden_cards: 3, requires_sign_in: true } } : data;
      if (pathname === '/api/username/stream') {
        res.setHeader('Content-Type', 'application/x-ndjson');
        if (holdStream) {
          const emit = event => res.write(JSON.stringify(event) + '\n');
          emit({ type: 'progress', phase: 'Checking platforms', percent: 2, detail: 'Starting scan' });
          pendingStream = {
            emitCard(index) {
              emit({ type: 'progress', phase: 'Checking platforms', percent: (index + 1) * 12,
                detail: guest ? 'Quick scan in progress' : `[${index + 1}/561] ${fixtureProfiles[index].platform}, found` });
              emit(guest && index > 1 ? { type: 'found_locked', count: index - 1 }
                : { type: 'found', result: fixtureProfiles[index] });
            },
            complete() { res.end(JSON.stringify({ type: 'complete', data: shown }) + '\n'); pendingStream = null; },
          };
        } else res.end(JSON.stringify({ type: 'complete', data: shown }) + '\n');
      } else json(shown);
    });
    return;
  }
  if (pathname === '/api/plans') return json({ payments_enabled: false, international_payments: { enabled: false }, paypal_payments: { enabled: false } });
  if (pathname === '/api/health') return json({ status: 'ok' });
  if (pathname.startsWith('/api/')) { res.statusCode = 404; return json({ status: 'error' }); }
  const file = path.resolve(root, '.' + pathname);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode = 404; return res.end(); }
  res.setHeader('Content-Type', ({ '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json' })[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ executablePath: process.env.MYRECON_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
    signedIn = false;
    await page.goto(base + '/index.html#tool=username');
    await page.locator('input[name="scope"][value="standard"]').check();
    const paste = async text => page.locator('#queryInput').evaluate((input, text) => {
      const data = new DataTransfer(); data.setData('text/plain', text);
      input.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
    }, text);
    const profileCount = scans.length;
    await paste('https://www.instagram.com/example.name/?utm_source=share');
    await paste('https://www.instagram.com/example.name/?utm_source=duplicate');
    await page.waitForFunction(() => document.querySelector('#results').textContent.includes('Results for “example.name”'));
    assert.equal(scans.length, profileCount + 1);
    assert.equal(scans.at(-1).body.username, 'example.name');
    assert.match(await page.locator('#profileInputPreview').textContent(), /not verified/);
    await paste('https://www.instagram.com/example.name/?utm_source=other');
    await page.waitForTimeout(900);
    assert.equal(scans.length, profileCount + 1, 'duplicate paste');
    await paste('https://github.com/alice https://instagram.com/bob');
    await page.waitForTimeout(900);
    assert.equal(scans.length, profileCount + 1, 'ambiguous paste');
    await paste('https://github.com/cancel-me');
    await page.locator('[data-profile-cancel]').click();
    await page.waitForTimeout(900);
    assert.equal(scans.length, profileCount + 1, 'cancel pending scan');
    await page.locator('#queryInput').fill('@manual_handle');
    await page.waitForTimeout(900);
    assert.equal(scans.length, profileCount + 1, 'typing requires submit');
    await page.locator('#runBtn').click();
    await page.waitForFunction(() => document.querySelector('#results').textContent.includes('Results for “manual_handle”'));
    assert.equal(scans.at(-1).body.username, 'manual_handle');
    // Existing guest entitlement remains in force for auto-submitted profiles.
    const gatedCount = scans.length;
    await page.locator('input[name="scope"][value="full"]').check();
    await paste('https://github.com/needs-auth');
    await page.locator('.gate').waitFor();
    assert.equal(scans.length, gatedCount);
    await page.locator('input[name="scope"][value="standard"]').check();
    await page.setViewportSize({ width: 390, height: 900 });
    await paste('https://www.tiktok.com/@mobile.test');
    await page.waitForFunction(() => document.querySelector('#results').textContent.includes('Results for “mobile.test”'));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.resolve(root, '../artifacts/profile-input-mobile.png'), fullPage: true});
    holdStream = true;
    await paste('https://github.com/stream-check');
    await page.waitForFunction(() => document.querySelector('#liveGrid') !== null && document.querySelector('#runBtn').disabled);
    while (!pendingStream) await page.waitForTimeout(25);
    pendingStream.emitCard(0);
    await page.locator('#liveGrid .card').first().waitFor();
    assert.match(await page.locator('#liveGrid').textContent(), /Same username/);
    const inFlightCount = scans.length;
    await page.locator('#queryInput').press('Enter');
    assert.equal(scans.length, inFlightCount);
    pendingStream.complete();
    await page.waitForFunction(() => document.querySelector('#results').textContent.includes('Results for “stream-check”'));
    assert.equal(await page.getByRole('button', {name:'Forgotten Account Finder',exact:true}).count(), 1);
    await page.locator('[data-match-choice]').first().selectOption('mine');
    await page.waitForFunction(() => document.querySelector('[data-confirmed-count]').textContent === '1 accounts confirmed by you');
    await page.getByRole('button', {name:'Preview my discovery recap'}).click();
    const recap = page.locator('dialog');
    await recap.screenshot({path: path.resolve(root, '../artifacts/discovery-recap-preview.png')});
    assert.match(await recap.innerText(), /I confirmed 1 public account/);
    assert.doesNotMatch(await recap.innerText(), /stream-check|first.example|fixture@example.com/);
    await recap.getByRole('button', {name:'Cancel',exact:true}).click();
    await recap.waitFor({state:'detached'});
    await page.locator('[data-match-choice]').first().selectOption('not_mine');
    await page.waitForFunction(() => document.querySelector('[data-confirmed-count]').textContent === '0 accounts confirmed by you');
    assert.deepEqual(errors, []);
    console.log('Profile browser checks passed: auto paste, canonical handle, source label, duplicate suppression, ambiguity, cancel, manual submit.');
  } finally { server.closeAllConnections(); server.close(); await browser.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });

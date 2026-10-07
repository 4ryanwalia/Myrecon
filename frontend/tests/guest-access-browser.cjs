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
  platform, url: `https://${platform.toLowerCase()}.example/fixture`, category: 'profile', confidence: 'high',
}));
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const json = (value) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(value)); };
  if (pathname === '/assets/js/account.js') {
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
  if (pathname === '/assets/js/config.js') {
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
    for (const width of [1280, 390]) {
      signedIn = false;
      await page.setViewportSize({ width, height: 900 });
      await page.goto(base + '/index.html#tool=username');
      assert.equal(await page.locator('input[name="scope"][value="standard"]').isChecked(), true, 'guests default to Quick');
      assert.equal(await page.locator('.scope-opt').filter({ has: page.locator('input[value="full"]') }).locator('strong').textContent(), 'Standard');
      await page.locator('#queryInput').fill('guest-fixture');
      let count = scans.length;
      await page.locator('#runBtn').click();
      await page.getByText('Results for “guest-fixture”', { exact: true }).waitFor();
      assert.equal(scans.length, count + 1);
      assert.equal(scans.at(-1).path, '/api/username/stream');
      assert.equal(scans.at(-1).body.scope, 'standard', 'Quick retains the API standard scope name');
      assert.equal(scans.at(-1).authorization, undefined);
      for (const scope of ['full', 'extended']) {
        count = scans.length;
        await page.locator(`input[name="scope"][value="${scope}"]`).check();
        await page.locator('#runBtn').click();
        await page.locator('.gate').waitFor();
        assert.match(await page.locator('.gate').textContent(), /require sign-in/);
        assert.equal(scans.length, count, `guest ${scope} must be gated before scan request`);
        assert.equal(await page.locator('[data-gate="signin"]').isVisible(), true);
      }
      count = scans.length;
      await page.locator('[data-gate="standard"]').click();
      await page.getByText('Results for “guest-fixture”', { exact: true }).waitFor();
      assert.equal(scans.length, count + 1, 'gate fallback starts Quick');
      assert.equal(scans.at(-1).body.scope, 'standard');
      assert.equal(await page.locator('input[name="scope"][value="standard"]').isChecked(), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `tool overflow at ${width}`);
      count = scans.length;
      const standardSignin = page.locator('[data-gate="signin-full"]').first();
      assert.equal(await standardSignin.textContent(), 'Sign in for Standard');
      await standardSignin.click();
      await page.waitForFunction(() => window.MyReconAccount.state().user
        && document.querySelector('input[name="scope"][value="full"]').checked
        && !document.querySelector('#runBtn').disabled
        && document.querySelector('#results').textContent.includes('Results for “guest-fixture”'));
      assert.equal(await page.evaluate(() => window.fixtureSignIns), 1, 'Quick CTA signs in once');
      assert.ok(await page.evaluate(() => window.fixtureAccountLoads) > 0, 'guard loads account API');
      assert.equal(scans.length, count + 1, 'Quick sign-in CTA starts exactly one Standard scan');
      assert.equal(scans.at(-1).path, '/api/username/stream');
      assert.equal(scans.at(-1).body.scope, 'full');
      assert.equal(scans.at(-1).authorization, 'Bearer fixture-token');
      assert.equal(await page.locator('input[name="scope"][value="full"]').isChecked(), true);
      assert.equal(await page.locator('.gate').count(), 0);
      await page.goto(base + '/pricing.html');
      const guest = page.locator('[data-plan-card="guest"]');
      assert.equal(await guest.locator('h3').textContent(), 'Guest login');
      const copy = await guest.textContent();
      assert.match(copy, /no sign-up/i);
      assert.match(copy, /Quick/i);
      assert.match(copy, /100 platforms/i);
      assert.doesNotMatch(copy, /500\+|sweep|first 100 platform verdicts/i);
      assert.equal(await guest.locator('[data-signin], button').count(), 0);
      assert.equal(await page.locator('[data-plan-card="free"] [data-signin]').isVisible(), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `pricing overflow at ${width}`);
    }
    signedIn = true;
    await page.goto(base + '/index.html#tool=username');
    await page.locator('#queryInput').fill('signed-in-fixture');
    await page.locator('input[name="scope"][value="full"]').check();
    const count = scans.length;
    await page.locator('#runBtn').click();
    await page.getByText('Results for “signed-in-fixture”', { exact: true }).waitFor();
    assert.equal(scans.length, count + 1);
    assert.equal(scans.at(-1).body.scope, 'full');
    assert.equal(scans.at(-1).authorization, 'Bearer fixture-token');
    assert.equal(await page.locator('.gate').count(), 0);
    holdStream = true;
    for (const width of [1280, 390]) {
      for (const isSignedIn of [false, true]) {
        signedIn = isSignedIn;
        await page.setViewportSize({ width, height: 900 });
        await page.goto(base + `/index.html?live=${width}-${isSignedIn}#tool=username`);
        await page.locator('#queryInput').fill('live-fixture');
        if (isSignedIn) await page.locator('input[value="full"]').check();
        await page.locator('#runBtn').click();
        await page.locator('#scanLog > div').first().waitFor();
        assert.equal(await page.locator('.retro-title').isVisible(), true);
        assert.equal(await page.locator('#runBtn').isDisabled(), true);
        for (let index = 0; index < fixtureProfiles.length; index++) {
          pendingStream.emitCard(index);
          await page.waitForFunction(count => document.querySelector('#liveGrid').children.length === count, index + 1);
          assert.equal(await page.locator('#liveGrid .card:not(.card-locked)').count(), isSignedIn ? index + 1 : Math.min(2, index + 1));
          assert.equal(await page.locator('#liveGrid .card-locked').count(), isSignedIn ? 0 : Math.max(0, index - 1));
          assert.equal(await page.locator('.results-bar').count(), 0, 'cards must arrive before completion');
        }
        assert.equal(await page.locator('#liveCount').textContent(), '5');
        assert.match(await page.locator('#scanTally').textContent(), /5 found/);
        if (isSignedIn) assert.match(await page.locator('#scanLog').textContent(), /Fifth, found/);
        else {
          assert.doesNotMatch(await page.locator('#results').innerHTML(), /third\.example|fourth\.example|fifth\.example/);
          assert.equal(await page.locator('.locked-card-shape').first().evaluate(el => getComputedStyle(el).filter), 'blur(5px)');
        }
        await page.screenshot({ path: path.resolve(root, `../artifacts/guest-${isSignedIn ? 'standard' : 'quick'}-live-${width}.png`), fullPage: true });
        pendingStream.complete();
        await page.getByText('Results for “live-fixture”', { exact: true }).waitFor();
        assert.equal(await page.locator('.card-grid .card:not(.card-locked)').count(), isSignedIn ? 5 : 2);
        assert.equal(await page.locator('.card-grid .card-locked').count(), isSignedIn ? 0 : 3);
        if (!isSignedIn) {
          assert.doesNotMatch(await page.locator('#results').innerHTML(), /third\.example|fourth\.example|fifth\.example/);
          assert.equal(await page.locator('.card-locked a, .card-locked [data-wayback]').count(), 0);
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `scan overflow at ${width}`);
      }
    }
    holdStream = false;
    assert.deepEqual(errors, []);
    console.log('Browser checks passed: desktop/mobile guest Quick limited to two visible cards and blurred locked cards; Standard/Extended sign-in gates; authenticated Standard log and cards update before completion; completed reports retain correct card access.');
  } finally { server.closeAllConnections(); server.close(); await browser.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });

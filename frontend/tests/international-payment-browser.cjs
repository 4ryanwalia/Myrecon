/* Checkout fixtures only: no provider navigation or real payments. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../output/international-payment');
const code = 'MR-' + 'a'.repeat(32);
const shop = 'https://buymeacoffee.com/myrecon/e/12345';
let enabled = true;
let requests = 0;
let statusRequests = 0;
let paymentStatus = 'pending';
let checkoutExpiry = null;
let omitExpiry = false;
let hangCheckout = false;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/assets/js/account.js') {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end(`let listeners=[];
      const account=paid=>paid?{standard_scans_unlimited:true,extended_pack_scans_left:10,deep_search_enabled:true}:{standard_scans_left:5};
      const user=uid=>uid?{uid,email:uid+'@example.com'}:null;
      let st={user:user(sessionStorage.getItem('fixture_uid')),account:account(sessionStorage.getItem('fixture_paid')==='true')};
      const emit=()=>listeners.forEach(fn=>fn(st));
      window.emitFixtureAccountState=emit;
      window.fixtureSetUser=(uid,paid=false)=>{
        uid?sessionStorage.setItem('fixture_uid',uid):sessionStorage.removeItem('fixture_uid');
        sessionStorage.setItem('fixture_paid',String(paid)); st={user:user(uid),account:account(paid)};emit();
      };
      window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>st,
      onChange:fn=>listeners.push(fn),avatarHtml:()=>'',wireAvatar:()=>{},
      friendly:e=>e.code==='auth/popup-closed-by-user'?'':e.message,
      authHeaders:async()=>window.fixtureAuthHang?new Promise(()=>{}):{Authorization:'Bearer fixture-token'},
      signIn:async()=>{
        if(window.fixtureSignInMode==='hang')return new Promise(resolve=>{window.resolveFixtureSignIn=resolve;});
        if(window.fixtureSignInMode==='cancel')throw Object.assign(new Error('Closed'),{code:'auth/popup-closed-by-user'});
        sessionStorage.setItem('fixture_uid','fixture');st={user:user('fixture'),account:account(false)};
      },
      signInRedirect:async()=>{
        sessionStorage.setItem('fixture_redirects',String(Number(sessionStorage.getItem('fixture_redirects')||0)+1));
        sessionStorage.setItem('fixture_intent_seen',String(!!sessionStorage.getItem('mr_bmc_signin_intent')));
        sessionStorage.setItem('fixture_uid','fixture');location.reload();return new Promise(()=>{});
      },
      signOut:async()=>window.fixtureSetUser(null),
      refreshAccount:async()=>{st.account=account(true);emit();return st.account;}};`);
  }
  if (pathname === '/assets/js/config.js') {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end('window.MYRECON_API_BASE=location.origin;\n' + fs.readFileSync(path.join(root, 'assets/js/config.js'), 'utf8'));
  }
  if (pathname.startsWith('/api/')) {
    res.setHeader('Content-Type', 'application/json');
    if (pathname === '/api/plans') return res.end(JSON.stringify({payments_enabled:false,international_payments:{enabled}}));
    if (pathname === '/api/history') return res.end('{"scans":[]}');
    if (pathname === '/api/billing/buymeacoffee/checkout' || pathname === '/api/billing/buymeacoffee/status') {
      assert.equal(req.headers.authorization, 'Bearer fixture-token');
      let body = '';
      req.on('data', chunk => { body += chunk; });
      return req.on('end', () => {
        if (pathname.endsWith('/status')) {
          assert.deepEqual(JSON.parse(body), {activation_code:code});
          statusRequests++;
          return res.end(JSON.stringify({payment_status:paymentStatus}));
        }
        assert.deepEqual(JSON.parse(body), {plan:'extended'});
        requests++;
        if (hangCheckout) return;
        res.end(JSON.stringify({url:shop,activation_code:code,amount:399,currency:'USD',
          ...(omitExpiry ? {} : {expires_at:checkoutExpiry ?? Math.floor(Date.now()/1000)+7*86400})}));
      });
    }
    res.statusCode = 404; return res.end('{}');
  }
  const file = path.resolve(root, '.' + pathname);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode=404; return res.end(); }
  const types = {'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml'};
  res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({executablePath:process.env.MYRECON_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true});
  fs.mkdirSync(output, {recursive:true});
  async function pageFor(width, mode='normal') {
    const context = await browser.newContext({viewport:{width,height:900}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(mode => {
      window.fixtureSignInMode = mode;
      Object.defineProperty(navigator, 'clipboard', {value:{writeText:async text => {
        if (window.fixtureCopyFail) throw new Error('Clipboard blocked');
        window.fixtureCopied = text;
      }}});
    }, mode);
    await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
    await page.goto(base + '/pricing.html');
    await page.waitForFunction(() => !document.querySelector('[data-buy-international]').disabled);
    return {page,errors,context};
  }
  const visibleCheckout = page => page.locator('#activationCode').waitFor({state:'visible'});
  async function checkPayment(page, expected) {
    await page.locator('#refreshInternational').click();
    await page.waitForFunction(expected => document.querySelector('#internationalCheckout').dataset.payment === expected
      && !document.querySelector('#refreshInternational').disabled, expected);
  }
  async function cleared(page) {
    assert.equal(await page.locator('#internationalCheckout').isVisible(), false);
    assert.equal(await page.locator('#activationCode').inputValue(), '');
    assert.equal(await page.locator('#openInternational').getAttribute('href'), null);
    assert.equal(await page.evaluate(() => sessionStorage.getItem('mr_bmc_checkout')), null);
  }
  try {
    for (const width of [1280,390]) {
      paymentStatus = 'pending';
      const {page,errors,context} = await pageFor(width);
      const initialRequests = requests;
      await page.locator('[data-buy-international]').click();
      await visibleCheckout(page);
      // Firebase's account notification can arrive after popup sign-in resolves.
      await page.evaluate(() => window.emitFixtureAccountState());
      assert.equal(await page.locator('#internationalCheckout').isVisible(), true);
      assert.equal(await page.locator('#activationCode').inputValue(), code);
      assert.equal(await page.locator('#openInternational').getAttribute('href'), shop);
      assert.equal(await page.locator('#openInternational').getAttribute('target'), null);
      assert.equal(await page.locator('[data-buy="extended"]').isDisabled(), true);
      await page.locator('#copyActivation').click();
      assert.equal(await page.evaluate(() => window.fixtureCopied), code);
      assert.match(await page.locator('#copyStatus').innerText(), /Code copied/);
      assert.equal(await page.locator('#copyActivation').innerText(), 'Copied!');
      const beforeRestoreStatus = statusRequests;
      await page.reload();
      await visibleCheckout(page);
      await page.waitForFunction(() => document.querySelector('#paymentStatus').textContent.includes('not been')
        && !document.querySelector('#refreshInternational').disabled);
      assert.equal(requests, initialRequests + 1, 'Reload must reuse the saved code');
      assert.equal(statusRequests, beforeRestoreStatus + 1, 'Reload must check this purchase');
      assert.equal(await page.locator('#activationCode').inputValue(), code);
      await page.evaluate(() => { window.fixtureCopyFail = true; });
      await page.locator('#copyActivation').click();
      assert.match(await page.locator('#copyStatus').innerText(), /copy it manually/);
      assert.equal(await page.locator('#activationCode').evaluate(el => el.selectionEnd - el.selectionStart), code.length);
      // A previous paid pack does not prove that this purchase was paid.
      await page.evaluate(() => window.fixtureSetUser('fixture', true));
      await checkPayment(page, 'pending');
      assert.match(await page.locator('#acctUsage').innerText(), /10 Extended/);
      assert.doesNotMatch(await page.locator('#paymentStatus').innerText(), /Payment confirmed/);
      paymentStatus = 'applied';
      await checkPayment(page, 'applied');
      assert.match(await page.locator('#paymentStatus').innerText(), /Payment confirmed/);
      assert.equal(await page.locator('#openInternational').getAttribute('href'), null);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.locator('#internationalCheckout').screenshot({path:path.join(output, `checkout-${width}.png`)});
      await page.evaluate(() => window.fixtureSetUser('other'));
      await cleared(page);
      paymentStatus = 'pending';
      await page.locator('[data-buy-international]').click();
      await visibleCheckout(page);
      await page.locator('#signOutBtn').click();
      await cleared(page);
      assert.equal(await page.evaluate(() => sessionStorage.getItem('mr_bmc_signin_intent')), null);
      assert.deepEqual(errors, []);
      await context.close();

      const recovery = await pageFor(width, 'hang');
      const beforeRedirect = requests;
      await recovery.page.locator('[data-buy-international]').click();
      await recovery.page.locator('#signinRecovery').waitFor({state:'visible'});
      assert.equal(await recovery.page.locator('[data-buy-international]').isDisabled(), true);
      assert.match(await recovery.page.locator('#payNote').innerText(), /Finish Google sign-in/);
      assert.equal(await recovery.page.evaluate(() => sessionStorage.getItem('mr_bmc_checkout')), null);
      await recovery.page.locator('#signinRedirect').click();
      await visibleCheckout(recovery.page);
      assert.equal(requests, beforeRedirect + 1, 'Redirect return resumes one checkout');
      assert.equal(await recovery.page.evaluate(() => sessionStorage.getItem('fixture_redirects')), '1');
      assert.equal(await recovery.page.evaluate(() => sessionStorage.getItem('fixture_intent_seen')), 'true');
      assert.equal(await recovery.page.evaluate(() => sessionStorage.getItem('mr_bmc_signin_intent')), null);
      await recovery.page.evaluate(() => window.emitFixtureAccountState());
      assert.equal(requests, beforeRedirect + 1);
      assert.deepEqual(recovery.errors, []);
      await recovery.context.close();

      const cancelled = await pageFor(width, 'cancel');
      await cancelled.page.locator('[data-buy-international]').click();
      await cancelled.page.waitForFunction(() => document.querySelector('#payNote').textContent.includes('cancelled'));
      assert.equal(await cancelled.page.locator('[data-buy-international]').isDisabled(), false);
      assert.equal(await cancelled.page.locator('#signinRecovery').isVisible(), false);
      assert.equal(await cancelled.page.evaluate(() => sessionStorage.getItem('mr_bmc_signin_intent')), null);
      await cleared(cancelled.page);
      assert.deepEqual(cancelled.errors, []);
      await cancelled.context.close();

      checkoutExpiry = Math.floor(Date.now()/1000) - 1;
      const expired = await pageFor(width);
      await expired.page.locator('[data-buy-international]').click();
      await visibleCheckout(expired.page);
      assert.equal(await expired.page.locator('#openInternational').getAttribute('href'), null);
      assert.equal(await expired.page.locator('#openInternational').getAttribute('aria-disabled'), 'true');
      await expired.page.locator('#openInternational').click();
      assert.equal(expired.page.url(), base + '/pricing.html');
      assert.match(await expired.page.locator('#paymentStatus').innerText(), /expired/);
      paymentStatus = 'expired';
      await checkPayment(expired.page, 'expired');
      assert.match(await expired.page.locator('#paymentStatus').innerText(), /contact support/);
      assert.deepEqual(expired.errors, []);
      await expired.context.close();
      checkoutExpiry = null;
      paymentStatus = 'pending';
    }

    // Bound the entire auth-header/request wait using a deterministic browser clock.
    for (const blocked of ['auth', 'fetch']) {
      const fixture = await pageFor(1280);
      await fixture.page.clock.install();
      await fixture.page.evaluate(blocked => { window.fixtureAuthHang = blocked === 'auth'; }, blocked);
      hangCheckout = blocked === 'fetch';
      const beforeBlocked = requests;
      const checkoutRequest = blocked === 'fetch' ? fixture.page.waitForRequest(base + '/api/billing/buymeacoffee/checkout') : null;
      await fixture.page.locator('[data-buy-international]').click();
      await fixture.page.waitForFunction(() => document.querySelector('#payNote').textContent.includes('Preparing your account code'));
      if (checkoutRequest) await checkoutRequest;
      await fixture.page.clock.runFor(30001);
      await fixture.page.waitForFunction(() => document.querySelector('#payNote').textContent.includes('taking too long'));
      assert.equal(await fixture.page.locator('[data-buy-international]').isDisabled(), false);
      assert.equal(await fixture.page.locator('#internationalCheckout').isVisible(), false);
      if (blocked === 'auth') assert.equal(requests, beforeBlocked, 'Timed out auth must not send a checkout request');
      assert.deepEqual(fixture.errors, []);
      await fixture.context.close();
      hangCheckout = false;
    }

    omitExpiry = true;
    const malformed = await pageFor(1280);
    await malformed.page.locator('[data-buy-international]').click();
    await malformed.page.waitForFunction(() => document.querySelector('#payNote').textContent.includes('Could not prepare'));
    await cleared(malformed.page);
    assert.equal(await malformed.page.locator('[data-buy-international]').isDisabled(), false);
    await malformed.context.close();
    omitExpiry = false;

    enabled = false;
    const page = await browser.newPage();
    await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
    await page.goto(base+'/pricing.html');
    await page.waitForFunction(() => document.querySelector('#internationalStatus').textContent.includes('temporarily unavailable'));
    assert.equal(await page.locator('[data-buy-international]').isDisabled(), true);
    await page.close();
    console.log('International checkout passed: desktop/mobile copy, payment status, restore, privacy, expiry, popup recovery, cancellation, auth/request deadlines and disabled configuration.');
  } finally { await browser.close(); server.closeAllConnections(); server.close(); }
})().catch(e => {console.error(e);server.closeAllConnections();server.close();process.exitCode=1;});

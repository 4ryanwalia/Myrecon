/* Actual pricing UI with stubbed providers. Never creates a real payment. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const base = 'http://127.0.0.1:8765';
const order = 'TESTORDER123456789';
let enabled = true, applied = false, captureCalls = 0, createCalls = 0;
let approval = 'https://www.paypal.com/checkoutnow?token=' + order;

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}) });
  async function page(options = {}) {
    const context = await browser.newContext({ viewport: options.mobile ? { width: 390, height: 844 } : { width: 1280, height: 900 } });
    const tab = await context.newPage();
    await tab.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== base) return url.hostname === 'www.paypal.com'
        ? route.fulfill({ contentType: 'text/html', body: '<p>Fixture checkout</p>' }) : route.abort();
      if (url.pathname === '/assets/js/account.js') return route.fulfill({ contentType: 'application/javascript', body: `
        let st={user:${options.signedOut ? 'null' : '{uid:"buyer",email:"buyer@example.com"}'},account:{standard_scans_left:5}};
        const listeners=[];
        window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>st,onChange:f=>listeners.push(f),
          avatarHtml:()=>'',wireAvatar:()=>{},friendly:e=>e.message,authHeaders:async()=>({Authorization:'Bearer fixture'}),
          signIn:async()=>{st.user={uid:'buyer'};},signOut:async()=>{st.user=null;listeners.forEach(f=>f(st));},
          refreshAccount:async()=>{window.refreshed=true;st.account={standard_scans_unlimited:true,extended_pack_scans_left:10};listeners.forEach(f=>f(st));}};
      ` });
      if (url.pathname === '/assets/js/config.js') return route.fulfill({ contentType: 'application/javascript', body: `window.MYRECON={apiBase:'${base}'};` });
      if (url.pathname === '/api/plans') return route.fulfill({ json: { paypal_payments: { enabled }, payments_enabled: false, international_payments: { enabled: false } } });
      if (url.pathname === '/api/history') return route.fulfill({ json: { scans: [] } });
      if (url.pathname === '/api/billing/paypal/order') {
        createCalls++;
        assert.deepEqual(route.request().postDataJSON(), { plan: 'extended' });
        return route.fulfill({ json: { order_id: order, url: approval } });
      }
      if (url.pathname === '/api/billing/paypal/capture') {
        captureCalls++;
        assert.deepEqual(route.request().postDataJSON(), { order_id: order });
        return route.fulfill({ json: { applied, pending: !applied } });
      }
      const file = path.join(root, url.pathname.replace(/^\//, ''));
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
      const type = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.svg') ? 'image/svg+xml' : 'text/html';
      return route.fulfill({ contentType: type, body: fs.readFileSync(file) });
    });
    return { context, tab };
  }
  try {
    const first = await page({ signedOut: true, mobile: true });
    await first.tab.goto(base + '/pricing.html');
    await first.tab.waitForFunction(() => !document.querySelector('[data-buy-paypal]').disabled);
    assert.equal(await first.tab.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await first.tab.locator('[data-buy-paypal]').click();
    await first.tab.waitForURL('https://www.paypal.com/**');
    assert.equal(createCalls, 1);
    assert.equal(captureCalls, 0);
    await first.context.close();

    const returned = await page();
    await returned.tab.goto(base + '/pricing.html?paypal=return&token=' + order);
    await returned.tab.waitForFunction(() => document.querySelector('#paypalStatus').textContent.includes('not confirmed'));
    assert.equal(await returned.tab.evaluate(() => window.refreshed), undefined);
    applied = true;
    await returned.tab.locator('#checkPayPal').click();
    await returned.tab.waitForFunction(() => window.refreshed === true);
    assert.match(await returned.tab.locator('#paypalStatus').textContent(), /Payment confirmed/);
    assert.equal(new URL(returned.tab.url()).search, '');
    const out = path.resolve(root, '../output/paypal-checkout');
    fs.mkdirSync(out, { recursive: true });
    await returned.tab.screenshot({ path: path.join(out, 'pricing-confirmed.png'), fullPage: true });
    await returned.context.close();

    const before = captureCalls;
    const cancelled = await page();
    await cancelled.tab.goto(base + '/pricing.html?paypal=cancel&token=' + order);
    await cancelled.tab.waitForFunction(() => document.querySelector('#paypalStatus').textContent.includes('cancelled'));
    assert.equal(captureCalls, before);
    await cancelled.context.close();

    approval = 'https://evil.example/checkout';
    const invalid = await page();
    await invalid.tab.goto(base + '/pricing.html');
    await invalid.tab.waitForFunction(() => !document.querySelector('[data-buy-paypal]').disabled);
    await invalid.tab.locator('[data-buy-paypal]').click();
    await invalid.tab.waitForFunction(() => document.querySelector('#paypalStatus').textContent.includes('Invalid PayPal'));
    assert.equal(new URL(invalid.tab.url()).origin, base);
    await invalid.context.close();

    enabled = false;
    const disabled = await page();
    await disabled.tab.goto(base + '/pricing.html');
    await disabled.tab.waitForFunction(() => document.querySelector('#paypalStatus').textContent.includes('temporarily unavailable'));
    assert.equal(await disabled.tab.locator('[data-buy-paypal]').isDisabled(), true);
    await disabled.context.close();
    console.log('PayPal browser checks passed: mobile layout, sign-in, approved redirect, pending/retry, confirmed account refresh, cancellation, unsafe URL and disabled configuration.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

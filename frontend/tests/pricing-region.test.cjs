const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'assets/js/subscriptions.js'), 'utf8');

// Which single checkout the Pro card offers, for each way the visitor's
// country can become known. /api/geo (Vercel's country header) wins over the
// browser time zone; with no answer the time zone decides; ?region= and the
// visitor's own switch override both.
test('pricing offers one checkout by country, falling back to the time zone', async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const cases = [
      { timezoneId: 'Asia/Kolkata', geo: null, expected: 'razorpay', label: 'India time zone, no geo answer' },
      { timezoneId: 'America/New_York', geo: null, expected: 'paypal', label: 'US time zone, no geo answer' },
      { timezoneId: 'America/New_York', geo: 'IN', expected: 'razorpay', label: 'geo says India (a VPN-less visitor on a US clock)' },
      { timezoneId: 'Asia/Kolkata', geo: 'US', expected: 'paypal', label: 'geo says US (traveller with an India clock)' },
    ];
    for (const { timezoneId, geo, expected, label } of cases) {
      const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, timezoneId });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      await page.route('**/*', async (route) => {
        const url = new URL(route.request().url());
        if (url.pathname === '/api/geo') return geo ? route.fulfill({ json: { country: geo } }) : route.abort();
        if (url.pathname === '/api/plans') return route.fulfill({ json: { subscriptions: ['monthly', 'yearly', 'inr_monthly', 'inr_yearly'].map((id) => ({ id, enabled: true })) } });
        if (url.pathname === '/api/billing/subscriptions') return route.fulfill({ json: { subscription: null } });
        if (url.pathname.includes('/assets/')) {
          const clean = url.pathname.replace('/optimized/', '/').replace(/\.[a-f0-9]{12}\./, '.');
          const file = path.join(root, clean);
          if (fs.existsSync(file)) return route.fulfill({ path: file });
        }
        if (url.pathname === '/pricing') {
          const html = fs.readFileSync(path.join(root, 'pricing.html'), 'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '');
          return route.fulfill({ contentType: 'text/html', body: html.replace('</body>', `<script>window.MYRECON={apiBase:''};window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>({user:null}),authHeaders:async()=>({}),refreshAccount:async()=>{},friendly:e=>e.message,onChange:()=>{}};</script><script>${source}</script></body>`) });
        }
        return route.abort();
      });
      await page.goto('https://pricing.test/pricing');
      await page.locator(`[data-subscribe="${expected}"]:enabled`).waitFor();
      assert.equal(await page.locator('.plan .provider-btn:visible').count(), 1, `${label}: exactly one checkout button`);
      assert.match(await page.locator('.plan .provider-btn:visible').innerText(), /Try Pro free for 7 days/, label);
      assert.equal(await page.locator('#proPrice').innerText(), expected === 'razorpay' ? '₹299' : '$3.99', `${label}: price matches the checkout`);
      assert.equal(await page.locator('#proAnchor').isVisible(), expected === 'paypal', `${label}: monthly strike-through exists only in USD`);
      // The switch is the visitor's way out of a wrong guess, and it is remembered.
      await page.locator('#regionSwitch').click();
      assert.equal(await page.locator('.plan .provider-btn:visible').count(), 1, `${label}: still one button after switching`);
      assert.equal(await page.locator(`[data-subscribe="${expected}"]`).isVisible(), false, `${label}: switch moves to the other checkout`);
      assert.deepEqual(errors, [], label);
      await context.close();
    }
  } finally { await browser.close(); }
});

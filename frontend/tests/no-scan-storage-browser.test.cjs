const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');

test('account page shows aggregate count without requesting scan history', async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage();
    const apiRequests = [];
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.hostname !== 'storage.test') return route.abort();
      if (url.pathname.startsWith('/api/')) {
        apiRequests.push(url.pathname);
        return route.fulfill({ json: { status: 'ok', plans: [], payments_enabled: false, subscriptions: [] } });
      }
      if (/\/account(?:\.[a-f0-9]+)?\.js$/.test(url.pathname)) {
        return route.fulfill({ contentType: 'application/javascript', body: `window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>({user:{uid:'fixture'},account:{tier:'free',scan_count:7,standard_scans_left:5}}),avatarHtml:()=>'',wireAvatar:()=>{},onChange:()=>{},authHeaders:async()=>({}),friendly:e=>e.message,refreshAccount:async()=>{},signOut:async()=>{}};` });
      }
      let relative = url.pathname === '/pricing' ? 'pricing.html' : url.pathname.slice(1);
      relative = relative.replace(/^assets\/optimized\/js\/([\w-]+)\.[a-f0-9]+\.js$/, 'assets/js/$1.js');
      const file = path.resolve(root, relative);
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
      const type = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : undefined;
      return route.fulfill({ path: file, contentType: type });
    });
    await page.goto('https://storage.test/pricing');
    await page.locator('#scanList').getByText('Searches are not saved.', { exact: false }).waitFor();
    assert.match(await page.locator('#scanList').innerText(), /Scan count: 7/);
    assert.equal(apiRequests.some(p => p.startsWith('/api/history')), false);
    assert.equal(await page.locator('#clearScans').isVisible(), false);
  } finally {
    await browser.close();
  }
});

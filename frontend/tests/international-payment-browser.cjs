/* Checkout fixtures only: no provider navigation or real payments. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../output/international-payment');
let enabled = true;
let requests = 0;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/assets/js/account.js') {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end(`let st={user:null,account:null}; let listeners=[];
      window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>st,
      onChange:fn=>listeners.push(fn),avatarHtml:()=>'',wireAvatar:()=>{},friendly:e=>e.message,
      authHeaders:async()=>({Authorization:'Bearer fixture-token'}),
      signIn:async()=>{st={user:{uid:'fixture',email:'a@example.com'},account:{standard_scans_left:5}};listeners.forEach(fn=>fn(st));},
      signOut:async()=>{st={user:null,account:null};listeners.forEach(fn=>fn(st));},
      refreshAccount:async()=>{st.account={standard_scans_unlimited:true,extended_pack_scans_left:10,deep_search_enabled:true};listeners.forEach(fn=>fn(st));}};`);
  }
  if (pathname === '/assets/js/config.js') {
    res.setHeader('Content-Type', 'application/javascript');
    return res.end('window.MYRECON_API_BASE=location.origin;\n' + fs.readFileSync(path.join(root,'assets/js/config.js'),'utf8'));
  }
  if (pathname.startsWith('/api/')) {
    res.setHeader('Content-Type', 'application/json');
    if (pathname === '/api/plans') return res.end(JSON.stringify({payments_enabled:false,international_payments:{enabled}}));
    if (pathname === '/api/history') return res.end('{"scans":[]}');
    if (pathname === '/api/billing/buymeacoffee/checkout') {
      assert.equal(req.headers.authorization, 'Bearer fixture-token');
      let body = '';
      req.on('data', chunk => { body += chunk; });
      return req.on('end', () => {
        assert.deepEqual(JSON.parse(body), {plan:'extended'});
        requests++;
        res.end(JSON.stringify({url:'https://buymeacoffee.com/myrecon/e/12345',activation_code:'MR-'+'a'.repeat(32),amount:399,currency:'USD'}));
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
  try {
    for (const width of [1280,390]) {
      const page = await browser.newPage({viewport:{width,height:900}});
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
      await page.goto(base + '/pricing.html');
      const button = page.locator('[data-buy-international]');
      await page.waitForFunction(() => !document.querySelector('[data-buy-international]').disabled);
      await button.click();
      await page.locator('#activationCode').waitFor({state:'visible'});
      assert.equal(await page.locator('#activationCode').inputValue(), 'MR-'+'a'.repeat(32));
      assert.equal(await page.locator('#openInternational').getAttribute('href'), 'https://buymeacoffee.com/myrecon/e/12345');
      assert.match(await page.locator('#payNote').innerText(), /paste/);
      await page.locator('#refreshInternational').click();
      assert.match(await page.locator('#acctUsage').innerText(), /10 Extended/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.locator('#internationalCheckout').screenshot({path:path.join(output, `checkout-${width}.png`)});
      await page.locator('#signOutBtn').click();
      assert.equal(await page.locator('#internationalCheckout').isVisible(), false);
      assert.equal(await page.locator('#activationCode').inputValue(), '');
      assert.deepEqual(errors, []);
      await page.close();
    }
    enabled = false;
    const page = await browser.newPage();
    await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
    await page.goto(base+'/pricing.html');
    await page.waitForFunction(() => document.querySelector('#payNote').textContent.includes('open soon'));
    assert.equal(await page.locator('[data-buy-international]').isDisabled(), true);
    assert.equal(requests, 2);
    await page.close();
    console.log('International checkout: desktop/mobile sign-in, activation, refresh, sign-out and disabled configuration passed.');
  } finally { await browser.close(); server.close(); }
})().catch(e => {console.error(e);server.close();process.exitCode=1;});

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'assets/js/subscriptions.js'), 'utf8');

test('pricing switches periods and providers, requires fresh consent, and fits responsive themes', async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1366,height:900}});
    const errors = []; const creations = []; let currentSubscription = null;
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/api/plans') return route.fulfill({json:{subscriptions:['monthly','yearly','inr_monthly','inr_yearly'].map(id=>({id,enabled:true}))}});
      if (url.pathname === '/api/billing/subscriptions') {
        if (route.request().method() === 'POST') {
          creations.push(route.request().postDataJSON());
          return route.fulfill({status:503,json:{error:'Test checkout stopped before provider approval.'}});
        }
        return route.fulfill({json:{subscription:currentSubscription}});
      }
      if (url.pathname.includes('/assets/')) {
        const clean = url.pathname.replace('/optimized/','/').replace(/\.[a-f0-9]{12}\./,'.');
        const file = path.join(root, clean);
        if (fs.existsSync(file)) return route.fulfill({path:file});
      }
      if (url.pathname === '/pricing') {
        const html = fs.readFileSync(path.join(root,'pricing.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
        return route.fulfill({contentType:'text/html',body:html.replace('</body>',`<script>window.MYRECON={apiBase:''};window.MyReconAccount={enabled:true,ready:Promise.resolve(),state:()=>({user:{uid:'test'}}),authHeaders:async()=>({}),refreshAccount:async()=>{},friendly:e=>e.message,onChange:()=>{}};window.Razorpay=function(){};</script><script>${source}</script></body>`)});
      }
      return route.abort();
    });
    await page.goto('https://pricing.test/pricing');
    await page.locator('[data-subscribe="paypal"]:enabled').waitFor();
    assert.equal(await page.locator('.plans > section').count(),2);
    assert.equal(await page.locator('select').count(),0);
    assert.ok(await page.locator('.plans').evaluate(el=>el.getBoundingClientRect().bottom) < 900);
    await page.screenshot({path:process.env.PRICING_SCREENSHOT || path.join(require('node:os').tmpdir(),'myrecon-pricing-desktop.png'),fullPage:true});
    await page.setViewportSize({width:1366,height:768});
    assert.ok(await page.locator('.plans').evaluate(el=>el.getBoundingClientRect().bottom) < 768);
    await page.locator('[data-billing="yearly"]').click();
    assert.equal(await page.locator('#proPrice').innerText(),'$19.99');
    assert.match(await page.locator('#proCredits').innerText(),/120/);
    assert.equal(await page.locator('[data-subscribe="razorpay"]').isEnabled(),true);
    await page.locator('[data-subscribe="razorpay"]').click();
    assert.equal(await page.locator('#basicPlan').inputValue(),'inr_yearly');
    assert.match(await page.locator('#basicTerms').innerText(),/₹1,999\/year/);
    await page.keyboard.press('Escape');
    await page.locator('[data-subscribe="paypal"]').click();
    assert.equal(await page.locator('#basicPlan').inputValue(),'yearly');
    assert.match(await page.locator('#basicTerms').innerText(),/US\$19.99\/year/);
    assert.equal(await page.locator('#startBasic').isDisabled(),true);
    await page.locator('#basicConsent').check();
    await page.locator('#startBasic').click();
    await page.locator('#checkoutStatus').getByText('Test checkout stopped before provider approval.').waitFor();
    assert.deepEqual(creations,[{plan:'yearly',consent:true}]);
    await page.keyboard.press('Escape');
    await page.locator('[data-billing="monthly"]').click();
    await page.locator('[data-subscribe="razorpay"]').click();
    assert.equal(await page.locator('#basicConsent').isChecked(),false);
    assert.equal(await page.locator('#basicPlan').inputValue(),'inr_monthly');
    assert.match(await page.locator('#basicTerms').innerText(),/₹299\/month/);
    await page.locator('#basicConsent').check(); await page.locator('#startBasic').click();
    await page.waitForFunction(()=>document.querySelector('#checkoutStatus').textContent.includes('Test checkout stopped'));
    assert.equal(creations[1].plan,'inr_monthly');
    await page.locator('#closeSubscription').click();
    for (const width of [320,390,768,1366]) {
      await page.setViewportSize({width,height:900});
      for (const theme of ['light','dark']) {
        await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),`${width} ${theme} overflow`);
        if (width===390) await page.screenshot({path:path.join(require('node:os').tmpdir(),`myrecon-pricing-mobile-${theme}.png`),fullPage:true});
      }
    }
    await page.locator('[data-subscribe="paypal"]').click();
    assert.equal(await page.locator('#basicPlan').inputValue(),'monthly');
    assert.equal(await page.locator('#basicConsent').isChecked(),false);
    await page.keyboard.press('Escape');

    // Unauthorized Razorpay checkout is replaceable: notice explains it and customer can proceed with PayPal or resume Razorpay.
    currentSubscription = {id:'sub_TEST123456',provider:'razorpay',plan:'inr_monthly',status:'created',active:false,trial_eligible:true};
    await page.reload();
    await page.locator('#resumeRazorpay').waitFor({state:'visible'});
    assert.equal(await page.locator('#cancelSubscription').innerText(), 'Cancel unfinished checkout');
    await page.locator('#resumeRazorpay').click();
    assert.equal(await page.locator('#basicPlan').inputValue(),'inr_monthly');
    assert.equal(await page.locator('#basicConsent').isChecked(),false);
    await page.locator('#closeSubscription').click();

    const createsBefore = creations.length;
    await page.locator('[data-subscribe="paypal"]').click();
    assert.match(await page.locator('#checkoutNotice').innerText(), /never authorized/);
    await page.locator('#basicConsent').check();
    assert.equal(await page.locator('#startBasic').isEnabled(),true);
    await page.locator('#startBasic').click();
    await page.locator('#checkoutStatus').getByText('Test checkout stopped before provider approval.').waitFor();
    assert.equal(creations.length, createsBefore + 1);
    assert.equal(creations[creations.length - 1].plan, 'monthly');
    await page.keyboard.press('Escape');

    // Confirmed active subscription is a hard conflict and cannot be replaced silently.
    currentSubscription = {id:'sub_TEST123456',provider:'razorpay',plan:'inr_monthly',status:'active',active:true,until:Date.now() + 86400000,trial_eligible:false};
    await page.reload();
    await page.locator('[data-subscribe="paypal"]').click();
    assert.match(await page.locator('#checkoutStatus').innerText(), /already have a Razorpay/);
    assert.equal(await page.locator('#startBasic').isDisabled(),true);
    await page.locator('#checkoutManage').click();
    assert.equal(await page.locator('#subscriptionDialog').isVisible(),false);
    assert.match(await page.locator('#subscriptionDetails').innerText(), /Pro/);
    assert.equal(await page.locator('#cancelSubscription').innerText(), 'Cancel subscription');
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
});

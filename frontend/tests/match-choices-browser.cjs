const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const script = fs.readFileSync(path.join(__dirname, '../assets/js/match-choices.js'));
const html = `<html><body><main></main><script>
let user = null, listeners = [];
window.MYRECON = {};
window.MyReconAccount = { ready: Promise.resolve(), state: () => ({user}),
 authHeaders: async () => ({Authorization: user.uid}), onChange: f => listeners.push(f) };
window.switchUser = id => { user = id ? {uid:id} : null; listeners.forEach(f=>f()); };
window.draw = () => { document.querySelector('main').innerHTML =
 MyReconMatchChoices.controls('https://example.com/Alice#bio') + MyReconMatchChoices.controls('https://example.com/alice'); };
</script><script src='/choices.js'></script></body></html>`;
(async () => {
  const rows = {}; let fail = false;
  const server = http.createServer((req, res) => {
    if (req.url === '/choices.js') { res.setHeader('Content-Type', 'text/javascript'); res.end(script); return; }
    if (req.url === '/api/match-choices') {
      if (fail) { res.statusCode = 503; res.end('{}'); return; }
      const owner = req.headers.authorization; rows[owner] ||= {};
      let body = ''; req.on('data', c => body += c); req.on('end', () => {
        if (body) { const {url, choice, cleanup} = JSON.parse(body); if (choice) rows[owner][url] = {url, choice, cleanup}; else delete rows[owner][url]; }
        res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({choices: rows[owner]}));
      }); return;
    }
    res.setHeader('Content-Type', 'text/html'); res.end(html);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true, ...(process.env.BROWSER_CHANNEL ? {channel:process.env.BROWSER_CHANNEL} : {})});
    const page = await browser.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    const url = `http://127.0.0.1:${server.address().port}`;
    await page.goto(url); await page.evaluate(() => draw());
    const first = page.locator('[data-match-choice]').first(), second = page.locator('[data-match-choice]').nth(1);
    await first.selectOption('not_mine');
    assert.equal(await second.inputValue(), '');
    await page.reload(); await page.evaluate(() => draw());
    assert.equal(await first.inputValue(), 'not_mine');
    assert.match(await page.locator('main').innerText(), /browser only/);
    await page.evaluate(() => switchUser('one'));
    await page.waitForFunction(() => !document.querySelector('select').disabled);
    assert.equal(await first.inputValue(), '');
    await first.selectOption('mine');
    await page.waitForFunction(() => !document.querySelector('[data-cleanup]').disabled);
    await page.locator('[data-cleanup]').first().selectOption('requested');
    await page.waitForFunction(() => !document.querySelector('[data-cleanup]').disabled);
    assert.equal(await page.locator('[data-cleanup]').first().inputValue(), 'requested');
    await page.waitForFunction(() => !document.querySelector('select').disabled);
    const report = await page.evaluate(() => MyReconMatchChoices.annotate({results:[{url:'https://example.com/Alice',confidence:'high'}]}));
    assert.equal(report.results[0].ownership_choice.choice, 'mine');
    assert.equal(report.results[0].ownership_choice.basis, 'user_assertion');
    assert.equal(report.results[0].confidence, 'high');
    await page.evaluate(() => switchUser('two'));
    await page.waitForFunction(() => !document.querySelector('select').disabled);
    assert.equal(await first.inputValue(), '');
    await page.evaluate(() => switchUser('one'));
    await page.waitForFunction(() => !document.querySelector('select').disabled);
    assert.equal(await first.inputValue(), 'mine');
    fail = true; await first.selectOption('unsure');
    await page.waitForFunction(() => document.querySelector('[data-match-status]').textContent.includes('not saved'));
    assert.equal(await first.inputValue(), 'mine');
    fail = false; await first.selectOption('unsure');
    await page.waitForFunction(() => !document.querySelector('select').disabled);
    assert.equal(await first.inputValue(), 'unsure');
    await first.selectOption('');
    await page.waitForFunction(() => !document.querySelector('select').disabled);
    assert.equal(Object.keys(rows.one).length, 0);
    assert.deepEqual(errors, []);
    console.log('PASS: guest reload, account persistence/isolation, URL identity, exports, revise/reset and failed-save rollback');
  } finally { await browser?.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(e => { console.error(e); process.exitCode = 1; });

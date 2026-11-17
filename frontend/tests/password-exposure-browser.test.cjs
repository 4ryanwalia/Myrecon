const test = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const path = require('node:path');
const { chromium } = require('playwright');

test('password checker requires a readable range before showing a verdict', async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  try {
    const page = await browser.newPage();
    const root = path.resolve(__dirname, '..');
    const origin = 'https://password.test';
    const secret = 'synthetic browser fixture';
    const hash = createHash('sha1').update(secret).digest('hex').toUpperCase();
    const suffix = hash.slice(5);
    let response;
    const requests = [];
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.hostname === 'api.pwnedpasswords.com') {
        requests.push([url.pathname, route.request().headers()['add-padding']]);
        return route.fulfill(response);
      }
      if (url.origin === origin) {
        if (url.pathname === '/') return route.fulfill({ path: path.join(root, 'index.html') });
        if (/^\/assets\/js\/(app|config|env)\.js$/.test(url.pathname)) {
          return route.fulfill({ path: path.join(root, url.pathname) });
        }
      }
      return route.abort();
    });
    await page.goto(origin);
    await page.locator('#tab-password').click();
    await page.locator('#queryInput').fill(secret);
    const cases = [
      [200, '', 'unreadable data'],
      [200, suffix + ':42\r\ntruncated', 'unreadable data'],
      [200, suffix + ':7oops', 'unreadable data'],
      [206, suffix + ':42', 'HTTP 206'],
      [200, 'F'.repeat(35) + ':3\r\n' + suffix.toLowerCase() + ':42\r\n', 'seen 42 times'],
      [200, suffix + ':0', 'no match'],
    ];
    for (const [index, [status, body, expected]] of cases.entries()) {
      response = { status, body, contentType: 'text/plain' };
      await page.locator('#runBtn').click();
      await page.locator('#results').getByText(expected, { exact: false }).first().waitFor();
      assert.equal(requests.length, index + 1);
      assert.deepEqual(requests.at(-1), ['/range/' + hash.slice(0, 5), 'true']);
    }
  } finally {
    await browser.close();
  }
});

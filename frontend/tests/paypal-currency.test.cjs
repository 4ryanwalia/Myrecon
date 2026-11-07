const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../assets/js/paypal-checkout.js'), 'utf8');

async function setup({ quotes, order, signedIn = true, locale = 'en-US' } = {}) {
  const callbacks = {};
  const elements = {};
  for (const name of ['[data-buy-paypal]', '#paypalStatus', '#paypalCurrency', '#paypalCurrencyControl', '#retryPayPalCurrencies']) {
    elements[name] = { disabled: false, hidden: false, value: '', children: [], listeners: {}, attrs: {},
      addEventListener(event, cb) { this.listeners[event] = cb; },
      setAttribute(key, value) { this.attrs[key] = value; },
      replaceChildren() { this.children = []; this.value = ''; },
      appendChild(child) { this.children.push(child); } };
  }
  const store = new Map();
  const requests = [];
  let user = signedIn ? { uid: 'user-1' } : null;
  const account = { enabled: true, ready: Promise.resolve(), state: () => ({ user }),
    authHeaders: async () => ({ Authorization: 'Bearer test' }),
    signIn: async () => { user = { uid: 'user-1' }; },
    onChange() {}, friendly: (e) => e.message, refreshAccount: async () => {} };
  const window = { navigator: { language: locale }, MyReconAccount: account, MYRECON: {}, location: { search: '', href: 'https://myrecon.xyz/pricing',
    assign(url) { this.assigned = url; } }, history: { replaceState() {} } };
  const document = { querySelector: (name) => elements[name], createElement: () => ({ value: '', textContent: '' }),
    addEventListener: (event, callback) => { callbacks[event] = callback; } };
  const fetch = async (url, options = {}) => {
    requests.push({ url, options });
    if (url.endsWith('/api/plans')) return { ok: true, json: async () => ({ paypal_payments: { enabled: true } }) };
    if (url.endsWith('/quotes')) { const result = typeof quotes === 'function' ? quotes() : quotes; return result instanceof Error ? Promise.reject(result) : { ok: true, json: async () => result }; }
    if (url.endsWith('/order')) return { ok: true, json: async () => order };
    throw new Error('Unexpected request: ' + url);
  };
  vm.runInNewContext(source, { window, document, fetch, sessionStorage: { getItem: (k) => store.get(k),
    setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) }, URL, URLSearchParams,
    AbortController, setTimeout, clearTimeout, Date });
  await callbacks.DOMContentLoaded();
  await new Promise((resolve) => setImmediate(resolve));
  return { elements, requests, window };
}

const currencies = [{ code: 'USD', amount: '3.99', quote: 'usd-quote' },
  { code: 'EUR', amount: '3.70', quote: 'eur-quote' }];

test('buyer sees the quoted currency and order sends its server quote', async () => {
  const page = await setup({ quotes: { currencies }, order: { currency: 'EUR', amount_value: '3.70',
    order_id: 'ORDER123456789', url: 'https://www.paypal.com/checkoutnow?token=ORDER123456789' } });
  const select = page.elements['#paypalCurrency'];
  assert.equal(page.elements['#paypalCurrencyControl'].hidden, false);
  assert.deepEqual(select.children.map((item) => item.textContent), ['USD 3.99', 'EUR 3.70']);
  select.value = 'EUR';
  select.listeners.change();
  assert.match(page.elements['#paypalStatus'].textContent, /EUR 3.70/);
  await page.elements['[data-buy-paypal]'].listeners.click();
  const request = page.requests.find((item) => item.url.endsWith('/order'));
  assert.deepEqual(JSON.parse(request.options.body), { plan: 'extended', currency: 'EUR', quote: 'eur-quote' });
  assert.match(page.window.location.assigned, /^https:\/\/www\.paypal\.com\//);
});

test('a mismatched price never redirects the buyer to payment', async () => {
  const page = await setup({ quotes: { currencies }, order: { currency: 'EUR', amount_value: '4.70',
    order_id: 'ORDER123456789', url: 'https://www.paypal.com/checkoutnow?token=ORDER123456789' } });
  page.elements['#paypalCurrency'].value = 'EUR';
  await page.elements['[data-buy-paypal]'].listeners.click();
  assert.equal(page.window.location.assigned, undefined);
  assert.match(page.elements['#paypalStatus'].textContent, /price changed/i);
});

test('quote failure preserves USD checkout', async () => {
  const page = await setup({ quotes: new Error('offline'), order: { currency: 'USD', amount_value: '3.99',
    order_id: 'ORDER123456789', url: 'https://www.paypal.com/checkoutnow?token=ORDER123456789' } });
  assert.equal(page.elements['#paypalCurrencyControl'].hidden, true);
  await page.elements['[data-buy-paypal]'].listeners.click();
  assert.deepEqual(JSON.parse(page.requests.find((item) => item.url.endsWith('/order')).options.body),
    { plan: 'extended', currency: 'USD' });
});

test('sign-in shows prices and requires explicit checkout confirmation', async () => {
  const page = await setup({ quotes: { currencies }, signedIn: false });
  await page.elements['[data-buy-paypal]'].listeners.click();
  assert.equal(page.requests.some((item) => item.url.endsWith('/order')), false);
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(page.elements['#paypalStatus'].textContent, /(?:Signed in|One-time)/);
  assert.equal(page.elements['#paypalCurrencyControl'].hidden, false);
});


const yenQuotes = { currencies: [...currencies, { code: 'JPY', amount: '631', quote: 'yen-token' }] };

test('Japanese locale selects a whole-yen quote and sends that quote', async () => {
  const page = await setup({ quotes: yenQuotes, locale: 'ja-JP', order: { currency: 'JPY', amount_value: '631',
    order_id: 'ORDER123456789', url: 'https://www.paypal.com/checkoutnow?token=ORDER123456789' } });
  assert.equal(page.elements['#paypalCurrency'].value, 'JPY');
  assert.match(page.elements['#paypalStatus'].textContent, /JPY 631/);
  await page.elements['[data-buy-paypal]'].listeners.click();
  assert.deepEqual(JSON.parse(page.requests.find((item) => item.url.endsWith('/order')).options.body),
    { plan: 'extended', currency: 'JPY', quote: 'yen-token' });
});

test('currency choice survives retry after user chooses another currency', async () => {
  const page = await setup({ quotes: yenQuotes, locale: 'ja-JP' });
  const select = page.elements['#paypalCurrency'];
  select.value = 'EUR';
  select.listeners.change();
  await page.elements['#retryPayPalCurrencies'].listeners.click();
  assert.equal(select.value, 'EUR');
});

test('failed local currency lookup offers retry and retry restores yen', async () => {
  let calls = 0;
  const page = await setup({ locale: 'ja-JP', quotes: () => ++calls === 1 ? new Error('offline') : yenQuotes });
  assert.equal(page.elements['#retryPayPalCurrencies'].hidden, false);
  assert.match(page.elements['#paypalStatus'].textContent, /temporarily unavailable/);
  await page.elements['#retryPayPalCurrencies'].listeners.click();
  assert.equal(page.elements['#paypalCurrency'].value, 'JPY');
  assert.equal(page.elements['#retryPayPalCurrencies'].hidden, true);
  assert.equal(calls, 2);
});

test('unsupported locale remains USD, with an explicit choice of other currencies', async () => {
  const page = await setup({ locale: 'en-IN', quotes: yenQuotes });
  assert.equal(page.elements['#paypalCurrency'].value, 'USD');
  assert.equal(page.elements['#paypalCurrencyControl'].hidden, false);
});


test('signed USD-only quote response still permits fallback checkout', async () => {
  const page = await setup({ locale: 'ja-JP', quotes: { currencies: [currencies[0]] },
    order: { currency: 'USD', amount_value: '3.99', order_id: 'ORDER123456789',
      url: 'https://www.paypal.com/checkoutnow?token=ORDER123456789' } });
  await page.elements['[data-buy-paypal]'].listeners.click();
  assert.deepEqual(JSON.parse(page.requests.find((item) => item.url.endsWith('/order')).options.body),
    { plan: 'extended', currency: 'USD' });
  assert.match(page.window.location.assigned, /^https:\/\/www\.paypal\.com/);
});

test('retry does not override a currency chosen while quotes are loading', async () => {
  let calls = 0, resolveNext;
  const delayed = new Promise((resolve) => { resolveNext = resolve; });
  const page = await setup({ locale: 'ja-JP', quotes: () => ++calls === 1 ? yenQuotes : delayed });
  const retry = page.elements['#retryPayPalCurrencies'].listeners.click();
  const select = page.elements['#paypalCurrency'];
  select.value = 'EUR';
  select.listeners.change();
  resolveNext(yenQuotes);
  await retry;
  assert.equal(select.value, 'EUR');
});

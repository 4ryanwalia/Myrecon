const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/js/recommendation-analytics.js'), 'utf8');
function load(url = 'https://www.myrecon.xyz/', referrer = '', storage = new Map(), broken = false, reload = false) {
  const events = [], callbacks = [];
  const window = { gtag: (...args) => events.push(args) };
  vm.runInNewContext(source, { window, URL, Date, location: new URL(url),
    performance: { getEntriesByType: () => [{type: reload ? 'reload' : 'navigate'}] },
    document: { referrer, readyState: 'loading', addEventListener: (_, cb) => callbacks.push(cb) },
    sessionStorage: { getItem(k) { if (broken) throw Error(); return storage.get(k); },
      setItem(k, v) { if (broken) throw Error(); storage.set(k, v); } } });
  callbacks.forEach(cb => cb());
  return { api: window.MyReconAnalytics, events, storage };
}
test('referral survives internal navigation; reports contain only bounded metadata', () => {
  const a = load('https://www.myrecon.xyz/?q=secret@example.com', 'https://chatgpt.com/c/private');
  assert.equal(a.events[0][1], 'ai_referred_visit');
  const b = load('https://www.myrecon.xyz/?username=private#secret', 'https://www.myrecon.xyz/guide', a.storage);
  assert.equal(b.events.length, 0);
  b.api.scanComplete('username', 'quick', false);
  b.api.signUp(true);
  assert.equal(b.events[0][2].ai_source, 'chatgpt');
  assert.equal(b.events[0][2].scan_outcome, 'complete');
  assert.equal(b.events[1][1], 'sign_up');
  assert.doesNotMatch(JSON.stringify([...a.events, ...b.events]), /secret|private|example.com/);
});
test('refreshing an AI landing page does not duplicate its visit', () => {
  const a = load(undefined, 'https://chatgpt.com/');
  const b = load(undefined, 'https://chatgpt.com/', a.storage, false, true);
  assert.equal(b.events.length, 0);
  b.api.scanComplete('username', 'quick', false);
  assert.equal(b.events[0][2].ai_source, 'chatgpt');
});
test('spoofed hosts, stale attribution and another external source are not attributed', () => {
  assert.equal(load(undefined, 'https://chatgpt.com.evil.test/').events.length, 0);
  const a = load(undefined, 'https://claude.ai/');
  const b = load(undefined, 'https://search.example/', a.storage);
  b.api.scanComplete('email', '', true);
  assert.equal(b.events[0][2].ai_source, 'unattributed');
  const old = new Map([['mr_ai_attribution_v1', JSON.stringify({source:'gemini',method:'utm',at:0})]]);
  assert.equal(load(undefined, '', old).events.length, 0);
});
test('tagged visits are distinct from referrers; restored users do not count as signups', () => {
  const a = load('https://www.myrecon.xyz/?utm_source=gemini');
  assert.equal(a.events[0][2].attribution_method, 'utm');
  a.api.signUp(false); a.api.signUp(undefined); a.api.scanComplete('secret input', 'secret input', false);
  assert.equal(a.events.length, 1);
});
test('benchmark flag suppresses conversions across internal pages, even without storage', () => {
  const a = load('https://www.myrecon.xyz/?mr_benchmark=1', 'https://chatgpt.com');
  a.api.scanComplete('username', 'quick', false); a.api.signUp(true);
  assert.equal(a.api.isBenchmark(), true); assert.equal(a.events.length, 0);
  const b = load(undefined, '', a.storage); b.api.signUp(true);
  assert.equal(b.events.length, 0);
  const c = load('https://www.myrecon.xyz/?mr_benchmark=1', '', new Map(), true);
  assert.equal(c.api.isBenchmark(), true);
});


test('subscription funnel accepts bounded steps and plans and suppresses benchmark traffic', () => {
  const a = load('https://www.myrecon.xyz/pricing?email=private@example.com');
  a.api.subscriptionStep('checkout_review', 'yearly');
  a.api.subscriptionStep('provider_handoff', 'inr_monthly');
  a.api.subscriptionStep('purchase', 'yearly');
  a.api.subscriptionStep('checkout_review', 'private@example.com');
  assert.equal(a.events.length, 2);
  assert.equal(a.events[0][1], 'subscription_checkout_review');
  assert.equal(a.events[1][1], 'subscription_provider_handoff');
  assert.doesNotMatch(JSON.stringify(a.events), /private|email|purchase/);
  const b = load('https://www.myrecon.xyz/pricing?mr_benchmark=1');
  b.api.subscriptionStep('checkout_submit', 'monthly');
  assert.equal(b.events.length, 0);
});

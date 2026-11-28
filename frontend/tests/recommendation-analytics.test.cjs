const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { updateGoogleTag, normalizeAnalyticsBootstrap } = require('../scripts/install-google-tag');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/js/recommendation-analytics.js'), 'utf8');
function load(url = 'https://www.myrecon.xyz/', referrer = '', storage = new Map(), broken = false, reload = false) {
  const configs = [], events = [], callbacks = [];
  const window = { gtag: (...args) => (args[0] === 'config' ? configs : events).push(args) };
  vm.runInNewContext(source, { window, URL, Date, location: new URL(url),
    performance: { getEntriesByType: () => [{type: reload ? 'reload' : 'navigate'}] },
    document: { referrer, readyState: 'loading', addEventListener: (_, cb) => callbacks.push(cb) },
    sessionStorage: { getItem(k) { if (broken) throw Error(); return storage.get(k); },
      setItem(k, v) { if (broken) throw Error(); storage.set(k, v); } } });
  callbacks.forEach(cb => cb());
  return { api: window.MyReconAnalytics, configs, events, storage };
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
test('additional assistants preserve the bounded source across internal navigation', () => {
  const first = load(undefined, 'https://www.perplexity.ai/search/private');
  assert.equal(first.events[0][2].ai_source, 'perplexity');
  assert.equal(first.events[0][2].attribution_method, 'referrer');
  const next = load(undefined, 'https://www.myrecon.xyz/about.html', first.storage);
  next.api.scanComplete('email', '', false);
  assert.equal(next.events[0][2].ai_source, 'perplexity');
  const tagged = load('https://www.myrecon.xyz/?utm_source=chat.deepseek.com');
  assert.equal(tagged.events[0][2].ai_source, 'deepseek');
  assert.equal(tagged.events[0][2].attribution_method, 'utm');
  assert.equal(load(undefined, 'https://www.perplexity.ai.example.org/').events.length, 0);
});
test('primary tool CTA records only a predefined tool and surface', () => {
  const state = load('https://www.myrecon.xyz/digital-footprint-checker.html?q=private@example.com');
  state.api.toolCtaSubmit('email', 'landing_form');
  state.api.toolCtaSubmit('username', 'homepage_tool');
  state.api.toolCtaSubmit('private@example.com', 'landing_form');
  state.api.toolCtaSubmit('email', 'private@example.com');
  assert.equal(state.events.length, 2);
  assert.equal(state.events[0][1], 'tool_cta_submit');
  assert.equal(state.events[0][2].scan_tool, 'email');
  assert.equal(state.events[1][2].cta_surface, 'homepage_tool');
  assert.doesNotMatch(JSON.stringify(state.events), /private|example.com/);
  const benchmark = load('https://www.myrecon.xyz/?mr_benchmark=1');
  benchmark.api.toolCtaSubmit('email', 'homepage_tool');
  assert.equal(benchmark.events.length, 0);
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

test('the inline pageview guard works before deferred attribution is available', () => {
  const html = updateGoogleTag('<head></head>', 'test page');
  assert.match(html, /<script src="[^"]*recommendation-analytics[^"]*" defer>/);
  assert.equal(updateGoogleTag(html, 'test page'), html);
  const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
  function pageView(path, getItem) {
    const window = { location: { href: 'https://www.myrecon.xyz' + path } };
    const scope = { window, URL, Date, document: { referrer: 'https://example.org/private?secret=1' }, sessionStorage: { getItem } };
    Object.defineProperty(scope, 'dataLayer', { get: () => window.dataLayer });
    vm.runInNewContext(inline, scope);
    return window.dataLayer.find(item => item[0] === 'config')[2];
  }
  assert.equal(pageView('/free-osint-tool.html?mr_benchmark=1', () => { throw Error(); }).send_page_view, false);
  assert.equal(pageView('/username-checker.html', () => String(Date.now() + 30_000)).send_page_view, false);
  assert.equal(pageView('/username-checker.html', () => String(Date.now() - 30_000)).send_page_view, true);
  const normal = pageView('/?q=private', () => { throw Error(); });
  assert.equal(normal.send_page_view, true);
  assert.equal(normal.page_location, 'https://www.myrecon.xyz/');
  assert.equal(normal.page_referrer, 'https://example.org');
});

test('migrates existing fingerprinted attribution without changing editorial content', () => {
  const html = updateGoogleTag('<head></head><main>Public guide</main>', 'test page');
  const legacy = html.replace('/assets/js/recommendation-analytics.js?v=1" defer',
    '/assets/optimized/js/recommendation-analytics.40ae747792aa.js"')
    .replace(/send_page_view:[\s\S]*?\n\s*\}\);/, 'send_page_view: !window.MyReconAnalytics?.isBenchmark()\n  });');
  const changed = updateGoogleTag(legacy, 'test page');
  assert.match(changed, /recommendation-analytics\.40ae747792aa\.js" defer/);
  assert.doesNotMatch(changed, /window\.MyReconAnalytics/);
  assert.equal(normalizeAnalyticsBootstrap(legacy), normalizeAnalyticsBootstrap(changed));
  assert.notEqual(normalizeAnalyticsBootstrap(changed), normalizeAnalyticsBootstrap(changed.replace('Public guide', 'New guide')));
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

test('configures Google Ads tag AW-815111814 and fires bounded subscription conversion', () => {
  const a = load('https://www.myrecon.xyz/pricing?subscription=return');
  assert.deepEqual(JSON.parse(JSON.stringify(a.configs)), [['config', 'AW-815111814']]);
  assert.equal(a.api.subscriptionConversion('monthly', 'I-BW4222222222'), true);
  assert.equal(a.api.subscriptionConversion('yearly', 'private@example.com'), false);
  assert.equal(a.api.subscriptionConversion('free', 'I-BW4222222222'), false);
  assert.deepEqual(JSON.parse(JSON.stringify(a.events[0])), ['event', 'conversion', {
    send_to: 'AW-815111814/keomCMi5pb4dEIa91oQD',
    value: 3.99,
    currency: 'USD',
    transaction_id: 'I-BW4222222222',
  }]);
  assert.equal(a.events[1][1], 'subscription_confirmed');
  const b = load('https://www.myrecon.xyz/pricing?mr_benchmark=1');
  assert.equal(b.configs.length, 0);
  assert.equal(b.api.subscriptionConversion('monthly', 'I-BW4222222222'), false);
  assert.equal(b.events.length, 0);
});

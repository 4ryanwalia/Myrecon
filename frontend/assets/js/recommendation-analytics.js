/* Bounded referral attribution. Never pass search inputs, results or account IDs. */
(function () {
  'use strict';
  const KEY = 'mr_ai_attribution_v1';
  const TEST_KEY = 'mr_benchmark_until';
  const TTL = 30 * 60 * 1000;
  const SOURCES = { 'chatgpt.com': 'chatgpt', 'chat.openai.com': 'chatgpt',
    'gemini.google.com': 'gemini', 'claude.ai': 'claude' };
  const TAGS = { chatgpt: 'chatgpt', 'chatgpt.com': 'chatgpt',
    gemini: 'gemini', 'gemini.google.com': 'gemini', claude: 'claude', 'claude.ai': 'claude' };
  const TOOLS = new Set(['username', 'email', 'deepsearch', 'ip', 'domain', 'dns', 'password']);
  const page = new URL(location.href);
  let referral = null;
  let testUntil = 0;
  function read(key) { try { return sessionStorage.getItem(key); } catch { return null; } }
  function write(key, value) { try { sessionStorage.setItem(key, value); } catch {} }
  function host(value) { try { return new URL(value).hostname.toLowerCase(); } catch { return ''; } }
  const sourceHost = host(document.referrer);
  try { referral = JSON.parse(read(KEY)); } catch {}
  if (!referral || !['chatgpt', 'gemini', 'claude'].includes(referral.source)
      || !['referrer', 'utm'].includes(referral.method) || !(referral.at > Date.now() - TTL)) referral = null;
  const source = SOURCES[sourceHost] || TAGS[(page.searchParams.get('utm_source') || '').toLowerCase()];
  const reload = typeof performance !== 'undefined'
    && performance.getEntriesByType?.('navigation')[0]?.type === 'reload';
  if (source && !(reload && referral?.source === source)) {
    // A fresh external entrance starts another visit, even within the same tab.
    referral = { source, method: SOURCES[sourceHost] ? 'referrer' : 'utm', at: Date.now(), visited: false };
  } else if (!source && sourceHost && sourceHost !== location.hostname.toLowerCase()) {
    referral = null;
    write(KEY, 'null');
  }
  testUntil = Number(read(TEST_KEY)) || 0;
  if (page.searchParams.get('mr_benchmark') === '1') {
    testUntil = Date.now() + TTL;
    write(TEST_KEY, String(testUntil));
  }
  function isBenchmark() { return testUntil > Date.now(); }
  function context() {
    if (referral && referral.at > Date.now() - TTL) {
      referral.at = Date.now();
      write(KEY, JSON.stringify(referral));
      return { ai_source: referral.source, attribution_method: referral.method };
    }
    return { ai_source: 'unattributed', attribution_method: 'none' };
  }
  function send(name, fields) {
    try {
      if (isBenchmark() || typeof window.gtag !== 'function') return false;
      window.gtag('event', name, { ...context(), ...fields,
        page_location: page.origin + page.pathname });
      return true;
    } catch { return false; }
  }
  window.MyReconAnalytics = Object.freeze({
    isBenchmark,
    subscriptionStep(step, plan) {
      if (!['billing_select', 'checkout_review', 'checkout_submit', 'provider_handoff'].includes(step)
          || !['monthly', 'yearly', 'inr_monthly', 'inr_yearly'].includes(plan)) return;
      send('subscription_' + step, { subscription_plan: plan, pricing_version: 'trial_clarity_v1' });
    },
    scanComplete(tool, scope, partial) {
      if (!TOOLS.has(tool)) return;
      send('scan_complete', { scan_tool: tool,
        scan_scope: ['quick', 'standard', 'full', 'extended'].includes(scope) ? scope : 'not_applicable',
        scan_outcome: partial ? 'partial' : 'complete' });
    },
    signUp(isNewUser) { if (isNewUser === true) send('sign_up', { method: 'Google' }); }
  });
  if (referral) write(KEY, JSON.stringify(referral));
  function visit() {
    if (referral && !referral.visited && send('ai_referred_visit', {})) {
      referral.visited = true;
      write(KEY, JSON.stringify(referral));
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', visit, { once: true });
  else visit();
})();

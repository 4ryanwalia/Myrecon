/* Bounded referral attribution. Never pass search inputs, results or account IDs. */
(function () {
  'use strict';
  const KEY = 'mr_ai_attribution_v1';
  const TEST_KEY = 'mr_benchmark_until';
  const TTL = 30 * 60 * 1000;
  const SOURCES = new Map(Object.entries({
    'chatgpt.com': 'chatgpt',
    'chat.openai.com': 'chatgpt',
    'gemini.google.com': 'gemini',
    'claude.ai': 'claude',
    'perplexity.ai': 'perplexity',
    'chat.deepseek.com': 'deepseek',
    'copilot.microsoft.com': 'copilot',
    'grok.com': 'grok',
    'meta.ai': 'meta_ai',
    'chat.mistral.ai': 'mistral',
    'you.com': 'you',
  }));
  const SOURCE_NAMES = new Set(SOURCES.values());
  const TOOLS = new Set(['username', 'email', 'deepsearch', 'ip', 'domain', 'dns', 'password']);
  const page = new URL(location.href);
  let referral = null;
  let testUntil = 0;
  function read(key) { try { return sessionStorage.getItem(key); } catch { return null; } }
  function write(key, value) { try { sessionStorage.setItem(key, value); } catch {} }
  function host(value) { try { return new URL(value).hostname.toLowerCase(); } catch { return ''; } }
  function sourceForHost(hostname) { return SOURCES.get(hostname.replace(/^www\./, '')); }
  const sourceHost = host(document.referrer);
  try { referral = JSON.parse(read(KEY)); } catch {}
  if (!referral || !SOURCE_NAMES.has(referral.source)
      || !['referrer', 'utm'].includes(referral.method) || !(referral.at > Date.now() - TTL)) referral = null;
  const referrerSource = sourceForHost(sourceHost);
  const tag = (page.searchParams.get('utm_source') || '').toLowerCase();
  const source = referrerSource || (SOURCE_NAMES.has(tag) ? tag : sourceForHost(tag));
  const reload = typeof performance !== 'undefined'
    && performance.getEntriesByType?.('navigation')[0]?.type === 'reload';
  if (source && !(reload && referral?.source === source)) {
    // A fresh external entrance starts another visit, even within the same tab.
    referral = { source, method: referrerSource ? 'referrer' : 'utm', at: Date.now(), visited: false };
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
  const ADS_ID = 'AW-815111814';
  const ADS_SUBSCRIPTION_SEND_TO = 'AW-815111814/keomCMi5pb4dEIa91oQD';
  const PLAN_VALUES = {
    monthly: { value: 3.99, currency: 'USD' },
    yearly: { value: 19.99, currency: 'USD' },
    inr_monthly: { value: 299, currency: 'INR' },
    inr_yearly: { value: 1999, currency: 'INR' },
  };
  const SUBSCRIPTION_ID_RE = /^(?:I-[A-Z0-9]{6,32}|sub_[A-Za-z0-9]{6,32})$/;
  let adsConfigured = false;
  function configureAds() {
    try {
      if (adsConfigured || isBenchmark() || typeof window.gtag !== 'function') return false;
      window.gtag('config', ADS_ID);
      adsConfigured = true;
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
    subscriptionConversion(plan, subscriptionId) {
      const price = PLAN_VALUES[plan];
      if (!price || !SUBSCRIPTION_ID_RE.test(String(subscriptionId || ''))) return false;
      try {
        if (isBenchmark() || typeof window.gtag !== 'function') return false;
        configureAds();
        window.gtag('event', 'conversion', {
          send_to: ADS_SUBSCRIPTION_SEND_TO,
          value: price.value,
          currency: price.currency,
          transaction_id: subscriptionId,
        });
        send('subscription_confirmed', {
          subscription_plan: plan,
          value: price.value,
          currency: price.currency,
          transaction_id: subscriptionId,
        });
        return true;
      } catch { return false; }
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
    configureAds();
    if (referral && !referral.visited && send('ai_referred_visit', {})) {
      referral.visited = true;
      write(KEY, JSON.stringify(referral));
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', visit, { once: true });
  else visit();
})();

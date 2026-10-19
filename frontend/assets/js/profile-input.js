/* Local-only profile parsing. No URL is fetched or followed. */
(function(root) {
  "use strict";
  const rules = [{"platform": "Instagram", "hosts": ["instagram.com", "www.instagram.com"], "host": "www.instagram.com", "prefix": "", "pattern": "[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?"}, {"platform": "TikTok", "hosts": ["tiktok.com", "www.tiktok.com"], "host": "www.tiktok.com", "prefix": "@", "pattern": "[A-Za-z0-9_][A-Za-z0-9_.]{0,22}[A-Za-z0-9_]|[A-Za-z0-9_]"}, {"platform": "GitHub", "hosts": ["github.com", "www.github.com"], "host": "github.com", "prefix": "", "pattern": "[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"}];
  const reserved = new Set(" about abuse account accounts ads advertise ai api app apps archive article articles auth blog blogs board brand business careers cart categories category challenge channel channels chat checkout cloud codespaces collection collections comment comments community companies company compare contact content cookie cookies copilot corporate courses create creator customer-stories dashboard de developer developers digital direct directory discover docs documentation download downloads edit editor education en enterprise es events explore faq features feed feedback files forum forums fr gallery get gift group groups guide guides hashtag help home hot how i images index info insights install intent invite issues it ja jobs join learn legal library license links list lists live login logout m magazine mail main map maps marketing marketplace media members menu message messages mobile more my new news newsletter notifications oauth offers onboarding opensource order orders organizations orgs p page pages partner partners password payment photo photos plans platform podcast podcasts policies policy post posts premium press pricing privacy product products profile profiles projects pt pulls pulse questions read readme recent redirect reel reels register release releases reset resources results reviews roadmap rss ru s sale search security services session sessions settings share shop shopping showcase signin signup site sitemap solutions source sponsor sponsors start static status store stories story subscribe support tag tags team teams terms test themes topic topics tos tour trending tv u upgrade upload user users video videos view wallet watch web welcome wiki work world write www zh".split(' '));
  const error = 'Paste a full Instagram, TikTok, or GitHub profile URL (not a post, video, short link, or search page), or enter a username.';
  function parse(raw) {
    const value = String(raw || '').trim();
    if (!value || value.length > 8192 || /[\x00-\x1f\x7f\\]/.test(value)) return {error};
    if (!/^[a-z][a-z0-9+.-]*:/i.test(value) && !value.includes('/')) {
      const handle = value.replace(/^@/, '');
      return /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$/.test(handle) && !value.startsWith('www.') ? {handle} : {error};
    }
    try {
      const u = new URL(value);
      const rule = rules.find(r => r.hosts.includes(u.hostname));
      // Check raw route too: URL normalisation must not turn /post/../alice into a profile.
      const route = value.match(/^https?:\/\/[^/?#]+([^?#]*)/i)?.[1];
      if (!rule || !/^https?:$/.test(u.protocol) || u.username || u.password || u.port || !route || /[%\\]/.test(route)) return {error};
      const match = new RegExp('^/' + rule.prefix + '(' + rule.pattern + ')/?$').exec(route);
      const handle = match?.[1];
      if (!handle || reserved.has(handle.toLowerCase()) || handle.includes('..') || (rule.platform === 'GitHub' && handle.includes('--'))) return {error};
      return {handle, platform: rule.platform, url: 'https://' + rule.host + '/' + rule.prefix + handle};
    } catch (_) { return {error}; }
  }
  function shared(raw) {
    const text = String(raw || '').trim();
    const links = text.match(/https?:\/\/[^\s<>]+/gi) || [];
    if (links.length > 1) return {error: 'Multiple links: select one profile link or correct the input before scanning.', choices: links};
    return parse(links.length === 1 ? links[0] : text);
  }
  function autoGate() { let last = null; return {accept(p) { if (!p.url || last === p.url) return false; last = p.url; return true; }, reset() {last = null;} }; }
  const api = {parse, shared, autoGate};
  if (typeof module !== 'undefined') module.exports = api;
  root.MyReconProfileInput = api;
})(typeof window !== 'undefined' ? window : globalThis);

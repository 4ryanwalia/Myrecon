/* MyRecon, Android app nudge.
 *
 * A small card in the bottom-right corner on computers, or a slim bar at the
 * bottom on Android phones (and on any window under 760px, where the card
 * would sit on top of the tool), pointing at the Play listing. iPhones and
 * other mobiles get nothing, because there is no app for them.
 *
 * Installed on every public page by scripts/install-app-nudge.js, so it
 * carries its own styles instead of relying on a page stylesheet.
 *
 * Rules it keeps, so it never gets in the way of a lookup:
 *  - waits a few seconds, and keeps waiting while a field has focus, a scan
 *    is running, a dialog or Google's consent message is open, or the
 *    search panel sits in the corner it would cover;
 *  - never takes focus, never hides content (the page gets bottom padding
 *    while the bar is up), and lifts the app.js toasts above itself;
 *  - X hides it for 14 days, the Play button for 30;
 *  - skipped on the app, pricing, badge and console pages, inside iframes
 *    and inside an Android WebView.
 *
 * Copy rule: say what the app does, never compare it with the website's
 * privacy. Each claim was checked against the app source on 2026-11-20: the
 * username scan (560 sites, PlatformCatalogue.ALL, free) runs on the phone,
 * and history is stored only on the device (ReconStore + HistoryArchive,
 * with backup and device transfer excluded in res/xml). Do not widen it to
 * "all lookups run on your phone": profile enrichment, email linked accounts
 * and the email/domain/IP fallbacks call the MyRecon backend. Do not add
 * "nothing is shared" or "no data collected": the app shows ads.
 */
(function () {
  "use strict";

  var ua = navigator.userAgent || "";
  var path = location.pathname.replace(/\.html$/, "").replace(/\/+$/, "") || "/";
  var android = /Android/i.test(ua);
  var otherMobile = !android && (/iPhone|iPad|iPod|Mobile|Silk|Kindle|BlackBerry|Opera Mini/i.test(ua) ||
    (navigator.maxTouchPoints > 1 && /Macintosh/.test(ua)));
  if (otherMobile) return;
  if (android && /; wv\)/.test(ua)) return;
  try { if (window.top !== window.self) return; } catch (e) { return; }
  if (/^\/(app|pricing|badge|worker-console|api)(\/|$)/.test(path)) return;
  if (document.querySelector(".app-nudge")) return;

  var KEY = "myrecon-app-nudge-until";
  try {
    if (Number(localStorage.getItem(KEY) || 0) > Date.now()) return;
  } catch (e) { /* storage blocked: still shown, X still closes it on this page */ }

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var root = document.documentElement;
  var platform = android ? "android" : "desktop";
  var PLAY = "https://play.google.com/store/apps/details?id=com.Myrecon.osint&referrer=" +
    encodeURIComponent("utm_source=myrecon.xyz&utm_medium=website&utm_campaign=web_nudge_" + platform);

  var CSS =
    ".app-nudge{position:fixed;z-index:290;right:20px;bottom:20px;box-sizing:border-box;background:var(--surface,#1d1d1d);color:var(--text,#fff);" +
    "border:1px solid var(--border-strong,#525252);border-radius:var(--radius-lg,14px);font-family:var(--font,system-ui,sans-serif);text-align:left;" +
    "opacity:0;transform:translateY(12px);transition:opacity .25s ease,transform .25s ease}" +
    ".app-nudge.is-in{opacity:1;transform:none}" +
    ".app-nudge p{margin:0}" +
    ".app-nudge-card{width:304px;padding:12px 14px 16px 16px}" +
    ".app-nudge-head{display:flex;align-items:center;gap:8px}" +
    ".app-nudge-icon{display:inline-flex;flex:none;color:var(--accent-text,currentColor)}" +
    ".app-nudge-kicker{font:600 11px/1.2 var(--mono,monospace);letter-spacing:.08em;text-transform:uppercase;color:var(--text-mute,#a3a3a3)}" +
    ".app-nudge-close{margin-left:auto;display:inline-flex;align-items:center;justify-content:center;flex:none;width:28px;height:28px;padding:0;" +
    "border:0;border-radius:var(--radius-sm,6px);background:transparent;color:var(--text-mute,#a3a3a3);cursor:pointer}" +
    ".app-nudge-close:hover{color:var(--text,#fff);background:var(--bg-soft,#181818)}" +
    ".app-nudge-close:focus-visible,.app-nudge-cta:focus-visible{outline:2px solid var(--accent,#fff);outline-offset:2px}" +
    ".app-nudge-card .app-nudge-title{margin:10px 0 4px;font-size:16px;font-weight:700;line-height:1.3}" +
    ".app-nudge-card .app-nudge-text{margin:0 0 12px;font-size:13px;line-height:1.5;color:var(--text-dim,#c5c5c5)}" +
    ".app-nudge-cta{display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;min-height:38px;padding:0 14px;" +
    "border-radius:var(--radius,10px);background:var(--burgundy,#6d001a);color:#fff!important;font-size:14px;font-weight:600;" +
    "text-decoration:none!important;white-space:nowrap}" +
    ".app-nudge-cta:hover{background:var(--burgundy-hover,#850022)}" +
    ".app-nudge-card .app-nudge-cta{width:100%}" +
    ".app-nudge-bar{left:10px;right:10px;bottom:calc(10px + env(safe-area-inset-bottom,0px));display:flex;align-items:center;gap:10px;padding:10px 4px 10px 12px}" +
    ".app-nudge-copy{display:grid;gap:2px;min-width:0;flex:1}" +
    ".app-nudge-bar .app-nudge-title{font-size:14px;font-weight:700;line-height:1.25}" +
    ".app-nudge-bar .app-nudge-text{font-size:12px;line-height:1.35;color:var(--text-dim,#c5c5c5)}" +
    ".app-nudge-bar .app-nudge-cta{min-height:36px;padding:0 12px;font-size:13px}" +
    ".app-nudge-bar .app-nudge-close{width:32px;height:32px;margin-left:0}" +
    "html.has-app-nudge-bar body{padding-bottom:var(--app-nudge-space,80px)}" +
    "html.has-app-nudge .toasts{bottom:calc(20px + var(--app-nudge-space,0px))}" +
    "@media (max-width:360px){.app-nudge-bar .app-nudge-text{display:none}}" +
    "@media print{.app-nudge{display:none!important}}" +
    "@media (prefers-reduced-motion:reduce){.app-nudge{transition:none;transform:none}}";

  var ICON = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10.5 18.5h3"/><circle cx="12" cy="10.5" r="3"/><path d="m14.2 12.7 1.8 1.8"/></svg>';
  var CLOSE = '<button type="button" class="app-nudge-close" aria-label="Hide for now"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>';

  var box;
  var bar = false;

  function track(name) {
    try {
      // Same rule as recommendation-analytics.js: benchmark runs are not visitors.
      var a = window.MyReconAnalytics;
      if (a && typeof a.isBenchmark === "function" && a.isBenchmark()) return;
      if (typeof window.gtag === "function") window.gtag("event", name, { nudge_platform: platform });
    } catch (e) { /* optional */ }
  }

  function snooze(days) {
    try { localStorage.setItem(KEY, String(Date.now() + days * 864e5)); } catch (e) { /* optional */ }
  }

  function busy() {
    var a = document.activeElement;
    if (a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.tagName === "SELECT" || a.isContentEditable)) return true;
    if (document.querySelector("#runBtn[disabled], dialog[open]")) return true;
    var cmp = document.querySelector(".fc-consent-root");
    if (cmp && cmp.getClientRects().length) return true;
    return document.hidden || overTool();
  }

  // Never land on top of the search panel: on the homepage the corner card
  // covered the scan-size options and the phone bar covered Investigate.
  // Wait until the visitor has scrolled the panel out of that corner.
  function overTool() {
    var panel = document.getElementById("toolPanel");
    if (!panel) return false;
    var r = panel.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    var w = window.innerWidth;
    var h = window.innerHeight;
    var narrow = android || w < 760;
    var left = narrow ? 0 : w - 344;
    var top = h - (narrow ? 100 : 260);
    return r.left < w && r.right > left && r.top < h && r.bottom > top;
  }

  function place() {
    if (box) root.style.setProperty("--app-nudge-space", (box.offsetHeight + 16) + "px");
  }

  function build() {
    if (!document.getElementById("app-nudge-style")) {
      var style = document.createElement("style");
      style.id = "app-nudge-style";
      style.textContent = CSS;
      document.head.appendChild(style);
    }
    bar = android || window.innerWidth < 760;
    box = document.createElement("aside");
    box.className = "app-nudge " + (bar ? "app-nudge-bar" : "app-nudge-card");
    box.setAttribute("aria-label", "MyRecon for Android");
    box.innerHTML = bar
      ? '<span class="app-nudge-icon">' + ICON + '</span>' +
        '<span class="app-nudge-copy"><span class="app-nudge-title">Get the free MyRecon app</span>' +
        '<span class="app-nudge-text">560 sites per username scan, run from your phone.</span></span>' +
        '<a class="app-nudge-cta" href="' + PLAY + '" target="_blank" rel="noopener">Get app</a>' + CLOSE
      : '<div class="app-nudge-head"><span class="app-nudge-icon">' + ICON + '</span>' +
        '<span class="app-nudge-kicker">MyRecon for Android</span>' + CLOSE + '</div>' +
        '<p class="app-nudge-title">Also on your phone, free</p>' +
        '<p class="app-nudge-text">The username scan checks 560 sites from your phone, and your search history is saved only on your device. No account needed.</p>' +
        '<a class="app-nudge-cta" href="' + PLAY + '" target="_blank" rel="noopener">Get it on Google Play</a>';
  }

  function hide(days, eventName) {
    snooze(days);
    track(eventName);
    box.classList.remove("is-in");
    root.classList.remove("has-app-nudge", "has-app-nudge-bar");
    window.removeEventListener("resize", place);
    setTimeout(function () { if (box.parentNode) box.parentNode.removeChild(box); }, reduce ? 0 : 260);
  }

  function show() {
    if (busy()) { setTimeout(show, 3000); return; }
    build();
    document.body.appendChild(box);
    place();
    root.classList.add("has-app-nudge");
    if (bar) root.classList.add("has-app-nudge-bar");
    requestAnimationFrame(function () { requestAnimationFrame(function () { box.classList.add("is-in"); }); });
    window.addEventListener("resize", place, { passive: true });
    box.querySelector(".app-nudge-close").addEventListener("click", function () { hide(14, "app_nudge_dismiss"); });
    box.querySelector(".app-nudge-cta").addEventListener("click", function () { hide(30, "app_nudge_click"); });
    track("app_nudge_view");
  }

  // Later pages in the same visit show it sooner; the first page lets the
  // visitor start reading or searching first.
  var first = true;
  try {
    first = sessionStorage.getItem("myrecon-app-nudge-seen") !== "1";
    sessionStorage.setItem("myrecon-app-nudge-seen", "1");
  } catch (e) { /* optional */ }
  setTimeout(show, first ? 7000 : 2500);
})();

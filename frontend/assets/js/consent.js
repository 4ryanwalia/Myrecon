/* Cookie / advertising consent controls.
 *
 * WHY THERE IS NO BANNER IN THIS FILE
 * -----------------------------------
 * The only cookies this site causes are Google's advertising cookies, and
 * Google's EU user consent policy requires a Google-certified CMP for ads
 * served to the EEA, the UK and Switzerland. A hand-rolled banner is not
 * certified, so writing one here would not make the site compliant — it
 * would add a second, non-binding prompt in front of the real one and
 * double-ask everyone. The certified message is enabled in the AdSense
 * console (Privacy & messaging → GDPR / "EU regulations"); see
 * LEGAL-CHECKLIST.md, which tracks that it is switched on.
 *
 * WHAT THIS FILE IS FOR
 * ---------------------
 * Consent has to be as easy to withdraw as it was to give, which the CMP
 * alone does not give you: once dismissed, its message never reappears.
 * This wires a "Cookie settings" control to the CMP's own revocation flow so
 * a visitor can reopen it from any page, and — when no CMP is on the page,
 * as outside the EEA where no ad-consent prompt is shown — lets the control
 * behave as the plain link to the cookie policy that it is in the markup.
 *
 * The rule throughout: never swallow the click unless something actually
 * opened. A consent control that does nothing is worse than no control.
 */
(function () {
  "use strict";

  var SELECTOR = "[data-cookie-settings]";

  function hasGoogleFc() {
    return !!(window.googlefc && typeof window.googlefc.showRevocationMessage === "function");
  }

  function hasTcf() {
    return typeof window.__tcfapi === "function";
  }

  function cmpPresent() {
    return hasGoogleFc() || hasTcf();
  }

  /* Returns true if a consent UI was actually opened, so the caller knows
   * whether it is safe to suppress the link's own navigation.
   *
   * `onFail` covers the awkward middle case: a CMP that exposes __tcfapi but
   * does not implement `displayConsentUi`, which is a Google extension rather
   * than a TCF v2 command. There the call is accepted and then quietly does
   * nothing, which would leave the visitor clicking a dead control. So we
   * watch for the callback reporting failure, and treat silence as failure
   * too, falling back to the cookie policy either way.
   */
  function openCmp(onFail) {
    if (hasGoogleFc()) {
      try {
        window.googlefc.showRevocationMessage();
        return true;
      } catch (e) { /* fall through */ }
    }
    if (hasTcf()) {
      try {
        var settled = false;
        window.__tcfapi("displayConsentUi", 2, function (_result, success) {
          settled = true;
          if (success === false) onFail();
        });
        window.setTimeout(function () { if (!settled) onFail(); }, 600);
        return true;
      } catch (e) { /* fall through */ }
    }
    return false;
  }

  function wire() {
    var nodes = document.querySelectorAll(SELECTOR);
    if (!nodes.length) return;

    Array.prototype.forEach.call(nodes, function (el) {
      el.addEventListener("click", function (event) {
        var href = el.getAttribute("href");
        var fallback = function () { if (href) window.location.href = href; };
        // Only take over the click if a consent UI really opened. Otherwise
        // let the element stay the ordinary link it is in the markup, which
        // is also exactly what happens with JavaScript disabled.
        if (openCmp(fallback)) event.preventDefault();
      });
    });

    /* The label is honest about which of the two it will do. It starts as
     * "Cookie policy" — the no-JS, no-CMP truth — and is promoted only once a
     * CMP has actually loaded. adsbygoogle.js is async, so poll briefly
     * rather than assuming it has arrived by DOMContentLoaded. It is the last
     * item in the footer, so a late relabel shifts nothing before it. */
    var tries = 0;
    (function poll() {
      if (cmpPresent()) {
        Array.prototype.forEach.call(nodes, function (el) {
          el.textContent = "Cookie settings";
        });
        return;
      }
      if (++tries < 20) window.setTimeout(poll, 250);
    })();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();

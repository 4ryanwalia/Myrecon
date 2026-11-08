/* PayPal redirects approve the order; only our backend can confirm and grant it. */
(function () {
  "use strict";
  const A = window.MyReconAccount;
  const base = (window.MYRECON || {}).apiBase || "";
  const savedKey = "mr_paypal_checkout";
  const intentKey = "mr_paypal_signin";
  const read = (key) => { try { return JSON.parse(sessionStorage.getItem(key)); } catch { return null; } };
  const save = (key, data) => { try { data ? sessionStorage.setItem(key, JSON.stringify(data)) : sessionStorage.removeItem(key); } catch {} };
  let available = false, busy = false, resumed = false;
  let currencies = [{ code: "USD", amount: "3.99" }], quoteUser = null, quoteTime = 0, quotePromise = null;
  let explicitCurrency = null, localPricesUnavailable = false, unavailablePreferred = null;
  const button = () => document.querySelector("[data-buy-paypal]");
  const selector = () => document.querySelector("#paypalCurrency");
  const retry = () => document.querySelector("#retryPayPalCurrencies");
  const message = (text) => { document.querySelector("#paypalStatus").textContent = text; };
  const selected = () => currencies.find((item) => item.code === selector()?.value) || currencies[0];
  const priceText = (item) => `${item.code} ${item.amount}`;
  const readyMessage = () => localPricesUnavailable
    ? "Local-currency prices are temporarily unavailable. Pay USD 3.99 or refresh to try again."
    : unavailablePreferred && selected().code === "USD"
      ? `${unavailablePreferred} is temporarily unavailable. Choose another currency or continue with USD.`
      : `One-time ${priceText(selected())} payment through PayPal. Review the total at PayPal.`;
  // Language is only a starting preference, not proof of the buyer's location.
  const defaultCurrency = () => {
    const locale = (window.navigator?.language || "").replace(/_/g, "-");
    let region = "";
    try { region = new Intl.Locale(locale).region || ""; } catch {}
    const byRegion = {
      JP: "JPY", GB: "GBP", US: "USD", AU: "AUD", CA: "CAD", CH: "CHF", CZ: "CZK",
      DK: "DKK", HK: "HKD", HU: "HUF", IL: "ILS", MX: "MXN", NO: "NOK", NZ: "NZD",
      PH: "PHP", PL: "PLN", SE: "SEK", SG: "SGD", TH: "THB", TW: "TWD",
      AT: "EUR", BE: "EUR", HR: "EUR", CY: "EUR", EE: "EUR", FI: "EUR", FR: "EUR",
      DE: "EUR", GR: "EUR", IE: "EUR", IT: "EUR", LV: "EUR", LT: "EUR", LU: "EUR",
      MT: "EUR", NL: "EUR", PT: "EUR", SK: "EUR", SI: "EUR", ES: "EUR"
    };
    return byRegion[region.toUpperCase()] || (!region && /^ja$/i.test(locale) ? "JPY" : "USD");
  };
  const update = () => {
    button().disabled = busy || !available || !A?.enabled;
    if (selector()) selector().disabled = busy;
  };

  function renderCurrencies(items, preferred) {
    currencies = items;
    const select = selector();
    const control = document.querySelector("#paypalCurrencyControl");
    if (!select || !control) return;
    select.replaceChildren();
    for (const item of currencies) {
      const option = document.createElement("option");
      option.value = item.code;
      option.textContent = priceText(item);
      select.appendChild(option);
    }
    select.value = currencies.some((item) => item.code === preferred) ? preferred : "USD";
    control.hidden = currencies.length < 2;
    button().setAttribute("aria-label", `Pay ${priceText(selected())} with PayPal`);
  }

  async function loadQuotes(uid, force = false) {
    if (!force && quoteUser === uid && quoteTime && Date.now() - quoteTime < 10 * 60 * 1000) return;
    if (quotePromise && quoteUser === uid) return quotePromise;
    quoteUser = uid;
    const pending = (async () => {
      const preferred = explicitCurrency || read(intentKey)?.currency || defaultCurrency();
      let items = [{ code: "USD", amount: "3.99" }];
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 35000);
      try {
        const headers = await A.authHeaders();
        const response = await fetch(base + "/api/billing/paypal/quotes", { headers, signal: controller.signal });
        if (!response.ok) throw new Error("Quotes unavailable");
        const data = await response.json();
        const offered = (Array.isArray(data.currencies) ? data.currencies : []).filter((item) =>
          /^[A-Z]{3}$/.test(item.code) && /^\d+(?:\.\d{1,2})?$/.test(item.amount)
          && (item.code === "USD" || (typeof item.quote === "string" && item.quote.length > 0)));
        if (offered.some((item) => item.code === "USD")) items = offered;
      } catch {} finally { clearTimeout(timer); } // USD remains available if local-currency quotes cannot be loaded.
      if (A.state().user?.uid !== uid) return;
      localPricesUnavailable = items.length < 2;
      if (localPricesUnavailable) items = [{ code: "USD", amount: "3.99" }];
      const currentPreference = explicitCurrency || preferred;
      unavailablePreferred = currentPreference !== "USD" && !items.some((item) => item.code === currentPreference) ? currentPreference : null;
      renderCurrencies(items, currentPreference);
      if (retry()) retry().hidden = !localPricesUnavailable && !unavailablePreferred;
      // A failed refresh is not a valid cached quote; retry can fetch fresh rates.
      quoteTime = localPricesUnavailable ? 0 : Date.now();
    })();
    quotePromise = pending;
    try { await pending; } finally { if (quotePromise === pending) quotePromise = null; }
  }

  async function post(path, body) {
    const controller = new AbortController();
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new Error("PayPal is taking too long. Refresh this page to check again; do not pay twice.")); }, 30000);
    });
    try {
      return await Promise.race([(async () => {
        const headers = await A.authHeaders();
        controller.signal.throwIfAborted();
        const response = await fetch(base + path, { method: "POST", signal: controller.signal,
          headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(body) });
        const data = await response.json();
        if (!response.ok || data.status === "error") throw new Error(data.error || "PayPal is unavailable. Try again later.");
        return data;
      })(), timeout]);
    } finally { clearTimeout(timer); }
  }

  function approvalUrl(value) {
    const url = new URL(value);
    if (url.protocol !== "https:" || !["www.paypal.com", "www.sandbox.paypal.com"].includes(url.hostname)
        || url.username || url.password || (url.port && url.port !== "443")) throw new Error("Invalid PayPal checkout link.");
    return url.href;
  }

  async function buy() {
    if (busy || !available) return;
    busy = true;
    update();
    try {
      if (!A.state().user) {
        save(intentKey, { at: Date.now(), currency: explicitCurrency });
        message("Sign in with Google to see your PayPal currency options.");
        await A.signIn();
        const uid = A.state().user?.uid;
        if (!uid) { save(intentKey, null); message("Sign-in was cancelled. You can try again."); return; }
        message("Signed in. Checking local-currency prices; USD is available while you wait.");
        loadQuotes(uid, true).then(() => {
          if (!busy && A.state().user?.uid === uid) message(readyMessage());
        });
        save(intentKey, null);
        return;
      }
      const uid = A.state().user?.uid;
      // The server accepts the existing USD price without a quote, including
      // while local prices are loading or unavailable.
      const usingUsdFallback = selected().code === "USD" && !selected().quote;
      if (!usingUsdFallback && (quoteUser !== uid || !quoteTime || Date.now() - quoteTime >= 10 * 60 * 1000)) {
        await loadQuotes(uid, true);
        message(`Prices refreshed. ${readyMessage()}`);
        return;
      }
      save(intentKey, null);
      message("Opening PayPal checkout…");
      const choice = selected();
      const result = await post("/api/billing/paypal/order", { plan: "extended", currency: choice.code, ...(choice.quote ? { quote: choice.quote } : {}) });
      if (A.state().user?.uid !== uid) return;
      const amountMatches = result.amount_value === choice.amount
        || (choice.code === "USD" && choice.amount === "3.99" && result.amount_value == null && result.amount === 399);
      if (result.currency !== choice.code || !amountMatches) {
        throw new Error("The checkout price changed. No payment was taken. Refresh the page and review the price again.");
      }
      const url = approvalUrl(result.url);
      if (!/^[A-Z0-9]{10,32}$/.test(result.order_id)) throw new Error("Invalid PayPal order.");
      save(savedKey, { uid, order_id: result.order_id });
      window.location.assign(url);
    } catch (error) {
      save(intentKey, null);
      message(A.friendly(error) || "Sign-in was cancelled. You can try again.");
    } finally { busy = false; update(); }
  }

  async function check() {
    if (busy) return;
    const uid = A?.state().user?.uid;
    const saved = read(savedKey);
    const query = new URLSearchParams(window.location.search);
    const orderId = query.get("paypal") === "return" ? query.get("token") : saved?.uid === uid ? saved.order_id : null;
    if (!uid) { message("Sign in to the account used for checkout to confirm your PayPal payment."); return; }
    if (!orderId) { message("No PayPal checkout found in this tab. If you already paid, contact support with your receipt."); return; }
    busy = true;
    update();
    message("Confirming your PayPal payment…");
    try {
      const result = await post("/api/billing/paypal/capture", { order_id: orderId });
      if (A.state().user?.uid !== uid) return;
      if (result.applied) {
        save(savedKey, null);
        const url = new URL(window.location.href);
        ["paypal", "token", "PayerID"].forEach((key) => url.searchParams.delete(key));
        window.history.replaceState(null, "", url.pathname + url.search + url.hash);
        message("Payment confirmed. Your pack includes 10 added Extended credits, unlimited standard scans and Deep Search.");
        await A.refreshAccount();
      } else {
        save(savedKey, { uid, order_id: orderId });
        message("PayPal has not confirmed a completed payment yet. Refresh this page in a moment. If you paid, do not pay again.");
      }
    } catch (error) {
      if (A.state().user?.uid === uid) message(A.friendly(error) + " If you already paid, refresh this page to check again; do not pay twice.");
    } finally { busy = false; update(); }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    if (!button()) return;
    button().addEventListener("click", buy);
    selector()?.addEventListener("change", () => {
      explicitCurrency = selector().value;
      button().setAttribute("aria-label", `Pay ${priceText(selected())} with PayPal`);
      message(readyMessage());
    });
    retry()?.addEventListener("click", async () => {
      const uid = A?.state().user?.uid;
      if (!uid) { message("Sign in with Google to see your PayPal currency options."); return; }
      retry().disabled = true;
      message("Checking local-currency prices; USD is available while you wait.");
      try { await loadQuotes(uid, true); }
      finally { retry().disabled = false; }
      if (!busy && A.state().user?.uid === uid) message(readyMessage());
    });
    if (!A) { message("Sign-in is unavailable."); return; }
    await A.ready;
    try {
      const response = await fetch(base + "/api/plans");
      if (response.ok) available = !!(await response.json()).paypal_payments?.enabled;
    } catch {}
    const returned = new URLSearchParams(window.location.search).get("paypal");
    message(returned === "cancel" ? "PayPal checkout was cancelled. You can try again."
      : available ? "Sign in to see PayPal currency options. The default price is USD 3.99."
      : "PayPal checkout is temporarily unavailable.");
    function onState() {
      update();
      const uid = A.state().user?.uid;
      const intent = read(intentKey);
      if (!uid && quoteUser) {
        quoteUser = null;
        quoteTime = 0;
        explicitCurrency = null;
        localPricesUnavailable = false;
        unavailablePreferred = null;
        if (retry()) retry().hidden = true;
        renderCurrencies([{ code: "USD", amount: "3.99" }], "USD");
      }
      if (uid && available && quoteUser !== uid) {
        loadQuotes(uid).then(() => {
          if (available && !busy && A.state().user?.uid === uid && !returned) message(readyMessage());
        });
      }
      if (uid && !resumed && !busy && returned !== "cancel" && (returned === "return" || read(savedKey)?.uid === uid)) {
        resumed = true;
        check();
      } else if (uid && !busy && available && intent && Date.now() - intent.at < 15 * 60 * 1000) {
        save(intentKey, null);
        message("Signed in. Review your currency and price, then continue with PayPal.");
      }
    }
    A.onChange(onState);
    onState();
    if (returned === "return" && !A.state().user) message("Sign in to the account used for checkout to confirm your PayPal payment.");
  });
})();

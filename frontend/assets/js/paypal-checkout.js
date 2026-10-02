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
  const button = () => document.querySelector("[data-buy-paypal]");
  const message = (text) => { document.querySelector("#paypalStatus").textContent = text; };
  const update = () => {
    button().disabled = busy || !available || !A?.enabled;
    document.querySelector("#checkPayPal").disabled = busy || !A?.state().user;
  };

  async function post(path, body) {
    const controller = new AbortController();
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new Error("Payment confirmation is taking too long. Check payment again; do not pay twice.")); }, 30000);
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
        save(intentKey, { at: Date.now() });
        message("Sign in with Google to connect your PayPal purchase to your account.");
        await A.signIn();
      }
      const uid = A.state().user?.uid;
      if (!uid) { save(intentKey, null); message("Sign-in was cancelled. You can try again."); return; }
      save(intentKey, null);
      message("Opening PayPal checkout…");
      const result = await post("/api/billing/paypal/order", { plan: "extended" });
      if (A.state().user?.uid !== uid) return;
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
    if (!uid) { message("Sign in to the account used for checkout, then select Check PayPal payment."); return; }
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
        message("PayPal has not confirmed a completed payment yet. Check again in a moment. If you paid, do not pay again.");
      }
    } catch (error) {
      if (A.state().user?.uid === uid) message(A.friendly(error) + " If you already paid, check again; do not pay twice.");
    } finally { busy = false; update(); }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    if (!button()) return;
    button().addEventListener("click", buy);
    document.querySelector("#checkPayPal").addEventListener("click", check);
    if (!A) { message("Sign-in is unavailable."); return; }
    await A.ready;
    try {
      const response = await fetch(base + "/api/plans");
      if (response.ok) available = !!(await response.json()).paypal_payments?.enabled;
    } catch {}
    const returned = new URLSearchParams(window.location.search).get("paypal");
    message(returned === "cancel" ? "PayPal checkout was cancelled. If you already paid, check payment below."
      : available ? "One-time US$3.99 payment through PayPal. Sign in before checkout."
      : "PayPal checkout is temporarily unavailable.");
    function onState() {
      update();
      const uid = A.state().user?.uid;
      const intent = read(intentKey);
      if (uid && !resumed && !busy && returned !== "cancel" && (returned === "return" || read(savedKey)?.uid === uid)) {
        resumed = true;
        check();
      } else if (uid && !busy && available && intent && Date.now() - intent.at < 15 * 60 * 1000) {
        save(intentKey, null);
        buy();
      }
    }
    A.onChange(onState);
    onState();
    if (returned === "return" && !A.state().user) message("Sign in to the account used for checkout, then select Check PayPal payment.");
  });
})();

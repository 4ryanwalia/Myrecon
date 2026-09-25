/* MyRecon, pricing page: account status and Pro pass checkout.
 *
 * The server does everything that matters. It creates the Razorpay order
 * (with the buyer's account id in the order notes), checks the payment
 * signature, and applies the pass. This page only opens Checkout for an order
 * the server made and reports what the server said back, so nothing a
 * visitor edits in the browser can grant a pass.
 */
(function () {
  "use strict";

  const CFG = window.MYRECON || { apiBase: "" };
  const A = window.MyReconAccount;
  const $ = (s) => document.querySelector(s);
  const note = (msg) => { const n = $("#payNote"); if (n) n.textContent = msg || ""; };
  let plansInfo = null;

  async function post(path, body) {
    const res = await fetch(CFG.apiBase + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await A.authHeaders()) },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === "error") throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  function loadCheckout() {
    if (window.Razorpay) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://checkout.razorpay.com/v1/checkout.js";
      s.onload = resolve;
      s.onerror = () => reject(new Error("Could not load the payment window. Check your connection."));
      document.head.appendChild(s);
    });
  }

  function renderAccount(st) {
    const box = $("#account");
    if (!box) return;
    if (!st || !st.user) { box.hidden = true; return; }
    box.hidden = false;
    const acct = st.account;
    $("#acctWho").textContent = `Signed in as ${st.user.email || st.user.name || "you"}`;
    if (!acct) {
      $("#acctPlan").textContent = "Account";
      $("#acctUsage").textContent = "";
      return;
    }
    if (acct.tier === "pro") {
      $("#acctPlan").textContent = acct.plan === "monthly" ? "Pro Monthly" : "Pro Weekly";
      $("#acctUsage").textContent =
        `${acct.pro_scans_left} Pro full scans left, until ${new Date(acct.pro_until).toLocaleDateString()}. `
        + `${acct.free_scans_left} of ${acct.free_scans_per_week} free ones left this week.`;
    } else {
      $("#acctPlan").textContent = "Free account";
      $("#acctUsage").textContent =
        `${acct.free_scans_left} of ${acct.free_scans_per_week} free full scans left this week `
        + `(resets ${new Date(acct.free_resets_at).toLocaleDateString()}).`;
    }
  }

  async function buy(planId) {
    if (!A || !A.enabled) { note("Accounts are not switched on yet."); return; }
    if (plansInfo && !plansInfo.payments_enabled) { note("Payments open soon. Your free account works now."); return; }
    try {
      if (!A.state().user) await A.signIn();
    } catch {
      return;
    }
    note("Preparing checkout…");
    let order;
    try {
      [order] = await Promise.all([post("/api/billing/order", { plan: planId }), loadCheckout()]);
    } catch (e) {
      note(e.message);
      return;
    }
    const rzp = new window.Razorpay({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount,
      currency: order.currency,
      name: "MyRecon",
      description: `${order.plan.label}: ${order.plan.full_scans} full scans, ${order.plan.days} days`,
      prefill: { email: order.email || "", name: order.name || "" },
      theme: { color: "#2563eb" },
      handler: async (resp) => {
        note("Confirming payment…");
        try {
          const r = await post("/api/billing/verify", resp);
          note(r.applied
            ? "Payment received. Your Pro pass is active."
            : "Payment received. It can take a minute to show here; refresh shortly.");
          await A.refreshAccount();
          renderAccount(A.state());
        } catch (e) {
          note(`${e.message} If you were charged, the pass is applied automatically once Razorpay confirms it. Contact us if it isn't within an hour.`);
        }
      },
      modal: { ondismiss: () => note("") },
    });
    rzp.on("payment.failed", (r) => note(`Payment failed: ${(r.error && r.error.description) || "please try again"}.`));
    rzp.open();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    document.querySelectorAll("[data-buy]").forEach((b) =>
      b.addEventListener("click", () => buy(b.dataset.buy)));
    document.querySelectorAll("[data-signin]").forEach((b) =>
      b.addEventListener("click", () => A && A.signIn().catch(() => {})));
    $("#signOutBtn")?.addEventListener("click", () => A && A.signOut());

    if (A) await A.ready;
    if (!A || !A.enabled) {
      note("Sign-in and Pro passes open soon. Every tool already works without an account.");
      return;
    }
    A.onChange(renderAccount);
    renderAccount(A.state());
    try {
      const res = await fetch(CFG.apiBase + "/api/plans");
      plansInfo = (await res.json()) || null;
      if (plansInfo && !plansInfo.payments_enabled) note("Pro passes open soon. Free accounts work now.");
    } catch {}
  });
})();

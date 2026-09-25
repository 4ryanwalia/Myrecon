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
    renderPlanButtons(st);
    if (!st || !st.user) { box.hidden = true; return; }
    box.hidden = false;
    const acct = st.account;
    const who = $("#acctWho");
    who.innerHTML = A.avatarHtml(st.user, "acct-avatar")
      + `<span>Signed in as ${escHtml(st.user.email || st.user.name || "you")}</span>`;
    A.wireAvatar(who);
    if (!acct) {
      $("#acctPlan").textContent = "Account";
      $("#acctUsage").textContent = "";
      return;
    }
    if (acct.tier === "pro") {
      $("#acctPlan").textContent = acct.plan === "monthly" ? "Pro Monthly" : "Pro Weekly";
      $("#acctUsage").textContent =
        `${acct.pro_scans_left} Pro scans and ${acct.extended_scans_left || 0} Extended scans left, until ${new Date(acct.pro_until).toLocaleDateString()}.`
        + (acct.free_scans_left > 0 ? " Your free Pro scan is still unused." : "");
    } else {
      $("#acctPlan").textContent = "Free account";
      $("#acctUsage").textContent =
        acct.free_scans_left > 0
        ? "Your free Pro scan is ready to use."
        : "You've used your free Pro scan. A Pro pass adds more.";
    }
  }

  // The Free account card: a sign-in button for visitors, and a status once
  // signed in, so nobody is asked to sign in again after they already have.
  function renderPlanButtons(st) {
    const signedIn = !!(st && st.user);
    const pro = signedIn && st.account && st.account.tier === "pro";
    document.querySelectorAll("[data-signin]").forEach((b) => {
      b.disabled = signedIn;
      b.classList.toggle("is-current", signedIn);
      b.textContent = !signedIn ? "Sign in with Google" : pro ? "Included with Pro" : "Your current plan";
    });
    document.querySelectorAll("[data-plan-card]").forEach((card) => {
      const current = card.dataset.planCard === (pro ? st.account.plan : signedIn ? "free" : "guest");
      card.classList.toggle("current", current);
    });
  }

  const escHtml = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---- saved scans --------------------------------------------------

  async function api(method, path) {
    const res = await fetch(CFG.apiBase + path, { method, headers: await A.authHeaders() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === "error") throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  async function loadScans() {
    const box = $("#scans"), list = $("#scanList");
    if (!box || !list) return;
    const st = A.state();
    if (!st.user) { box.hidden = true; return; }
    box.hidden = false;
    list.innerHTML = `<p class="hint">Loading your scans…</p>`;
    let scans;
    try {
      scans = (await api("GET", "/api/history")).scans || [];
    } catch (e) {
      list.innerHTML = `<p class="hint">Could not load your scans: ${escHtml(e.message)}</p>`;
      return;
    }
    $("#clearScans").hidden = !scans.length;
    if (!scans.length) {
      list.innerHTML = `<p class="hint">No saved scans yet. <a href="/#tool">Run a username scan</a> while signed in and it appears here.</p>`;
      return;
    }
    list.innerHTML = scans.map((s) => `
      <div class="scan-row">
        <div class="scan-main">
          <strong>${escHtml(s.handle)}</strong>
          <span class="scan-badge${s.scope === "full" || s.scope === "extended" ? " pro" : ""}">${s.scope === "extended" ? "Extended · 3,000+" : s.scope === "full" ? "Pro · 500+" : "Standard · 100"}</span>
          <span class="hint">${escHtml(new Date(s.at).toLocaleString())} · ${Number(s.profiles) || 0} found</span>
        </div>
        <div class="scan-actions">
          <a class="btn btn-sm" href="/#tool=username&amp;scan=${encodeURIComponent(s.id)}">Open</a>
          <button type="button" class="btn btn-ghost btn-sm" data-del-scan="${escHtml(s.id)}" aria-label="Delete scan of ${escHtml(s.handle)}">Delete</button>
        </div>
      </div>`).join("");
  }

  async function buy(planId) {
    if (!A || !A.enabled) { note("Accounts are not switched on yet."); return; }
    if (plansInfo && !plansInfo.payments_enabled) { note("Payments open soon. Your free account works now."); return; }
    try {
      if (!A.state().user) await A.signIn();
    } catch (e) {
      note(A.friendly(e));
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
      description: `${order.plan.label}: ${order.plan.full_scans} full scans, ${order.plan.extended_scans} Extended, ${order.plan.days} days`,
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
      b.addEventListener("click", () => A && A.signIn().catch((e) => note(A.friendly(e)))));
    $("#signOutBtn")?.addEventListener("click", () => A && A.signOut());

    if (A) await A.ready;
    if (!A || !A.enabled) {
      note("Sign-in and Pro passes open soon. Every tool already works without an account.");
      return;
    }
    let lastUid = null;
    const onState = (st) => {
      renderAccount(st);
      const uid = st && st.user ? st.user.uid : null;
      if (uid !== lastUid) { lastUid = uid; loadScans(); }
    };
    A.onChange(onState);
    onState(A.state());
    $("#scanList")?.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-del-scan]");
      if (!btn) return;
      btn.disabled = true;
      try { await api("DELETE", `/api/history/${encodeURIComponent(btn.dataset.delScan)}`); }
      catch (err) { note(err.message); }
      loadScans();
    });
    $("#clearScans")?.addEventListener("click", async () => {
      if (!confirm("Delete all your saved scans? This cannot be undone.")) return;
      try { await api("DELETE", "/api/history"); } catch (err) { note(err.message); }
      loadScans();
    });
    try {
      const res = await fetch(CFG.apiBase + "/api/plans");
      plansInfo = (await res.json()) || null;
      if (plansInfo && !plansInfo.payments_enabled) note("Pro passes open soon. Free accounts work now.");
    } catch {}
  });
})();

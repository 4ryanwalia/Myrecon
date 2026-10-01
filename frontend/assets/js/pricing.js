/* MyRecon, pricing page: account status and Extended pack checkout.
 *
 * The server creates Razorpay orders or Buy Me a Coffee activation codes,
 * verifies provider signatures and applies the pack. Browser actions alone
 * cannot grant paid access.
 */
(function () {
  "use strict";

  const CFG = window.MYRECON || { apiBase: "" };
  const A = window.MyReconAccount;
  const $ = (s) => document.querySelector(s);
  const note = (msg) => { const n = $("#payNote"); if (n) n.textContent = msg || ""; };
  let plansInfo = null;
  let internationalUid = null;

  function closeInternational() {
    internationalUid = null;
    const box = $("#internationalCheckout");
    if (box) box.hidden = true;
    const code = $("#activationCode");
    if (code) code.value = "";
    $("#openInternational")?.removeAttribute("href");
  }

  function renderPayments() {
    const b = $("[data-buy-international]");
    if (!b) return;
    b.disabled = !plansInfo?.international_payments?.enabled;
    const status = $("#internationalStatus");
    if (status) status.textContent = b.disabled
      ? "International checkout opens soon."
      : "Same pack, paid in USD through Buy Me a Coffee.";
  }

  async function buyInternational() {
    if (!A?.enabled || !plansInfo?.international_payments?.enabled) {
      note("International checkout is not available yet.");
      return;
    }
    const button = $("[data-buy-international]");
    button.disabled = true;
    closeInternational();
    try {
      if (!A.state().user) await A.signIn();
      const uid = A.state().user?.uid;
      if (!uid) return;
      note("Preparing international checkout…");
      const result = await post("/api/billing/buymeacoffee/checkout", { plan: "extended" });
      if (A.state().user?.uid !== uid) return;
      const url = new URL(result.url);
      if (url.protocol !== "https:" || !["buymeacoffee.com", "www.buymeacoffee.com"].includes(url.hostname)) {
        throw new Error("The checkout link is unavailable. Please try later.");
      }
      internationalUid = uid;
      $("#activationCode").value = result.activation_code;
      $("#openInternational").href = url.href;
      $("#internationalCheckout").hidden = false;
      $("#internationalCheckout").scrollIntoView({ block: "start" });
      $("#activationCode").focus({ preventScroll: true });
      note("Copy your activation code, then paste it into the required question at checkout.");
    } catch (e) {
      note(A.friendly(e));
    } finally {
      renderPayments();
    }
  }

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
    $("#acctPlan").textContent = acct.standard_scans_unlimited ? "Extended Scan Pack" : "Free standard account";
    const pack = Number(acct.extended_pack_scans_left) || 0;
    const legacy = Number(acct.extended_legacy_scans_left) || 0;
    $("#acctUsage").textContent = (acct.standard_scans_unlimited
      ? "Unlimited standard 500+ platform scans and Deep Search included with your paid plan. "
      : `${acct.standard_scans_left} of 5 free standard scans left today. Resets at midnight UTC (${new Date(acct.standard_resets_at).toLocaleString()}). `)
      + (pack ? `${pack} Extended pack scans left, no expiry. ` : "")
      + (legacy ? `${legacy} scans from a previous pass, until ${new Date(acct.extended_legacy_until).toLocaleDateString()}.` : "")
      + (!pack && !legacy ? "Get 10 Extended scans for ₹99 when you need wider coverage." : "");
  }

  // The Free account card: a sign-in button for visitors, and a status once
  // signed in, so nobody is asked to sign in again after they already have.
  function renderPlanButtons(st) {
    const signedIn = !!(st && st.user);
    const pro = signedIn && st.account && st.account.standard_scans_unlimited;
    document.querySelectorAll("[data-signin]").forEach((b) => {
      b.disabled = signedIn;
      b.classList.toggle("is-current", signedIn);
      b.textContent = !signedIn ? "Sign in with Google" : pro ? "Unlimited standard included" : "Standard: 5 scans a day";
    });
    document.querySelectorAll("[data-plan-card]").forEach((card) => {
      const current = card.dataset.planCard === (pro ? "extended" : signedIn ? "free" : "guest");
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
          <span class="scan-badge${s.scope === "full" || s.scope === "extended" ? " pro" : ""}">${s.scope === "extended" ? "Extended · 3,000+" : s.scope === "full" ? "Standard · 500+" : "Quick · 100"}</span>
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
      description: `${order.plan.label}: Deep Search + unlimited standard scans + ${order.plan.extended_scans} Extended scans, no expiry`,
      prefill: { email: order.email || "", name: order.name || "" },
      theme: { color: "#16633a" },
      handler: async (resp) => {
        note("Confirming payment…");
        try {
          const r = await post("/api/billing/verify", resp);
          note(r.applied
            ? "Payment received. Deep Search and your Extended scans are ready."
            : "Payment received. It can take a minute to show here; refresh shortly.");
          await A.refreshAccount();
          renderAccount(A.state());
        } catch (e) {
          note(`${e.message} If you were charged, the pack is applied automatically once Razorpay confirms it. Contact us if it isn't within an hour.`);
        }
      },
      modal: { ondismiss: () => note("") },
    });
    rzp.on("payment.failed", (r) => note(`Payment failed: ${(r.error && r.error.description) || "please try again"}.`));
    rzp.open();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    $("[data-buy-international]")?.addEventListener("click", buyInternational);
    $("#copyActivation")?.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText($("#activationCode").value);
        note("Activation code copied. Paste it into the required question on Buy Me a Coffee.");
      } catch {
        $("#activationCode").focus();
        $("#activationCode").select();
        note("Select and copy the activation code, then paste it into the required checkout question.");
      }
    });
    $("#openInternational")?.addEventListener("click", (e) => {
      if (!internationalUid || A.state().user?.uid !== internationalUid) {
        e.preventDefault();
        closeInternational();
        note("Sign in and prepare international checkout again.");
      }
    });
    $("#refreshInternational")?.addEventListener("click", async () => {
      try {
        await A.refreshAccount();
        renderAccount(A.state());
        note("Account refreshed. If your purchase is still missing, wait a minute and check again. Contact aryan@bugsnaps.in with your receipt if it has not appeared within an hour.");
      } catch (e) { note(A.friendly(e)); }
    });
    document.querySelectorAll("[data-buy]").forEach((b) =>
      b.addEventListener("click", () => buy(b.dataset.buy)));
    document.querySelectorAll("[data-signin]").forEach((b) =>
      b.addEventListener("click", () => A && A.signIn().catch((e) => note(A.friendly(e)))));
    $("#signOutBtn")?.addEventListener("click", () => A && A.signOut());

    if (A) await A.ready;
    if (!A || !A.enabled) {
      note("Sign-in is temporarily unavailable. Guest previews and other free tools still work.");
      return;
    }
    let lastUid = null;
    const onState = (st) => {
      renderAccount(st);
      const uid = st && st.user ? st.user.uid : null;
      if (uid !== lastUid) { closeInternational(); lastUid = uid; loadScans(); }
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
      if (plansInfo && !plansInfo.payments_enabled && !plansInfo.international_payments?.enabled) note("Extended packs open soon. Free accounts get 5 standard scans a day.");
    } catch {} finally { renderPayments(); }
  });
})();

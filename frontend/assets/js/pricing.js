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
  let internationalExpires = 0;
  let paymentState = "pending";
  let busy = "";
  let attempt = 0;
  const CHECKOUT = "mr_bmc_checkout";
  const SIGNIN_INTENT = "mr_bmc_signin_intent";
  const save = (key, value) => { try { value ? sessionStorage.setItem(key, JSON.stringify(value)) : sessionStorage.removeItem(key); } catch {} };
  const read = (key) => { try { return JSON.parse(sessionStorage.getItem(key)); } catch { return null; } };

  function closeInternational(clearSaved = true) {
    internationalUid = null;
    internationalExpires = 0;
    paymentState = "pending";
    if (clearSaved) save(CHECKOUT, null);
    const box = $("#internationalCheckout");
    if (box) box.hidden = true;
    const code = $("#activationCode");
    if (code) code.value = "";
    $("#openInternational")?.removeAttribute("href");
  }

  function renderPayments() {
    const b = $("[data-buy-international]");
    if (!b) return;
    b.disabled = !A?.enabled || !plansInfo?.international_payments?.enabled || !!busy;
    b.textContent = busy === "signin" ? "Finish Google sign-in…" : busy ? "Preparing your checkout…" : "Buy Me a Coffee: US$3.99";
    const status = $("#internationalStatus");
    if (status) status.textContent = !plansInfo?.international_payments?.enabled
      ? "US dollar checkout is temporarily unavailable. Please try again later."
      : "One-time payment through Buy Me a Coffee. Sign in to connect your pack.";
    document.querySelectorAll("[data-buy]").forEach((button) => {
      button.disabled = !A?.enabled || !plansInfo?.payments_enabled;
    });
    if ($("#indianStatus")) $("#indianStatus").textContent = plansInfo?.payments_enabled
      ? "Pay in INR through Indian checkout."
      : "Indian checkout is temporarily unavailable.";
  }

  function checkoutUrl(value) {
    const url = new URL(value);
    if (url.protocol !== "https:" || !["buymeacoffee.com", "www.buymeacoffee.com"].includes(url.hostname)
        || url.username || url.password || (url.port && url.port !== "443")) {
      throw new Error("The checkout link is unavailable. Please try later.");
    }
    return url.href;
  }

  function showCheckout(result, uid, scroll = true) {
    const url = checkoutUrl(result.url);
    if (!/^MR-[a-f0-9]{32}$/.test(result.activation_code) || !Number.isFinite(result.expires_at)) {
      throw new Error("Could not prepare your account code. Please try again.");
    }
    internationalUid = uid;
    internationalExpires = result.expires_at;
    paymentState = "pending";
    save(CHECKOUT, { uid, url, activation_code: result.activation_code, expires_at: result.expires_at });
    $("#activationCode").value = result.activation_code;
    $("#openInternational").href = url;
    $("#openInternational").removeAttribute("aria-disabled");
    $("#internationalCheckout").hidden = false;
    $("#internationalCheckout").dataset.payment = "pending";
    $("#copyActivation").textContent = "Copy code";
    $("#copyStatus").textContent = "";
    $("#activationExpiry").textContent = `Use this code before ${new Date(internationalExpires * 1000).toLocaleString()}.`;
    $("#paymentStatus").textContent = "Waiting for payment. This code alone does not unlock the pack.";
    if (internationalExpires <= Date.now() / 1000) {
      $("#openInternational").removeAttribute("href");
      $("#openInternational").setAttribute("aria-disabled", "true");
      $("#paymentStatus").textContent = "This code has expired. If you have not paid, use Get the pack above to create a new code. If you already paid, check payment below.";
    }
    if (scroll) $("#internationalCheckout").scrollIntoView({ block: "start" });
  }

  function restoreCheckout(uid) {
    const saved = read(CHECKOUT);
    if (!uid || !saved || internationalUid) return false;
    if (saved.uid !== uid) { save(CHECKOUT, null); return false; }
    try { showCheckout(saved, uid, false); return true; }
    catch { save(CHECKOUT, null); return false; }
  }

  function resumeCheckout() {
    const intent = read(SIGNIN_INTENT);
    if (!intent) return;
    if (!Number.isFinite(intent.at) || Date.now() - intent.at > 15 * 60 * 1000) { save(SIGNIN_INTENT, null); return; }
    if (!busy && !internationalUid && A.state().user && plansInfo?.international_payments?.enabled) {
      save(SIGNIN_INTENT, null);
      buyInternational();
    }
  }

  async function buyInternational() {
    if (busy) return;
    if (!A?.enabled || !plansInfo?.international_payments?.enabled) {
      note("International checkout is not available yet.");
      return;
    }
    const thisAttempt = ++attempt;
    closeInternational();
    try {
      if (!A.state().user) {
        busy = "signin";
        save(SIGNIN_INTENT, { at: Date.now() });
        $("#signinRecovery").hidden = false;
        note("Finish Google sign-in. If no window opens, select Sign in in this tab below.");
        renderPayments();
        await A.signIn();
      }
      if (thisAttempt !== attempt) return;
      const uid = A.state().user?.uid;
      if (!uid) return;
      save(SIGNIN_INTENT, null);
      $("#signinRecovery").hidden = true;
      busy = "checkout";
      renderPayments();
      note("Preparing your account code…");
      const result = await post("/api/billing/buymeacoffee/checkout", { plan: "extended" });
      if (thisAttempt !== attempt || A.state().user?.uid !== uid) return;
      showCheckout(result, uid);
      note("Your checkout is ready. Follow the three steps below.");
    } catch (e) {
      if (thisAttempt === attempt) note(A.friendly(e) || "Sign-in was cancelled. You can try again.");
    } finally {
      if (thisAttempt === attempt) {
        busy = "";
        save(SIGNIN_INTENT, null);
        $("#signinRecovery").hidden = true;
        renderPayments();
      }
    }
  }

  async function post(path, body) {
    const controller = new AbortController();
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new Error("This is taking too long. Check your connection and try again.")); }, 30000);
    });
    try {
      return await Promise.race([(async () => {
        const headers = await A.authHeaders();
        controller.signal.throwIfAborted();
        const res = await fetch(CFG.apiBase + path, {
          method: "POST", signal: controller.signal,
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.status === "error") throw new Error(data.error || `Request failed (${res.status})`);
        return data;
      })(), timeout]);
    } finally { clearTimeout(timer); }
  }

  async function checkPayment() {
    const uid = internationalUid;
    const code = $("#activationCode").value;
    if (!uid || A.state().user?.uid !== uid || !code) return;
    const button = $("#refreshInternational");
    button.disabled = true;
    button.textContent = "Checking payment…";
    $("#paymentStatus").textContent = "Checking Buy Me a Coffee's payment confirmation…";
    try {
      const result = await post("/api/billing/buymeacoffee/status", { activation_code: code });
      if (internationalUid !== uid || A.state().user?.uid !== uid || $("#activationCode").value !== code) return;
      paymentState = result.payment_status;
      $("#internationalCheckout").dataset.payment = paymentState;
      if (paymentState === "applied") {
        $("#paymentStatus").textContent = "Payment confirmed. Your pack is unlocked: unlimited standard scans, Deep Search and 10 added Extended credits.";
        $("#openInternational").removeAttribute("href");
        $("#openInternational").setAttribute("aria-disabled", "true");
        // Payment status comes from this code's verified grant, even for repeat buyers.
        A.refreshAccount().then(() => { if (A.state().user?.uid === uid) renderAccount(A.state()); });
      } else if (paymentState === "expired") {
        $("#openInternational").removeAttribute("href");
        $("#openInternational").setAttribute("aria-disabled", "true");
        $("#paymentStatus").textContent = "This code has expired. If you have not paid, create a new code using Get the pack above. If you already paid, contact support with your receipt.";
      } else {
        $("#paymentStatus").textContent = "Payment has not been linked yet. If you already paid, submit your activation code in Buy Me a Coffee's purchase question, then wait a minute and check again. You do not need to pay again.";
      }
    } catch (e) {
      if (internationalUid === uid && $("#activationCode").value === code) $("#paymentStatus").textContent = `${A.friendly(e)} If you already paid, keep your receipt and try checking again.`;
    } finally {
      button.disabled = false;
      button.textContent = "Check payment";
    }
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
      + (!pack && !legacy ? "Get 10 Extended scans for ₹99 or US$3.99 when you need wider coverage." : "");
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
        $("#copyActivation").textContent = "Copied!";
        $("#copyStatus").textContent = "Code copied. Select Pay US$3.99, then paste it into the purchase question after payment.";
      } catch {
        $("#activationCode").focus();
        $("#activationCode").select();
        $("#copyStatus").textContent = "Automatic copy is unavailable. The code is selected: copy it manually, then paste it at checkout.";
      }
    });
    $("#openInternational")?.addEventListener("click", (e) => {
      if (!internationalUid || A.state().user?.uid !== internationalUid) {
        e.preventDefault();
        closeInternational();
        note("Sign in and prepare international checkout again.");
      } else if (paymentState === "applied" || internationalExpires <= Date.now() / 1000) {
        e.preventDefault();
        $("#paymentStatus").textContent = paymentState === "applied"
          ? "This purchase is confirmed. Use Get the pack above if you want to buy 10 more credits."
          : "This code has expired. Create a new code before paying, or check payment if you already paid.";
      }
    });
    $("#refreshInternational")?.addEventListener("click", checkPayment);
    $("#signinRedirect")?.addEventListener("click", async () => {
      // Abandon the popup attempt; its late completion must not open an old checkout.
      ++attempt;
      busy = "signin";
      save(SIGNIN_INTENT, { at: Date.now() });
      const button = $("#signinRedirect");
      button.disabled = true;
      note("Opening Google sign-in in this tab…");
      try {
        await A.signInRedirect();
      } catch (e) {
        busy = "";
        save(SIGNIN_INTENT, null);
        note(A.friendly(e));
        renderPayments();
      } finally { button.disabled = false; }
    });
    document.querySelectorAll("[data-buy]").forEach((b) =>
      b.addEventListener("click", () => buy(b.dataset.buy)));
    document.querySelectorAll("[data-signin]").forEach((b) =>
      b.addEventListener("click", () => A && A.signIn().catch((e) => note(A.friendly(e)))));
    $("#signOutBtn")?.addEventListener("click", () => {
      ++attempt;
      busy = "";
      save(SIGNIN_INTENT, null);
      closeInternational();
      $("#signinRecovery").hidden = true;
      renderPayments();
      A && A.signOut();
    });

    if (A) await A.ready;
    if (!A || !A.enabled) {
      note("Sign-in is temporarily unavailable. Guest previews and other free tools still work.");
      return;
    }
    let lastUid = null;
    const onState = (st) => {
      renderAccount(st);
      const uid = st && st.user ? st.user.uid : null;
      if (uid !== lastUid) {
        // Google sign-in can resolve before the account notification arrives.
        if (internationalUid && internationalUid !== uid) closeInternational();
        if (lastUid) {
          ++attempt;
          busy = "";
          save(SIGNIN_INTENT, null);
          $("#signinRecovery").hidden = true;
          renderPayments();
        }
        lastUid = uid;
        loadScans();
      }
      if (restoreCheckout(uid)) checkPayment();
      resumeCheckout();
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
      if (plansInfo && !plansInfo.payments_enabled && !plansInfo.international_payments?.enabled && !plansInfo.paypal_payments?.enabled) note("Extended packs open soon. Free accounts get 5 standard scans a day.");
    } catch {} finally { renderPayments(); resumeCheckout(); }
  });
})();

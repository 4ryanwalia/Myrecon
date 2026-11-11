/* Recurring checkout: all entitlements come from provider-verified server state. */
(function () {
  "use strict";
  const A = window.MyReconAccount;
  const base = (window.MYRECON || {}).apiBase || "";
  const $ = (s) => document.querySelector(s);
  let offers = [], busy = false, subscription = null, userId = null;
  const say = (s) => { $("#subscriptionStatus").textContent = s; };
  const date = (ms) => new Date(ms).toLocaleString();
  const selected = () => $("#basicPlan").value;
  const labels = { monthly: "US$3.99/month", yearly: "US$19.99/year", inr_monthly: "₹299/month" };

  async function api(path, body) {
    const response = await fetch(base + "/api/billing/subscriptions" + path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", ...await A.authHeaders() },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(60000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not update subscription.");
    return result;
  }

  function render() {
    const offer = offers.find((o) => o.id === selected());
    const trial = subscription?.trial_eligible !== false;
    $("#basicTerms").textContent = trial
      ? `3 days free, then ${labels[selected()]} automatically until cancelled. Cancel before the first charge to pay no subscription fee. One trial per account. Your exact first charge date is shown by the payment provider.`
      : `${labels[selected()]} starting today, automatically renewing until cancelled. Your account has already used its free trial.`;
    $("#basicAllowance").textContent = `${selected() === "yearly" ? "120 Extended scans per paid year" : "10 Extended scans per paid month"}; 3 during your free trial. Unused subscription scans expire at the end of their period.`;
    $("#startBasic").disabled = busy || !A?.enabled || !offer?.enabled || !$("#basicConsent").checked;
    $("#startBasic").textContent = busy ? "Please wait…" : trial ? "Start 3-day free trial" : "Subscribe to Basic";
    $("#basicPlan").disabled = busy;
    $("#manageSubscription").hidden = !A?.state().user;
    $("#refreshSubscription").disabled = busy;
    $("#cancelSubscription").hidden = !subscription?.id || ["cancelled", "expired", "completed", "approval_pending"].includes(subscription.status);
    const resume = $("#resumeSubscription");
    if (resume) {
      resume.hidden = true; resume.removeAttribute("href");
      if (subscription?.approval_url && subscription.status === "approval_pending") {
        const url = new URL(subscription.approval_url);
        if (url.protocol === "https:" && ["www.paypal.com", "www.sandbox.paypal.com"].includes(url.hostname) && !url.username && !url.password && (!url.port || url.port === "443")) {
          resume.href = url.href; resume.hidden = false;
        }
      }
    }
    $("#cancelSubscription").disabled = busy;
    $("#subscriptionDetails").textContent = !subscription ? "No Basic subscription on this account."
      : `Basic ${labels[subscription.plan] || ""} · ${subscription.status}. `
      + (subscription.active ? `${subscription.scans_left || 0} Extended scans left. Access until ${date(subscription.until)}. ` : "")
      + (subscription.status === "cancelled" ? "Automatic billing is cancelled."
        : subscription.active ? `Next charge: ${date(subscription.until)}. Cancel before then to stop renewal.`
        : "Check status after completing checkout. If checkout was interrupted, contact support before starting another subscription.");
  }

  async function refresh() {
    const uid = A?.state().user?.uid;
    if (!uid) { subscription = null; render(); return; }
    const result = await api("");
    if (A.state().user?.uid !== uid) return;
    subscription = result.subscription;
    render();
    await A.refreshAccount();
  }

  async function loadRazorpay() {
    if (window.Razorpay) return;
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://checkout.razorpay.com/v1/checkout.js";
      s.onload = resolve;
      s.onerror = () => reject(new Error("Could not load Razorpay. Check your connection."));
      document.head.appendChild(s);
    });
  }

  async function start() {
    if (busy || !$("#basicConsent").checked) return;
    busy = true; render();
    try {
      if (!A.state().user) await A.signIn();
      const uid = A.state().user?.uid;
      if (!uid) return;
      // Sign-in may reveal that this account has already used its trial.
      // Reconfirm the displayed terms before creating a billable contract.
      const offeredTrial = subscription?.trial_eligible !== false;
      await refresh();
      if (A.state().user?.uid !== uid) return;
      if (offeredTrial !== (subscription?.trial_eligible !== false)) {
        $("#basicConsent").checked = false;
        say("Your account has already used its trial. Review the updated billing terms and select Subscribe to Basic to continue.");
        return;
      }
      const key = selected();
      if (key === "inr_monthly") await loadRazorpay();
      say("Preparing your subscription approval…");
      const result = await api("", { plan: key, consent: true });
      if (A.state().user?.uid !== uid) return;
      if (result.provider === "paypal") {
        const url = new URL(result.url);
        if (url.protocol !== "https:" || !["www.paypal.com", "www.sandbox.paypal.com"].includes(url.hostname) || url.username || url.password || (url.port && url.port !== "443")) throw new Error("Invalid approval link.");
        window.location.assign(url.href);
        return;
      }
      say(result.trial_until ? `First subscription charge: ₹299 on ${date(result.trial_until)}, then monthly. Razorpay may require a refundable payment-method authorization.` : "₹299 monthly. Review and authorize recurring billing in Razorpay.");
      const checkout = new window.Razorpay({
        key: result.key_id, subscription_id: result.id, name: "MyRecon Basic",
        description: "₹299/month after a 3-day trial for eligible accounts",
        handler: async () => {
          try { await refresh(); say(subscription?.active ? "Basic is ready. Manage or cancel your subscription below." : "Authorization is being confirmed. Check status shortly; do not subscribe again."); }
          catch (e) { say(e.message); }
        },
        modal: { ondismiss: () => { refresh().catch((e) => say(e.message)); } },
      });
      checkout.on("payment.failed", () => say("Authorization failed. Check subscription status before trying again."));
      checkout.open();
    } catch (e) { say(A.friendly(e)); }
    finally { busy = false; render(); }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    if (!$("#startBasic")) return;
    $("#basicPlan").addEventListener("change", () => { $("#basicConsent").checked = false; render(); });
    $("#basicConsent").addEventListener("change", render);
    $("#startBasic").addEventListener("click", start);
    $("#refreshSubscription").addEventListener("click", async () => {
      busy = true; render();
      try { await refresh(); say("Subscription status updated."); }
      catch (e) { say(e.message); }
      finally { busy = false; render(); }
    });
    $("#cancelSubscription").addEventListener("click", async () => {
      if (busy || !confirm("Cancel automatic billing? Your confirmed access remains available until the end of the current trial or paid period.")) return;
      busy = true; render();
      try {
        const uid = A.state().user?.uid;
        const result = await api("/cancel", {});
        if (A.state().user?.uid !== uid) return;
        subscription = result.subscription;
        say("Subscription cancelled. You will not be charged for future periods.");
        await A.refreshAccount();
      } catch (e) { say(e.message); }
      finally { busy = false; render(); }
    });
    if (!A) { say("Sign-in is temporarily unavailable."); return; }
    await A.ready;
    try {
      const response = await fetch(base + "/api/plans");
      if (!response.ok) throw new Error("Could not load subscription prices.");
      offers = (await response.json()).subscriptions || [];
      say(offers.some((o) => o.enabled) ? "Choose your billing option, then review the recurring payment terms." : "Subscription checkout is temporarily unavailable.");
    } catch (e) { say(e.message); }
    A.onChange((state) => {
      const uid = state.user?.uid || null;
      if (uid !== userId) {
        userId = uid; subscription = null;
        if (uid) refresh().catch((e) => say(e.message));
      }
      render();
    });
    userId = A.state().user?.uid || null;
    if (userId) await refresh().catch((e) => say(e.message));
    if (new URLSearchParams(location.search).has("subscription")) say(userId ? "Check your subscription status below. Returning from checkout alone does not confirm authorization." : "Sign in to the same account to confirm your subscription.");
    render();
  });
})();

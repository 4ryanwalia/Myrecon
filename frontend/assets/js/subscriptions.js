/* Recurring checkout: all entitlements come from provider-verified server state. */
(function () {
  "use strict";
  const A = window.MyReconAccount;
  const base = (window.MYRECON || {}).apiBase || "";
  const $ = (s) => document.querySelector(s);
  let offers = [], busy = false, subscription = null, userId = null, period = "monthly";
  const say = (s) => { $("#subscriptionStatus").textContent = s; if ($("#checkoutStatus")) $("#checkoutStatus").textContent = s; };
  const date = (ms) => new Date(ms).toLocaleString();
  const selected = () => $("#basicPlan").value;
  const labels = { monthly: "US$3.99/month", yearly: "US$19.99/year", inr_monthly: "₹299/month", inr_yearly: "₹1,999/year" };
  const isRazorpay = (key) => String(key || "").startsWith("inr_");
  const providerKey = (provider) => provider === "paypal" ? period : (period === "yearly" ? "inr_yearly" : "inr_monthly");
  const COPY = {
    monthly: {
      price: "$3.99", period: "/ month", anchor: "", credits: "10 Extended scans per paid month",
      caption: "Monthly flexibility · ₹299/month in India",
      paypal: "$3.99/mo", razorpay: "₹299/mo", charge: "Pro continues at $3.99/mo or ₹299/mo.",
    },
    yearly: {
      price: "$19.99", period: "/ year", anchor: "", credits: "120 Extended scans per paid year",
      caption: "$1.67/month equivalent · $19.99 billed yearly · ₹1,999/year in India",
      paypal: "$19.99/yr · save 58%", razorpay: "₹1,999/yr · save 44%", charge: "Pro continues at $19.99/yr or ₹1,999/yr.",
    },
  };

  // A Razorpay checkout the customer never authorized can be closed by the
  // server and replaced; anything authorized, paid or PayPal-pending cannot.
  const replaceable = () => subscription?.provider === "razorpay" && subscription?.status === "created" && !subscription?.active;

  function checkoutConflict() {
    if (!subscription) return false;
    const terminal = ["cancelled", "expired", "completed"].includes(subscription.status);
    const resumable = ["pending", "approval_pending", "created"].includes(subscription.status);
    if (subscription.active) return true;
    if (terminal) return false;
    if (resumable && subscription.id && subscription.plan === selected()) return false;
    return !replaceable();
  }

  function conflictMessage() {
    return `You already have ${subscription?.provider === "razorpay" ? "a Razorpay" : "a PayPal"} ${labels[subscription?.plan] || ""} checkout or subscription. Manage it first, or resume that same plan. A second subscription has not been created.`;
  }

  function replacementNotice() {
    if (!replaceable() || subscription.plan === selected()) return "";
    return `Your unfinished Razorpay ${labels[subscription.plan] || ""} checkout was never authorized and nothing was charged. Continuing closes it and starts this plan instead.`;
  }

  async function api(path, body) {
    const controller = new AbortController();
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => {
        controller.abort();
        reject(new Error("Checkout took too long to respond. Check subscription status before retrying. An unfinished checkout may already exist; do not start a second subscription."));
      }, 30000);
    });
    try {
      return await Promise.race([timeout, (async () => {
        const headers = await A.authHeaders();
        controller.signal.throwIfAborted();
        const response = await fetch(base + "/api/billing/subscriptions" + path, {
          method: body === undefined ? "GET" : "POST",
          headers: { "Content-Type": "application/json", ...headers },
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: controller.signal,
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error || "Could not reach checkout. Check subscription status before retrying.");
        return result;
      })()]);
    } finally { clearTimeout(timer); }
  }

  function render() {
    const offer = offers.find((o) => o.id === selected());
    const trial = subscription?.trial_eligible !== false;
    $("#basicTerms").textContent = trial
      ? `3 days free, then ${labels[selected()]} automatically until cancelled. Cancel before the first charge to pay no subscription fee. One trial per account. Your exact first charge date is shown by the payment provider.`
      : `${labels[selected()]} starting today, automatically renewing until cancelled. Your account has already used its free trial.`;
    $("#basicAllowance").textContent = `${selected().endsWith("yearly") ? "120 Extended scans per paid year" : "10 Extended scans per paid month"}; 3 during your free trial. Unused subscription scans expire at the end of their period.`;
    $("#startBasic").disabled = busy || checkoutConflict() || !A?.enabled || !offer?.enabled || !$("#basicConsent").checked;
    $("#startBasic").textContent = busy ? "Please wait…" : trial ? "Start 3-day free trial" : "Subscribe to Pro";
    $("#basicPlan").disabled = busy;
    if ($("#checkoutManage")) $("#checkoutManage").hidden = !checkoutConflict();
    if ($("#checkoutNotice")) {
      const notice = replacementNotice();
      $("#checkoutNotice").textContent = notice;
      $("#checkoutNotice").hidden = !notice;
    }
    if ($("#resumeRazorpay")) {
      $("#resumeRazorpay").hidden = !(subscription?.provider === "razorpay" && subscription?.id && ["pending", "created"].includes(subscription.status));
      $("#resumeRazorpay").disabled = busy;
    }
    const yearly = period === "yearly";
    const copy = COPY[yearly ? "yearly" : "monthly"];
    document.querySelectorAll("[data-billing]").forEach((button) => {
      button.disabled = busy;
      button.setAttribute("aria-pressed", String(button.dataset.billing === period));
    });
    const setText = (id, text) => { if ($(id)) $(id).textContent = text; };
    setText("#pricingHeading", trial ? "Follow more public leads. Try Pro free." : "Follow more public leads with Pro.");
    setText("#pricingIntroCopy", trial ? "Explore Deep Search and a wider username search for 3 days. Cancel before your trial ends to avoid the subscription charge." : "Choose your billing period for Deep Search, unlimited Standard scans and Extended scan credits.");
    setText("#proPrice", copy.price);
    setText("#proPeriod", copy.period);
    if ($("#proAnchor")) { $("#proAnchor").textContent = copy.anchor; $("#proAnchor").hidden = !copy.anchor; }
    setText("#proPriceCaption", copy.caption);
    setText("#proCredits", copy.credits);
    setText("#paypalPrice", copy.paypal);
    setText("#razorpayPrice", copy.razorpay);
    setText("#timelineCharge", copy.charge);
    setText("#trialRibbonTitle", trial ? "3 days to explore Pro" : "Welcome back");
    setText("#trialRibbonText", trial ? "Includes 3 Extended scans + Deep Search." : "Pick up where you left off with Pro.");
    if ($("#trialTimeline")) $("#trialTimeline").hidden = !trial;
    if ($("#trialPill")) $("#trialPill").hidden = !trial;
    document.querySelectorAll("[data-provider-cta]").forEach((el) => { el.textContent = trial ? "Try Pro free for 3 days" : "Subscribe"; });
    setText("#trialSummary", trial ? `3 days free, then ${yearly ? "US$19.99/year or ₹1,999/year" : "US$3.99/month or ₹299/month"}. Auto-renews until cancelled. New subscribers only.` : "Your free trial has been used. Billing starts today and renews automatically until cancelled. Cancel anytime from this page.");
    setText("#checkoutHeading", trial ? "Start your 3-day free trial" : "Subscribe to Pro");
    setText("#checkoutProvider", `${isRazorpay(selected()) ? "Razorpay" : "PayPal"} · ${labels[selected()]}`);
    document.querySelectorAll("[data-subscribe]").forEach((button) => {
      const key = providerKey(button.dataset.subscribe);
      button.disabled = busy || !A?.enabled || !offers.find((o) => o.id === key)?.enabled;
      button.title = `${trial ? "Start your free trial" : "Subscribe"}: ${labels[key]}`;
    });
    $("#manageSubscription").hidden = !A?.state().user;
    $("#refreshSubscription").disabled = busy;
    $("#cancelSubscription").hidden = !subscription?.id || ["cancelled", "expired", "completed", "approval_pending"].includes(subscription.status);
    if (!$("#cancelSubscription").hidden) {
      $("#cancelSubscription").textContent = replaceable() ? "Cancel unfinished checkout" : "Cancel subscription";
    }
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
    $("#subscriptionDetails").textContent = !subscription ? "No Pro subscription on this account."
      : `Pro ${labels[subscription.plan] || ""} · ${subscription.status}. `
      + (subscription.active ? `${subscription.scans_left || 0} Extended scans left. Access until ${date(subscription.until)}. ` : "")
      + (subscription.status === "cancelled" ? "Automatic billing is cancelled."
        : subscription.active ? `Next charge: ${date(subscription.until)}. Cancel before then to stop renewal.`
        : replaceable() ? "Unfinished Razorpay checkout: never authorized, nothing charged. Resume it, or choose another plan above and it will be closed for you."
        : "Check status after completing checkout. If checkout was interrupted, contact support before starting another subscription.");
  }

  async function refresh(includeAccount = true) {
    const uid = A?.state().user?.uid;
    if (!uid) { subscription = null; render(); return; }
    const result = await api("");
    if (A.state().user?.uid !== uid) return;
    subscription = result.subscription;
    render();
    if (includeAccount) await A.refreshAccount();
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
    if (checkoutConflict()) { say(conflictMessage()); return; }
    busy = true; render();
    say("Checking your account and existing checkout…");
    let progressTimer;
    try {
      if (!A.state().user) await A.signIn();
      const uid = A.state().user?.uid;
      if (!uid) return;
      // Sign-in may reveal that this account has already used its trial.
      // Reconfirm the displayed terms before creating a billable contract.
      const offeredTrial = subscription?.trial_eligible !== false;
      await refresh(false);
      if (A.state().user?.uid !== uid) return;
      if (checkoutConflict()) { say(conflictMessage()); return; }
      if (offeredTrial !== (subscription?.trial_eligible !== false)) {
        $("#basicConsent").checked = false;
        say("Your account has already used its trial. Review the updated billing terms and select Subscribe to Pro to continue.");
        return;
      }
      const key = selected();
      window.MyReconAnalytics?.subscriptionStep?.("checkout_submit", key);
      if (isRazorpay(key)) await loadRazorpay();
      say(replaceable() && subscription.plan !== key ? "Closing your unfinished Razorpay checkout and preparing this plan…" : "Preparing your subscription approval…");
      progressTimer = setTimeout(() => say("Still waiting for the payment provider. Please keep this page open; this can take up to 30 seconds."), 8000);
      const result = await api("", { plan: key, consent: true });
      window.MyReconAnalytics?.subscriptionStep?.("provider_handoff", key);
      if (A.state().user?.uid !== uid) return;
      clearTimeout(progressTimer);
      if (result.provider === "paypal") {
        const url = new URL(result.url);
        if (url.protocol !== "https:" || !["www.paypal.com", "www.sandbox.paypal.com"].includes(url.hostname) || url.username || url.password || (url.port && url.port !== "443")) throw new Error("Invalid approval link.");
        window.location.assign(url.href);
        return;
      }
      const price = key === "inr_yearly" ? "₹1,999" : "₹299";
      const every = key === "inr_yearly" ? "yearly" : "monthly";
      say(result.trial_until ? `First subscription charge: ${price} on ${date(result.trial_until)}, then ${every}. Razorpay may require a refundable payment-method authorization.` : `${price} ${every}. Review and authorize recurring billing in Razorpay.`);
      const checkout = new window.Razorpay({
        key: result.key_id, subscription_id: result.id, name: "MyRecon Pro",
        description: `${labels[key]} after a 3-day trial for eligible accounts`,
        theme: { color: "#6d001a" },
        handler: async () => {
          try { await refresh(); say(subscription?.active ? "Pro is ready. Manage or cancel your subscription below." : "Authorization is being confirmed. Check status shortly; do not subscribe again."); }
          catch (e) { say(e.message); }
        },
        modal: { ondismiss: () => { refresh().catch((e) => say(e.message)); } },
      });
      checkout.on("payment.failed", () => say("Authorization failed. Check subscription status before trying again."));
      // Release the native dialog top layer so Razorpay can receive focus.
      $("#subscriptionDialog")?.close();
      checkout.open();
    } catch (e) { say(A.friendly(e)); }
    finally { clearTimeout(progressTimer); busy = false; render(); }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    if (!$("#startBasic")) return;
    document.querySelectorAll("[data-billing]").forEach((button) => button.addEventListener("click", () => {
      if (busy) return;
      period = button.dataset.billing;
      window.MyReconAnalytics?.subscriptionStep?.("billing_select", period);
      $("#basicPlan").value = period;
      $("#basicConsent").checked = false;
      render();
    }));
    document.querySelectorAll("[data-subscribe]").forEach((button) => button.addEventListener("click", () => {
      if (busy || button.disabled) return;
      $("#basicPlan").value = providerKey(button.dataset.subscribe);
      $("#basicConsent").checked = false;
      if ($("#checkoutStatus")) $("#checkoutStatus").textContent = "";
      render();
      if (checkoutConflict()) say(conflictMessage());
      $("#subscriptionDialog").showModal();
      window.MyReconAnalytics?.subscriptionStep?.("checkout_review", selected());
    }));
    $("#checkoutManage")?.addEventListener("click", () => {
      $("#subscriptionDialog").close();
      $("#manageSubscription").scrollIntoView({ block: "center" });
      $("#refreshSubscription").focus({ preventScroll: true });
    });
    $("#resumeRazorpay")?.addEventListener("click", () => {
      const plan = subscription?.plan === "inr_yearly" ? "inr_yearly" : "inr_monthly";
      period = plan === "inr_yearly" ? "yearly" : "monthly";
      $("#basicPlan").value = plan;
      $("#basicConsent").checked = false;
      say("Resume your existing Razorpay checkout. Review the terms, then continue; this will reuse the same subscription.");
      render();
      $("#subscriptionDialog").showModal();
    });
    $("#closeSubscription")?.addEventListener("click", () => $("#subscriptionDialog").close());
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
      const prompt = replaceable()
        ? "Cancel this unfinished Razorpay checkout? Nothing has been charged."
        : "Cancel automatic billing? Your confirmed access remains available until the end of the current trial or paid period.";
      if (busy || !confirm(prompt)) return;
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
      say(offers.some((o) => o.enabled) ? "Choose PayPal or Razorpay to review your plan." : "Subscription checkout is temporarily unavailable.");
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

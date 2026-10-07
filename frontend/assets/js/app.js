/* MyRecon, application logic (vanilla JS, no dependencies). */
(function () {
  "use strict";

  const CFG = window.MYRECON;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const RESPONSE_UID = Symbol("responseUid");

  // ---------------------------------------------------------------- helpers
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));

  /* Any URL that reaches an href or src attribute goes through here first.
   *
   * esc() makes a string safe to sit *inside* markup, but it has nothing to say
   * about what the string means once it is there: "javascript:alert(1)" has no
   * &<>"' in it, so it passes through esc() untouched and then runs on click.
   * The URLs on this page are not all ours, avatar and profile links arrive in
   * whatever a platform's API returned, and a Gravatar account link is filled
   * in by whoever owns the Gravatar, so the scheme has to be checked rather
   * than assumed.
   *
   * Anything that is not http(s) becomes "", which renders as a dead link
   * instead of a live script.
   */
  const safeUrl = (u) => {
    const raw = String(u ?? "").trim();
    if (!raw) return "";
    try {
      // Resolved against the page so relative URLs keep working; the protocol
      // check then sees what the browser would actually navigate to.
      const parsed = new URL(raw, location.href);
      return (parsed.protocol === "http:" || parsed.protocol === "https:") ? parsed.href : "";
    } catch {
      return "";
    }
  };

  const fmtNum = (n) => {
    n = Number(n) || 0;
    // Breach corpora run to billions of records, so B is a real bucket here.
    if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(n);
  };

  const hostOf = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } };

  // ---------------------------------------------------------------- icons
  // Clean inline line-icons (no emoji). currentColor + stroke.
  const SVG = {
    user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4.5 20.5c1-4 4.2-6 7.5-6s6.5 2 7.5 6"/></svg>',
    mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/></svg>',
    globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18"/></svg>',
    compass: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/></svg>',
    pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>',
    link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 15a4 4 0 0 0 5.66 0l3-3A4 4 0 1 0 12 6.34l-1 1"/><path d="M15 9a4 4 0 0 0-5.66 0l-3 3A4 4 0 1 0 12 17.66l1-1"/></svg>',
    external: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 5h5v5"/><path d="M19 5l-8 8"/><path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6z"/><circle cx="12" cy="12" r="2.6"/></svg>',
    eyeOff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.6 6.2A9.7 9.7 0 0 1 12 6c6.4 0 10 6 10 6a17 17 0 0 1-3.2 3.7M6.3 8.3A17 17 0 0 0 2 12s3.6 6 10 6a9.6 9.6 0 0 0 3.9-.8"/><path d="m3 3 18 18"/></svg>',
  };
  const icon = (name, size = 18) => {
    const s = SVG[name];
    return s ? s.replace("<svg ", `<svg width="${size}" height="${size}" aria-hidden="true" `) : "";
  };

  // ---------------------------------------------------------------- toast
  function toast(msg, kind = "ok") {
    let host = $(".toasts");
    if (!host) { host = document.createElement("div"); host.className = "toasts"; document.body.appendChild(host); }
    const el = document.createElement("div");
    el.className = "toast " + (kind === "err" ? "err" : "ok");
    el.textContent = msg;
    el.setAttribute("role", "status");
    host.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 3200);
  }

  // ---------------------------------------------------------------- theme
  const THEME_KEY = "myrecon-theme";
  // Browser storage is optional. It can throw in privacy modes, embedded
  // browsers, and when the quota is full; none of those should stop a lookup.
  function storageGet(key) {
    try { return window.localStorage.getItem(key); } catch { return null; }
  }
  function storageSet(key, value) {
    try { window.localStorage.setItem(key, value); return true; } catch { return false; }
  }
  function storageRemove(key) {
    try { window.localStorage.removeItem(key); return true; } catch { return false; }
  }

  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    const browserTheme = document.querySelector('meta[name="theme-color"]');
    if (browserTheme) browserTheme.content = t === "light" ? "#f7f7f4" : "#111111";
    const btn = $("#themeToggle");
    if (btn) btn.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }
  function initTheme() {
    const stored = storageGet(THEME_KEY);
    const saved = stored === "light" || stored === "dark" ? stored : null;
    const defaultTheme = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    applyTheme(saved || defaultTheme);
    $("#themeToggle")?.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      storageSet(THEME_KEY, next);
      applyTheme(next);
    });
  }

  // ---------------------------------------------------------------- nav
  function initNav() {
    const btn = $("#navToggle");
    const links = $("#navLinks");
    if (!btn || !links) return;
    // The button showed and hid the menu but never said so: no aria-expanded,
    // so a screen reader announced the same thing open or closed.
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-controls", "navLinks");
    btn.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      btn.setAttribute("aria-expanded", String(open));
    });
  }

  // ---------------------------------------------------------------- API
  // A refusal the page can act on (sign in, upgrade, come back tomorrow),
  // as opposed to a failure. Carries the server's code and, for
  // upgrade_required, the account's remaining allowance.
  class GateError extends Error {
    constructor(message, code, account, scope) {
      super(message);
      this.code = code;
      this.account = account || null;
      this.scope = scope || null;
    }
  }
  const GATE_CODES = ["sign_in_required", "upgrade_required", "guest_limit", "standard_daily_limit",
    "accounts_unavailable", "auth_invalid"];

  function errorFrom(res, data) {
    const msg = (data && data.error) || `Request failed (${res.status})`;
    return data && GATE_CODES.includes(data.code)
      ? new GateError(msg, data.code, data.account, data.scope) : new Error(msg);
  }

  // Signed-in requests carry the Firebase ID token. account.js owns it; a
  // guest gets no header at all.
  async function authHeaders() {
    try {
      return window.MyReconAccount ? await window.MyReconAccount.authHeaders() : {};
    } catch {
      return {};
    }
  }

  async function api(endpoint, body) {
    const url = CFG.apiBase + endpoint;
    // Email reports and their public photos have no account access boundary.
    const publicEmail = /^\/api\/email(?:\/|[?#]|$)/.test(endpoint);
    const ctrl = new AbortController();
    // The full sweep checks 561 platforms and can take well over a minute;
    // the extended one checks several times that.
    const scopeWait = { full: 720000, extended: 2400000 };
    const timer = setTimeout(() => ctrl.abort(), (body && scopeWait[body.scope]) || (endpoint === CFG.endpoints.email ? 140000 : 90000));
    try {
      const requestUid = publicEmail ? null : window.MyReconAccount?.state()?.user?.uid || null;
      const headers = requestUid ? await authHeaders() : {};
      if (requestUid && window.MyReconAccount?.state()?.user?.uid !== requestUid) throw new Error("Your account changed. Start this action again.");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw errorFrom(res, data);
      }
      if (!publicEmail && !data.guest_access && (window.MyReconAccount?.state()?.user?.uid || null) !== requestUid) throw new Error("Your account changed before the report arrived. Start this action again.");
      if (!publicEmail) Object.defineProperty(data, RESPONSE_UID, { value: requestUid });
      return data;
    } catch (e) {
      if (e.name === "AbortError") throw new Error("The scan took too long and was cancelled. Try again.");
      if (e instanceof TypeError) throw new Error("Could not reach the MyRecon API. Check your connection or try later.");
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }

  // ---------------------------------------------------------------- tools registry
  const TOOLS = {
    username: {
      label: "Username", icon: "user", placeholder: "e.g. johndoe or a profile URL",
      endpoint: CFG.endpoints.username, field: "username", deep: true,
      sub: "Search a username across a wide range of platforms and enrich matches with avatars and bios.",
      examples: ["github", "torvalds", "nasa"],
    },
    email: {
      label: "Email", icon: "mail", placeholder: "e.g. name@example.com",
      endpoint: CFG.endpoints.email, field: "email",
      sub: "Free email results, no sign-in required. See reported breaches and exposed data, with optional public account checks.",
      examples: ["test@gmail.com", "contact@github.com"],
    },
    deepsearch: {
      label: "Deep Search", icon: "search", placeholder: "Name, @handle or exact email",
      sub: "Investigate public profiles, indexed mentions and Google reviews. Guests can run an investigation; sign in with an eligible plan to view findings.",
      examples: [], route: "/deep-search.html",
    },
    domain: {
      label: "Domain", icon: "globe", placeholder: "e.g. example.com",
      endpoint: CFG.endpoints.domain, field: "domain",
      sub: "WHOIS/RDAP registration, DNS records, email spoofing protection (SPF / DMARC), subdomains, and the resolved server's geolocation.",
      examples: ["github.com", "stripe.com", "wikipedia.org"],
    },
    dns: {
      label: "DNS", icon: "compass", placeholder: "e.g. example.com",
      endpoint: CFG.endpoints.dns, field: "domain",
      sub: "A, AAAA, MX, NS, TXT, CNAME, SOA and CAA records via DNS-over-HTTPS, with an SPF / DMARC spoofing check.",
      examples: ["cloudflare.com", "google.com"],
    },
    ip: {
      label: "IP", icon: "pin", placeholder: "e.g. 8.8.8.8",
      endpoint: CFG.endpoints.ip, field: "ip",
      sub: "Geolocation, network/ASN ownership, hosting flags, and reverse DNS.",
      examples: ["8.8.8.8", "1.1.1.1"],
    },
    // `local: true` keeps this tool entirely in the browser. It has no
    // endpoint, is refused by hash routing, and never sets lastResult, so
    // save / share / export / history cannot reach the typed secret.
    password: {
      label: "Password", icon: "lock", placeholder: "Type or paste a password to check",
      local: true, secret: true, field: "password",
      sub: "Checks a password against 900M+ credentials recovered from breach dumps. It is hashed in your browser, only the first 5 characters of the hash are ever sent.",
      examples: ["password", "qwerty123", "letmein"],
    },
  };

  let activeTool = "username";
  let lastResult = null;
  let lastExposure = null;
  let guestSnapshot = null, resultUid = null, activeScanUid = null, revealingGuest = false;
  const GUEST_REPORT_KEY = "myrecon.guest-report";

  function rememberGuestReport(tool, query, data) {
    if (tool === "email") {
      resultUid = null;
      return;
    }
    if (!data?.guest_access && data?.[RESPONSE_UID] !== undefined && (window.MyReconAccount?.state()?.user?.uid || null) !== data[RESPONSE_UID]) {
      lastResult = null;
      throw new Error("Your account changed before the report could be displayed.");
    }
    resultUid = data?.guest_access ? null : window.MyReconAccount?.state()?.user?.uid || null;
    if (!data?.guest_access) return;
    guestSnapshot = { tool, query, data };
    try { sessionStorage.setItem(GUEST_REPORT_KEY, JSON.stringify(guestSnapshot)); } catch {}
    if (signedIn() && data.guest_access.locked_count) Promise.resolve().then(revealGuestReport);
  }

  function lockedResults() {
    return lastResult?.tool !== "email" && !!lastResult?.data?.guest_access?.locked_count;
  }

  function accountChanged(state) {
    refreshScopeNote(false);
    const uid = state.user?.uid || null;
    if (activeScanUid && activeScanUid !== uid && activeTool !== "email") {
      liveSeen = new Set();
      lastResult = null;
      lastExposure = null;
      resultsEl().innerHTML = defaultEmpty();
    }
    if (lastResult && lastResult.tool !== "email" && resultUid && resultUid !== uid) {
      lastResult = null;
      lastExposure = null;
      resultUid = null;
      if (guestSnapshot && guestSnapshot.tool === activeTool) {
        lastResult = guestSnapshot;
        renderSafely(RENDERERS[activeTool], guestSnapshot.data);
        bindActions();
      } else resultsEl().innerHTML = defaultEmpty();
    }
    if (uid && lastResult?.tool !== "email" && lastResult?.data?.guest_access?.locked_count) revealGuestReport();
  }

  function guestPlaceholder() {
    return `<div class="card guest-placeholder" aria-hidden="true" inert><div class="guest-placeholder-line"></div><div class="guest-placeholder-line short"></div><div class="guest-placeholder-line"></div></div>`;
  }

  function renderGuestResults(data) {
    lastExposure = null;
    const access = data.guest_access;
    const cards = Array.isArray(data.cards) ? data.cards : [];
    const title = `${TOOLS[lastResult?.tool || activeTool].label} results`;
    let html = resultsHeader(title, `${Number(access.total_cards) || 0} result cards`);
    html += (data.notices || []).map(n => `<p class="partial-notice" role="status">${esc(n)}</p>`).join("");
    if (data.partial) html += `<p class="partial-notice" role="status">Some checks did not complete. Returned results are shown below; missing results remain inconclusive.</p>`;
    if (!cards.length) html += `<div class="empty"><p>No result cards were returned. An empty response does not establish absence; some sources may be unavailable.</p></div>`;
    html += `<div class="guest-visible-results">${cards.filter(c => !c.locked).map(guestCard).join("")}</div>`;
    if (access.locked_count > 0) html += `<section class="guest-locked-results" aria-label="Locked results"><div class="card-grid">${cards.filter(c => c.locked).map(guestPlaceholder).join("")}</div><div class="guest-results-overlay"><strong>Sign in to view all results</strong><p>${Number(access.locked_count)} more result ${access.locked_count === 1 ? "card is" : "cards are"} available.</p><p>${access.report_token ? "Your scan is retained for up to 30 minutes. A restart or capacity limit can end retention sooner." : "This report could not be retained. Sign in, then run the lookup again to view all results."}</p>${access.report_token ? `<button type="button" class="btn" data-guest-reveal>${signedIn() ? "View all results" : "Sign in to view all results"}</button>` : `<button type="button" class="btn" data-gate="signin">Sign in and run again</button>`}<p class="hint" data-guest-reveal-status role="status"></p></div></section>`;
    resultsEl().innerHTML = html;
    if (access.locked_count > 0) $$(".results-actions button", resultsEl()).forEach(b => { b.disabled = true; b.title = "Sign in to view all results before exporting or sharing."; });
  }

  function guestCard(card) {
    const d = card.data || {};
    if (card.kind === "profile") return `<div class="guest-visible-card">${profileCard(d, true)}</div>`;
    if (card.kind === "email_profile") return emailProfileCards({ evidence_report: { profiles: [d] } });
    if (card.kind === "email_review") return emailProfileCollections({ platform: "Google", reviews: [d] });
    if (card.kind === "email_position") return emailProfileCollections({ platform: "LinkedIn", positions: [d] });
    if (card.kind === "email_education") return emailProfileCollections({ platform: "LinkedIn", education: [d] });
    if (card.kind === "breach") return emailBreachList({ darkweb: { breaches: [d] } });
    if (card.kind === "mail_security") return `<div class="guest-visible-card">${mailSecurityBlock(d)}</div>`;
    if (card.kind === "dns") return `<div class="guest-visible-card">${renderDnsBlock(d)}</div>`;
    if (card.kind === "ip") return `<div class="guest-visible-card"><div class="section-label">${esc(card.title || "IP intelligence")}</div>${ipDetails(d)}</div>`;
    if (card.kind === "whois") return `<div class="guest-visible-card"><div class="section-label">Registration</div>${datalist([
      ["Domain", esc(d.domain) || "-"], ["Registrar", esc(d.registrar) || "-"],
      ["Created", esc(d.created) || "-"], ["Expires", esc(d.expires) || "-"],
      ["Updated", esc(d.updated) || "-"], ["Registrant", esc(d.registrant) || "-"],
      ["Country", esc(d.country) || "-"], ["Nameservers", (d.nameservers || []).map(esc).join("<br>") || "-"],
      ["DNSSEC", d.dnssec == null ? "-" : d.dnssec ? "Enabled" : "Disabled"],
      ["Status", (d.statuses || []).map(esc).join("<br>") || "-"],
    ])}</div>`;
    if (card.kind === "gravatar") return `<div class="card guest-visible-card"><div class="card-head">${avatarHTML(d, "G")}<div><div class="card-title">${esc(d.display_name || "Gravatar")}</div>${safeUrl(d.profile_url) ? `<a href="${esc(safeUrl(d.profile_url))}" target="_blank" rel="noopener nofollow">Open Gravatar profile ↗</a>` : ""}</div></div>${d.bio ? `<p class="card-bio">${esc(d.bio)}</p>` : ""}</div>`;
    if (card.kind === "service") return linkedServices({ services: [d] });
    if (card.kind === "github") return `<div class="card guest-visible-card"><div class="card-head">${avatarHTML(d, "GH")}<div><div class="card-title">${esc(d.username || "GitHub")}</div>${safeUrl(d.url) ? `<a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener nofollow">Open GitHub profile ↗</a>` : ""}</div></div><p class="card-bio">${esc(d.evidence || "Public GitHub evidence for this email")}</p>${safeUrl(d.evidence_url) ? `<p><a href="${esc(safeUrl(d.evidence_url))}" target="_blank" rel="noopener nofollow">View public commit evidence</a></p>` : ""}</div>`;
    return `<article class="card guest-visible-card"><h3>${esc(card.title || "Result")}</h3>${guestCardDetails(d)}</article>`;
  }

  function guestCardDetails(value) {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) return `<ul>${value.map(v => `<li>${guestCardDetails(v)}</li>`).join("")}</ul>`;
    if (typeof value !== "object") return esc(value);
    return `<dl class="guest-card-fields">${Object.entries(value).filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => `<div><dt>${esc(k.replace(/_/g, " "))}</dt><dd>${guestCardDetails(v)}</dd></div>`).join("")}</dl>`;
  }

  async function revealGuestReport() {
    const snapshot = lastResult?.data?.guest_access ? lastResult : guestSnapshot;
    if (snapshot?.tool === "email") return;
    const token = snapshot?.data?.guest_access?.report_token;
    if (!token || revealingGuest) return;
    revealingGuest = true;
    const revealUid = window.MyReconAccount?.state()?.user?.uid;
    const status = $("[data-guest-reveal-status]");
    if (status) status.textContent = "Opening your existing scan…";
    try {
      const response = await api("/api/guest-reports/reveal", { report_token: token });
      if (!revealUid || window.MyReconAccount?.state()?.user?.uid !== revealUid || lastResult?.data?.guest_access?.report_token !== token) return;
      const tool = response.tool;
      if (!RENDERERS[tool] || !response.data) throw new Error("This report could not be opened.");
      lastResult = { tool, query: snapshot.query, data: response.data };
      resultUid = window.MyReconAccount.state().user.uid;
      renderSafely(RENDERERS[tool], response.data);
      bindActions();
      toast("All results revealed. Nothing was rescanned.");
    } catch (error) {
      const message = error.code === "guest_report_expired" ? "This retained report has expired. Run a new lookup to continue." : error.message;
      const current = $("[data-guest-reveal-status]");
      if (current) current.textContent = message;
      else toast(message, "err");
    } finally { revealingGuest = false; }
  }

  // ---------------------------------------------------------------- rendering
  const resultsEl = () => $("#results");

  function setLoading(tool) {
    resultsEl().innerHTML = `
      <div class="loading" role="status" aria-live="polite">
        <div class="spinner"></div>
        <h3>Investigating…</h3>
        <p>Running the ${esc(TOOLS[tool].label.toLowerCase())} lookup and gathering data.</p>
        <div class="progress"><i></i></div>
      </div>`;
  }

  function setError(msg) {
    const live = $("#liveFound");
    if (live && liveSeen.size) {
      $(".loading.scan")?.remove();
      resultsEl().insertAdjacentHTML("afterbegin", `<div class="partial-notice" role="alert"><strong>Scan interrupted</strong><p>${esc(msg)} Completed findings below are a preview; remaining checks are incomplete.</p></div>`);
    } else {
      resultsEl().innerHTML = `<div class="error-box" role="alert">${esc(msg)}</div>`;
    }
  }

  // A result-view error must still leave a usable response and recovery path.
  function renderSafely(renderer, data) {
    try { data?.guest_access ? renderGuestResults(data) : renderer(data); }
    catch {
      lastExposure = null;
      resultsEl().innerHTML = `<div class="error-box" role="alert">Results arrived, but this view could not be displayed. Download the response or try the search again.<p><button class="btn btn-ghost" data-export="json">Download JSON</button></p></div>`;
    }
  }

  // What to show when the server refuses a scan for a reason the visitor can
  // fix. Each one says what happened and offers the one action that helps.
  function setGate(err) {
    const acct = err.account || {};
    const canSignIn = !!(window.MyReconAccount && window.MyReconAccount.enabled);
    let title, body, action = "";
    switch (err.code) {
      case "guest_limit":
        title = "That's today's free scans";
        if (!canSignIn) {
          body = "Guests get 5 Quick scans a day across 100 platforms. The allowance resets at midnight UTC.";
          break;
        }
        body = "Guests get 5 Quick scans a day across 100 platforms. Sign in with Google for 5 free Standard 500+ platform scans a day and complete results.";
        action = `<button type="button" class="btn btn-primary" data-gate="signin">Sign in with Google</button>`;
        break;
      case "standard_daily_limit":
        title = "You have used today's 5 standard scans";
        body = "Your free allowance resets at midnight UTC. The ₹99 plan unlocks unlimited standard scans and includes 10 Extended scans across 3,000+ platforms.";
        action = `<a class="btn btn-primary" href="/pricing.html">Get unlimited standard scans for ₹99</a>`;
        break;
      case "sign_in_required":
      case "auth_invalid":
        title = err.code === "auth_invalid" ? "Please sign in again"
          : err.scope === "extended" ? "Extended scans require sign-in" : "Standard scans require sign-in";
        body = canSignIn
          ? "Sign in with Google before running a Standard scan across 500+ platforms. Free accounts get 5 standard scans daily. Guests can run Quick scans across 100 platforms. The ₹99 plan adds unlimited standard scans and 10 Extended scans."
          : "Sign-in is temporarily unavailable. Guests can still run Quick scans across 100 platforms.";
        action = (canSignIn ? `<button type="button" class="btn btn-primary" data-gate="signin">Sign in with Google</button>` : "")
          + `<button type="button" class="btn btn-ghost" data-gate="standard">Run a Quick scan</button>`;
        break;
      case "upgrade_required": {
        title = "Get more Extended scans";
        body = "₹99 gives you 10 Extended scans across 3,000+ platforms each, with no expiry. Signed-in free accounts get 5 standard scans daily; the ₹99 plan includes unlimited standard scans.";
        action = `<a class="btn btn-primary" href="/pricing.html">Get the ₹99 plan</a>
          <button type="button" class="btn btn-ghost" data-gate="full">Run a free standard scan</button>`;
        break;
      }
      default:
        title = "Not available right now";
        body = esc(err.message);
    }
    resultsEl().innerHTML = `<div class="panel gate" role="alert">
      <h3>${esc(title)}</h3><p>${body}</p><div class="gate-actions">${action}</div></div>`;
  }

  function resultsHeader(title, count) {
    return `
      <div class="results-bar">
        <h2>${esc(title)}</h2>
        <span class="hint">${count}</span>
        <div class="results-actions">
          <button type="button" class="btn btn-sm" data-action="share-native">Share</button>
          <button type="button" class="btn btn-ghost btn-sm" data-action="save">Save</button>
          <button type="button" class="btn btn-ghost btn-sm" data-action="share">Copy link</button>
          <button type="button" class="btn btn-ghost btn-sm" data-action="copy">Copy results</button>
          <button type="button" class="btn btn-ghost btn-sm" data-action="print">Download PDF</button>
          <button type="button" class="btn btn-ghost btn-sm" data-export="json">Download JSON</button>
          <button type="button" class="btn btn-ghost btn-sm" data-export="csv">Download CSV</button>
        </div>
      </div>`;
  }

  function avatarHTML(r, fallbackChar, emailPhoto = false) {
    const pic = safeUrl(r.profile_pic_url || r.avatar_url);
    return `<div class="avatar"><span class="avatar-fallback" aria-hidden="true">${esc(fallbackChar)}</span>${pic
      ? `<img data-avatar${emailPhoto ? " data-email-photo" : ""} src="${esc(pic)}" alt="${esc(r.platform || "Profile")} photo" loading="lazy" referrerpolicy="no-referrer">` : ""}</div>`;
  }

  // Capture handles images inserted by any renderer. Keep the initials visible
  // until the image loads, and never read the parent after removing an image.
  document.addEventListener("load", (event) => {
    const img = event.target;
    if (img.matches?.("img[data-avatar]")) img.parentElement?.classList.add("loaded");
  }, true);
  document.addEventListener("error", (event) => {
    const img = event.target;
    if (!img.matches?.("img[data-avatar]") || (img.hasAttribute("data-email-photo") && window.EmailPhotos)) return;
    const parent = img.parentElement;
    if (parent) { parent.classList.remove("loaded"); parent.title = "Photo unavailable"; }
    img.remove();
  }, true);

  // -- Username results
  function previewMeta(data) {
    const p = data && data.preview;
    if (!p || p.requires_sign_in !== true) return null;
    const checked = Number(p.checked), visible = Number(p.visible), hidden = Number(p.hidden);
    if (![checked, visible, hidden].every(Number.isFinite) || checked <= 0 || visible < 0 || hidden < 0) return null;
    const hiddenFindings = Number(p.hidden_findings);
    return { checked, visible, hidden,
      hiddenFindings: Number.isFinite(hiddenFindings) && hiddenFindings >= 0 ? hiddenFindings : null };
  }

  function previewNotice(p) {
    return `<div class="preview-notice" role="status">
      <span class="preview-eyebrow">Guest preview</span>
      <strong>${p.visible} of ${p.checked} platforms shown</strong>
      <span>Results below include only the visible platforms.</span>
    </div>`;
  }

  function previewUnlock(p) {
    const canSignIn = !!(window.MyReconAccount && window.MyReconAccount.enabled);
    return `<section class="panel unlock-report" aria-labelledby="unlockTitle">
      <div class="unlock-copy">
        <span class="preview-eyebrow">Full report</span>
        <h3 id="unlockTitle">${p.hiddenFindings > 0
          ? `${p.hiddenFindings} more ${p.hiddenFindings === 1 ? "finding is" : "findings are"} in the full report`
          : `Unlock all ${p.checked} platform details`}</h3>
        <p>The sweep covered a ${p.checked}-platform catalogue. Your guest preview shows verdicts from ${p.visible} of them. Sign in to request the full report, including matches and links from the remaining platforms.</p>
        <div class="unlock-counts"><span>${p.visible} shown</span><span>${p.hidden} locked</span></div>
      </div>
      <div class="unlock-action">
        ${canSignIn ? `<button type="button" class="btn btn-primary" data-gate="unlock">Sign in to unlock</button>
          <span class="hint">Sign in for 5 free standard scans a day. The scan may run again.</span>`
          : `<span class="hint">Sign-in is temporarily unavailable. Your visible results remain above.</span>`}
      </div>
    </section>`;
  }

  // The map uses only found/possible profiles returned in this report. An
  // edge means the searched handle appeared on that platform, never that
  // every profile belongs to one person. Keep all visible profiles in the list.
  // Brand marks the site already ships (assets/img/platforms.svg, Simple
  // Icons, CC0), with each brand's colour. Anything else falls back to the
  // platform's own favicon, then to initials if that does not load.
  const MAP_MARKS = {
    instagram: ["instagram", "#E4405F"], facebook: ["facebook", "#0866FF"],
    youtube: ["youtube", "#FF0000"], reddit: ["reddit", "#FF4500"],
    discord: ["discord", "#5865F2"], telegram: ["telegram", "#26A5E4"],
    twitch: ["twitch", "#9146FF"], spotify: ["spotify", "#1DB954"],
    pinterest: ["pinterest", "#E60023"], steam: ["steam", "#66C0F4"],
    snapchat: ["snapchat", "#FFFC00"], tiktok: ["tiktok", "currentColor"],
    x: ["x", "currentColor"], "twitter / x": ["x", "currentColor"], twitter: ["x", "currentColor"],
    github: ["github", "currentColor"], gist: ["github", "currentColor"],
    medium: ["medium", "currentColor"], threads: ["threads", "currentColor"],
  };

  function mapMark(r, x, y) {
    const name = String(r.platform || "").trim().toLowerCase();
    const mark = MAP_MARKS[name];
    if (mark) {
      return `<svg x="${(x - 14).toFixed(1)}" y="${(y - 14).toFixed(1)}" width="28" height="28"
        viewBox="0 0 24 24" class="relationship-logo" style="color:${mark[1]}"><use href="/assets/img/platforms.svg#${mark[0]}"/></svg>`;
    }
    const host = hostOf(r.url);
    const initials = esc(String(r.platform || host || "Profile").slice(0, 2).toUpperCase());
    const text = `<text x="${x.toFixed(1)}" y="${(y + 5).toFixed(1)}" class="relationship-initials">${initials}</text>`;
    if (!host) return text;
    return text + `<image href="https://${esc(host)}/favicon.ico" x="${(x - 13).toFixed(1)}" y="${(y - 13).toFixed(1)}"
      width="26" height="26" class="relationship-favicon" preserveAspectRatio="xMidYMid meet"/>`;
  }

  // Favicons stay invisible until they load; one that fails is removed so the
  // initials underneath remain. Listeners, not inline handlers, for the CSP.
  function wireMapFavicons(root) {
    root.querySelectorAll(".relationship-favicon").forEach((img) => {
      img.addEventListener("load", () => {
        img.classList.add("ok");
        img.previousElementSibling?.classList.add("covered");
      }, { once: true });
      img.addEventListener("error", () => img.remove(), { once: true });
    });
  }

  function relationshipGraph(handle, profiles) {
    const mapped = profiles.filter((r) => safeUrl(r.url) &&
      (r.verdict === "found" || (r.exists === true && ["high", "medium"].includes(r.confidence))));
    const plotted = mapped.slice(0, 9);
    const w = 760, h = 470, cx = 380, cy = 222, rx = 278, ry = 156;
    const points = plotted.map((r, i) => {
      const angle = -Math.PI / 2 + i * (2 * Math.PI / plotted.length);
      return { r, x: cx + rx * Math.cos(angle), y: cy + ry * Math.sin(angle) };
    });
    const edges = points.map(({ x, y }) =>
      `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"/>`).join("");
    const nodes = points.map(({ r, x, y }) => {
      const name = String(r.platform || hostOf(r.url) || "Profile");
      const possible = r.confidence === "medium";
      return `<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener nofollow"
          aria-label="Open ${possible ? "possible" : "found"} ${esc(name)} profile">
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="28" class="relationship-node${possible ? " possible" : ""}"/>
          ${mapMark(r, x, y)}
          <text x="${x.toFixed(1)}" y="${(y + 45).toFixed(1)}" class="relationship-label">${esc(name.slice(0, 17))}</text>
          <title>${esc(name)}: ${possible ? "possible" : "found"} match for this handle</title>
        </a>`;
    }).join("");
    const graph = plotted.length ? `<svg viewBox="0 0 ${w} ${h}" role="img"
        aria-label="${plotted.length} found or possible platform profiles connected by the searched handle">
        <circle cx="${cx}" cy="${cy}" r="192" class="relationship-ring"/>
        <circle cx="${cx}" cy="${cy}" r="116" class="relationship-ring inner"/>
        <g class="relationship-edges">${edges}</g>
        <circle cx="${cx}" cy="${cy}" r="68" class="relationship-core"/>
        <text x="${cx}" y="${cy - 1}" class="relationship-handle">@${esc(String(handle || "").slice(0, 19))}</text>
        <text x="${cx}" y="${cy + 19}" class="relationship-core-sub">searched handle</text>
        <g class="relationship-nodes">${nodes}</g>
      </svg>` : `<div class="relationship-empty">No found or possible public profiles in the visible results.</div>`;
    return `<section class="relationship-panel" aria-labelledby="relationshipTitle">
      <div class="relationship-heading"><div><span class="preview-eyebrow">Account map</span>
        <h3 id="relationshipTitle">Profiles sharing this handle</h3></div>
        <span class="relationship-total">${mapped.length} mapped from this report</span></div>
      <div class="relationship-body"><div class="relationship-visual">${graph}</div>
        <div class="relationship-context"><strong>What the links mean</strong>
          <p>These platform checks found or suggested a public profile for the searched handle. A shared handle alone does not establish that the same person owns every account. Check the confidence label on each card.</p>
          ${mapped.length > plotted.length ? `<p class="relationship-more">Map shows ${plotted.length} of ${mapped.length} found or possible profiles. Switch to Cards to see every one.</p>` : ""}
          <span class="relationship-key"><i></i> Found profile <i class="possible"></i> Possible match</span>
        </div></div>
    </section>`;
  }

  function renderUsername(data) {
    const r = resultsEl();
    const { profiles = [], documents = [], mentions = [] } = data.results || {};
    const s = data.summary || {};
    const preview = previewMeta(data);
    const guest = !signedIn() || data.guest_preview?.requires_sign_in === true;
    const allCards = profiles.concat(documents, mentions);
    const hiddenCards = guest ? Math.max(0, Number(data.guest_preview?.hidden_cards) || allCards.length - 2) : 0;
    let html = resultsHeader(`Results for “${data.query.username}”`, `${s.total || 0} ${preview ? "visible findings" : "findings"}`);
    html += window.MyReconPartial?.notice(data) || "";

    if (preview) html += previewNotice(preview);
    if (guest && allCards.length) html += `<div class="preview-notice" role="status"><strong>Guest preview</strong><span>Only the first 2 result cards are visible. Sign in to run Standard and see complete results.</span></div>`;

    // A score based on two visible cards would misstate the complete report.
    const exp = guest || preview || data.partial ? null : computeExposure("username", data);
    lastExposure = exp;
    if (exp && (s.profiles || 0) > 0) html += exposureGauge(exp);

    html += `<div class="summary-grid">
      ${stat(s.profiles, "Profiles")}${stat(s.documents, "Documents")}
      ${stat(s.mentions, "Mentions")}${stat(s.clusters, "Identities")}
    </div>`;

    const relDomains = guest ? [] : usernameRelatedDomains(data);
    if (relDomains.length) html += pivotRow("Related domains", relDomains.map((d) => pivotChip("domain", d, d)));

    (guest ? [] : data.identity_clusters || []).forEach((c) => { html += clusterCard(c); });

    if (!guest) html += exposuresPanel(data.exposures || []);

    if (!profiles.length && !documents.length && !mentions.length) {
      html += emptyState(data.partial ? "No confirmed findings from the completed checks. Some sources could not be checked." : "No public profiles were found for this username.");
    } else {
      let cards = `<div class="card-grid">`;
      (guest ? allCards.slice(0, 2) : allCards).forEach((item) => { cards += profileCard(item); });
      for (let i = 0; i < hiddenCards; i++) cards += lockedProfileCard();
      cards += `</div>`;
      // The account map is for signed-in reports, and it replaces the cards
      // rather than sitting above them: one view of the same profiles at a time.
      if (!guest && !preview && profiles.length) {
        const view = resultsView();
        html += `<div class="view-switch" role="group" aria-label="Show results as">
            <button type="button" data-view="cards" aria-pressed="${view === "cards"}">Cards</button>
            <button type="button" data-view="map" aria-pressed="${view === "map"}">Account map</button>
          </div>
          <div data-view-pane="cards"${view === "cards" ? "" : " hidden"}>${cards}</div>
          <div data-view-pane="map"${view === "map" ? "" : " hidden"}>${relationshipGraph(data.query.username, profiles)}</div>`;
      } else {
        html += cards;
      }
    }

    const platformChecks = guest ? [] : data.platform_checks || [];
    if (platformChecks.length) {
      html += platformChecksPanel(platformChecks, s.checked || 0, data.query.username);
    } else if (!guest) {
      // Older saved reports predate the complete platform-check log. Keep their
      // original disclosures useful instead of rendering an empty new panel.
      html += unverifiedPanel(data.unverified || []);
      html += rejectedPanel(data.rejected || [], s.checked || 0);
    }
    if (data.coverage && !guest && !preview) html = html.replace(`<div class="summary-grid">`, coverageLine(data.coverage) + `<div class="summary-grid">`);
    else if (guest
      && !preview && window.MyReconAccount && window.MyReconAccount.enabled) html += fullScanNudge();
    if (preview) html += previewUnlock(preview);
    r.innerHTML = html;
    wireMapFavicons(r);
    animateCountUps();
  }

  // The full sweep reports how much of the map it could actually read. A
  // clean result means little if a third of the platforms never answered.
  function coverageLine(c) {
    const decided = (c.found || 0) + (c.not_found || 0);
    return `<p class="coverage-line hint">Full scan: ${c.total} platforms, ${decided} gave a definite answer,
      ${c.undetermined || 0} could not tell, ${c.unreachable || 0} blocked or timed out from our server.</p>`;
  }

  // One row for every platform the selected scan actually reached. This is a
  // report of the request, not an assertion that a username is absent: blocks,
  // timeouts, and weak signals stay "could not verify" or "possible".
  function platformChecksPanel(checks, checked, username) {
    if (!checks.length) return "";
    const labels = {
      found: "Profile found", possible: "Possible",
      not_found: "No match", unknown: "Could not verify",
    };
    const counts = { found: 0, possible: 0, not_found: 0, unknown: 0 };
    checks.forEach((check) => {
      const verdict = Object.prototype.hasOwnProperty.call(counts, check.verdict)
        ? check.verdict : "unknown";
      counts[verdict] += 1;
    });
    const total = Number(checked) > 0 ? Number(checked) : checks.length;
    const handle = String(username || "").replace(/^@+/, "");
    const rows = [...checks].sort((a, b) => String(a.platform || "").localeCompare(String(b.platform || "")))
      .map((check) => {
        const verdict = Object.prototype.hasOwnProperty.call(labels, check.verdict)
          ? check.verdict : "unknown";
        const url = safeUrl(check.url);
        const name = esc(check.platform || "Platform");
        const platform = url
          ? `<a href="${esc(url)}" target="_blank" rel="noopener nofollow">${name}</a>`
          : name;
        const category = check.category ? ` · ${esc(check.category)}` : "";
        const status = check.unreachable && verdict === "unknown" ? "Unavailable" : labels[verdict];
        return `<tr><td>${platform}<span class="hint">${category}</span></td>
          <td class="rj-code">${esc(status)}</td>
          <td class="rj-why">${esc(check.reason || "No additional response detail was available.")}</td></tr>`;
      }).join("");
    const outcomes = [
      counts.found ? `${counts.found} found` : "",
      counts.possible ? `${counts.possible} possible` : "",
      counts.not_found ? `${counts.not_found} no match` : "",
      counts.unknown ? `${counts.unknown} unverified` : "",
    ].filter(Boolean).join(" · ");
    return `<details class="panel rejected platform-checks">
      <summary>${total} platforms checked${handle ? ` for @${esc(handle)}` : ""}
        <span class="hint">${esc(outcomes)}</span></summary>
      <p class="hint" style="margin:0;padding:0 20px 14px">This is the exact scan record for this username. A blocked, timed-out, or ambiguous platform is not treated as a no-account result. <a href="/data/platforms.json" download>Download the current platform catalogue</a>.</p>
      <div class="rj-scroll"><table class="rj-table"><thead><tr><th scope="col">Platform</th><th scope="col">Outcome</th><th scope="col">Why</th></tr></thead><tbody>${rows}</tbody></table></div>
    </details>`;
  }

  // Platforms that answered but show one page to everybody, so no checker can
  // tell. Listed as links to open yourself, never counted as found.
  function unverifiedPanel(rows) {
    if (!rows.length) return "";
    const items = rows.map((x) => `<tr>
      <td><a href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener nofollow">${esc(x.platform)}</a></td>
      <td class="rj-why">${esc(x.reason)}</td></tr>`).join("");
    return `<details class="panel rejected">
      <summary>${rows.length} worth checking by hand
        <span class="hint">these sites can't be verified automatically</span></summary>
      <div class="rj-scroll"><table class="rj-table"><tbody>${items}</tbody></table></div>
    </details>`;
  }

  function fullScanNudge() {
    return `<div class="panel gate slim"><p>This was the 100-platform Quick scan. ${signedIn() ? "Run" : "Sign in to run"} a
      <strong>Standard scan across 500+ platforms</strong> with complete results.</p>
      <div class="gate-actions"><button type="button" class="btn btn-ghost btn-sm" data-gate="${signedIn() ? "full" : "signin-full"}">${signedIn() ? "Run Standard scan" : "Sign in for Standard"}</button></div></div>`;
  }

  // Addresses and identifiers the handle leaks, as opposed to where it exists.
  // Kept above the profile grid because it is the finding a person is least
  // likely to already know about themselves.
  function exposuresPanel(exposures) {
    if (!exposures.length) return "";
    let rows = "";
    exposures.forEach((x) => {
      (x.emails || []).forEach((m) => {
        rows += `<div class="expo-row">
          <div class="expo-val">${esc(m.email)}
            <button class="pivot-chip" data-pivot data-tool="email" data-query="${esc(m.email)}"
              title="Check this address for breaches">check breaches</button></div>
          <div class="expo-why">published in ${m.commits} public commit${m.commits === 1 ? "" : "s"}
            across ${(m.repos || []).length} repositor${(m.repos || []).length === 1 ? "y" : "ies"}
            as “${esc(m.name || "")}”</div>
        </div>`;
      });
      if (x.protected) {
        rows += `<div class="expo-row ok"><div class="expo-val">No address exposed</div>
          <div class="expo-why">every public commit uses GitHub's noreply address</div></div>`;
      }
      if (x.limited) {
        // Not a finding and not a clean result: say it was skipped and when it
        // can run again, without developer jargon about tokens.
        const at = x.retry_at
          ? new Date(x.retry_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : "";
        rows += `<div class="expo-row"><div class="expo-why">Commit email check skipped this time,
          GitHub's free lookups are busy${at ? `. Scan again after ${esc(at)} to include it` : ". Scan again later to include it"}.</div></div>`;
      } else if (x.error) {
        rows += `<div class="expo-row"><div class="expo-why">Commit email check could not run, ${esc(x.error)}</div></div>`;
      }
    });
    if (!rows) return "";
    return `<div class="panel expo">
      <div class="section-label">Leaked in public commit metadata</div>${rows}</div>`;
  }

  // What we checked and deliberately did not report. Every other tool in this
  // category shows these as green ticks; stating the reason is the whole point.
  function rejectedPanel(rejected, checked) {
    if (!rejected.length) return "";
    const rows = rejected.map((x) => `<tr>
      <td>${esc(x.platform)}</td>
      <td class="rj-code">${esc(String(x.status_code || "-"))}</td>
      <td class="rj-why">${esc(x.reason)}</td></tr>`).join("");
    return `<details class="panel rejected">
      <summary>${checked} platforms checked · ${rejected.length} not confirmed
        <span class="hint">why we didn't report these</span></summary>
      <div class="rj-scroll"><table class="rj-table"><tbody>${rows}</tbody></table></div>
    </details>`;
  }

  function stat(n, label) {
    n = n || 0;
    return `<div class="stat"><div class="num" data-countup="${n}">0</div><div class="lbl">${esc(label)}</div></div>`;
  }

  function clusterCard(c) {
    const conf = c.confidence || 0;
    const platforms = (c.platforms || []).map((p) =>
      `<a class="meta-tag" href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener nofollow">${esc(p.platform)}</a>`
    ).join("");
    return `<div class="card" style="grid-column:1/-1;margin-bottom:14px">
      <div class="card-head">
        ${avatarHTML(c, (c.display_name || c.username || "?").charAt(0).toUpperCase())}
        <div style="min-width:0">
          <div class="card-title">${esc(c.display_name || c.username || "Correlated identity")}</div>
          <div class="card-url">Cross-platform match</div>
        </div>
        <span class="tag profile">${conf}% match</span>
      </div>
      ${c.bio ? `<div class="card-bio">${esc(c.bio.slice(0, 160))}</div>` : ""}
      <div class="card-meta">${platforms}</div>
    </div>`;
  }

  function profileCard(r, live = false) {
    const platform = r.platform || r.source || hostOf(r.url) || "Result";
    const cat = r.category || "mention";
    const fallback = (platform[0] || "?").toUpperCase();
    let meta = "";
    // "low" is reported, not hidden: the platform answered without an error but
    // served nothing that distinguishes a real account from a missing one. The
    // label has to say that, or an unverifiable hit reads as a confirmed one.
    if (r.confidence === "low") meta += `<span class="meta-tag conf-low" title="This platform returns the same page whether or not the account exists">Unconfirmed</span>`;
    else if (r.confidence === "medium") meta += `<span class="meta-tag conf-medium">Possible match</span>`;
    else if (r.confidence === "high") meta += `<span class="meta-tag conf-high">Confirmed</span>`;
    if (r.followers || r.followers === 0) meta += `<span class="meta-tag">${fmtNum(r.followers)} followers</span>`;
    Object.entries(r.statistics || {}).filter(([key, value]) => key !== "followers" && Number.isFinite(value))
      .forEach(([key, value]) => { meta += `<span class="meta-tag">${fmtNum(value)} ${esc(key.replace(/_/g, " "))}</span>`; });
    if (r.is_verified) meta += `<span class="meta-tag">Verified</span>`;
    if (r.is_private) meta += `<span class="meta-tag">Private</span>`;
    if (r.repos) meta += `<span class="meta-tag">${fmtNum(r.repos)} repos</span>`;
    const href = r.url && /^https?:\/\//.test(r.url) ? r.url : null;
    // Sourced adapter metadata carries its own links, so such a card is not an
    // <a>: nested anchors are invalid and would swallow the link clicks.
    const publicLinks = (Array.isArray(r.public_links) ? r.public_links : []).filter(u => /^https?:\/\//i.test(u) && safeUrl(u));
    const hasDetails = publicLinks.length > 0 || Boolean(r.metadata_source);
    // On demand, never during the scan: archive.org needs ~10s per cold key
    // and throttles under fan-out. A span, not a button, the card is an <a>.
    // Left off live cards: its handler is bound only when the final result
    // renders, so on a live card a click would just open the profile.
    if (href && !live) meta += `<span class="meta-tag wb" data-wayback="${esc(href)}"
      role="button" tabindex="0" title="Look up archive.org history">archive history</span>`;
    const inner = `
      <div class="card-head">
        ${avatarHTML(r, fallback)}
        <div style="min-width:0">
          <div class="card-title">${esc(platform)}</div>
          <div class="card-url">${hasDetails && href ? `<a href="${esc(safeUrl(href))}" target="_blank" rel="noopener nofollow">Open profile ${icon("external", 12)}</a>` : `${esc(hostOf(r.url))}${href ? ` <span class="open-ico">${icon("external", 12)}</span>` : ""}`}</div>
        </div>
        <span class="tag ${esc(cat)}">${esc(cat)}</span>
      </div>
      ${r.display_name && r.display_name !== platform ? `<div class="card-bio" style="font-weight:600;color:var(--text)">${esc(r.display_name)}</div>` : ""}
      ${r.bio ? `<div class="card-bio">${esc(r.bio.slice(0, 150))}</div>` : ""}
      ${r.metadata_source ? `<div class="hint">Source: ${safeUrl(r.metadata_source.url) ? `<a href="${esc(safeUrl(r.metadata_source.url))}" target="_blank" rel="noopener nofollow">${esc(r.metadata_source.platform || platform)} public account data</a>` : esc(r.metadata_source.platform || platform)}</div>` : ""}
      ${publicLinks.length ? `<div class="card-bio">Public links: ${publicLinks.map(u => `<a href="${esc(safeUrl(u))}" target="_blank" rel="noopener nofollow">${esc(hostOf(u))}</a>`).join(" · ")}</div>` : ""}
      ${meta ? `<div class="card-meta">${meta}</div>` : ""}`;
    if (href && !hasDetails) {
      return `<a class="card card-link" href="${esc(safeUrl(href))}" target="_blank" rel="noopener nofollow"
        aria-label="Open ${esc(platform)} profile in a new tab">${inner}</a>`;
    }
    return `<div class="card">${inner}</div>`;
  }

  // -- Email results
  function emailQualityBadges(record, compact = false) {
    let html = "";
    const score = record?.confidence;
    if (score?.method === "source-basis-v1" && Number.isInteger(score.score) && score.scale === 4 && score.score >= 0 && score.score <= 4) {
      html += `<span class="pill" title="${esc(score.label || "Evidence strength")} · ${esc(score.reason || "Rule-based association score; not a probability of identity.")}">Evidence strength ${score.score}/4</span>`;
    }
    const age = record?.freshness;
    if (age?.label && (!compact || age.status !== "unknown")) {
      html += `<span class="pill${["potentially_outdated", "future_date", "invalid_date"].includes(age.status) ? " danger" : ""}" title="${esc(age.reason || "Recency is source-reported")}">${esc(age.label)}</span>`;
    }
    return html ? `<span class="email-quality-badges">${html}</span>` : "";
  }

  function emailFieldConflicts(profile) {
    const rows = Object.entries(profile.field_conflicts || {}).filter(([, alternatives]) => Array.isArray(alternatives) && alternatives.length > 1);
    if (!rows.length) return "";
    return `<details class="registration-coverage email-field-conflicts"><summary>Source values differ for ${rows.length} ${rows.length === 1 ? "field" : "fields"}</summary><ul>${rows.map(([field, alternatives]) => `<li><strong>${esc(field)}</strong><ul>${alternatives.slice(0, 5).map(value => `<li>${esc(typeof value.value === "object" ? JSON.stringify(value.value).slice(0, 1000) : String(value.value ?? "").slice(0, 1000))}<span class="hint"> · ${esc(value.source || "Source not specified")}${value.basis ? " · " + esc(value.basis.replace(/_/g, " ")) : ""}</span></li>`).join("")}</ul></li>`).join("")}</ul></details>`;
  }

  function emailEvidenceOverview(data) {
    const report = data.evidence_report;
    if (!report) return ""; // Older saved reports keep their original evidence.
    const counts = report.counts || {};
    const identity = report.identity || {};
    const photos = new Map();
    (report.profiles || []).forEach(p => {
      const url = safeUrl(p.avatar_url);
      if (!url) return;
      if (!photos.has(url)) photos.set(url, []);
      photos.get(url).push(p);
    });
    const field = (label, values, usernameActions = false) => `<div class="email-identity-field"><h3>${label}</h3>${values?.length
      ? values.map((v) => `<p>${safeUrl(v.url) ? `<a href="${esc(safeUrl(v.url))}" target="_blank" rel="noopener nofollow"><strong>${esc(v.value)}</strong></a>` : `<strong>${esc(v.value)}</strong>`}<span>${esc(v.source)}${v.basis === "historical_commit" ? " · historical commit association" : v.basis === "historical_breach" ? " · historical breach" : ""}</span>${usernameActions && String(v.value || "").trim() ? `<button type="button" class="btn btn-ghost btn-sm" data-email-username="${esc(v.value)}" aria-label="Search this username: ${esc(v.value)}">Search this username</button>` : ""}</p>`).join("")
      : `<p class="hint">Not returned by checked sources</p>`}${usernameActions && values?.length ? `<p class="hint">Opens the username scanner for you to run. Matches to a handle do not verify the same person.</p>` : ""}</div>`;
    return `<section class="email-overview" aria-label="Email evidence summary">
      <div class="email-overview-evidence">
      ${emailPlatformSummary(data)}
      <div class="email-evidence-counts">${[["Public profiles", counts.public_profiles], ["Registration signals", counts.registration_signals], ["Historical services", counts.historical_services], ["Named breaches", counts.named_breaches]].map(([label, n]) => `<div><strong>${esc(n || 0)}</strong><span>${label}</span></div>`).join("")}</div>
      <p class="hint">${esc(report.counts_note || "Counts describe returned evidence. Categories can overlap; zero does not prove no account or exposure.")}</p>
      ${report.confidence_note ? `<details class="registration-coverage email-quality-method"><summary>How evidence strength and age are assessed</summary><p class="hint">${esc(report.confidence_note)}</p><p class="hint">${esc(report.freshness_note || "Retrieval time is not an activity date.")}</p>${report.generated_at ? `<p class="hint">Report collected: ${esc(report.generated_at)}</p>` : ""}</details>` : ""}
      ${data.account_checks?.enabled === false ? `<p class="hint">Live profile and registration checks are off. Enable “Check linked accounts” to include them in a new lookup.</p>` : ""}
      <div class="email-evidence-range"><div><span>Earliest dated evidence</span><strong>${esc(report.earliest?.date_label || "Not available")}</strong></div><div><span>Latest dated evidence</span><strong>${esc(report.latest?.date_label || "Not available")}</strong></div></div>
      <p class="hint">${esc(report.date_note)}</p>
      </div><div class="email-overview-identity">
      <div class="section-label">Profile summary</div><div class="email-identity-grid">${field("Names reported", identity.display_name)}${field("Usernames", identity.username, true)}
        <div class="email-identity-field"><h3>Profile pictures</h3><div class="email-photo-strip">${[...photos.values()].map(group => `<figure>${avatarHTML(group[0], String(group[0].platform).slice(0, 2), true)}<figcaption>${[...new Set(group.map(p => p.platform))].map(esc).join(" · ")}</figcaption></figure>`).join("") || `<p class="hint">Not returned by checked sources</p>`}</div></div>
        <div class="email-identity-field"><h3>Profile links</h3>${(report.profiles || []).filter(p => safeUrl(p.url)).map(p => `<p><a href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener nofollow">${esc(p.display_name || p.username || p.platform)} ↗</a><span>${esc(p.platform)}</span></p>`).join("") || `<p class="hint">Not returned by checked sources</p>`}</div></div>
      ${emailLocations(report.locations || identity.location || [])}
      <p class="hint">${esc(report.identity_note)}</p>
      </div>
    </section>`;
  }

  function emailPlatformSummary(data) {
    const summary = window.MyReconEmailOutcome.platforms?.(data);
    if (!summary) return "";
    const coverage = summary.coverage || {};
    const observed = (data.platform_summary?.platforms || []).filter(p => p.status === "found");
    const names = summary.names || [];
    const chips = names.map(name => {
      const row = observed.find(p => p.name === name);
      const href = safeUrl(row?.url);
      return href ? `<a class="pill" href="${esc(href)}" target="_blank" rel="noopener nofollow">${esc(name)} ↗</a>` : `<span class="pill">${esc(name)}</span>`;
    }).join("");
    const completed = Number.isFinite(coverage.completed) ? coverage.completed : 0;
    const attempted = Number.isFinite(coverage.attempted) ? coverage.attempted : 0;
    const gap = Number.isFinite(coverage.unavailable) ? coverage.unavailable : 0;
    return `<div class="email-platform-summary" aria-label="Email linked platforms">
      <div class="email-platform-head"><div><span class="hint">Platforms associated with this email</span><h3>${esc(summary.linked)} <span>${summary.linked === 1 ? "linked platform" : "linked platforms"}</span></h3></div><span class="pill">${esc(coverage.status || "unknown")}</span></div>
      <p class="hint">${esc(summary.detail)}</p>
      ${chips ? `<div class="chips" aria-label="Source-associated platforms">${chips}</div>` : `<p class="hint">No linked-platform evidence was returned by the available sources.</p>`}
      <p class="hint">${coverage.enabled === false ? "Linked-account checks were off." : `${completed} of ${attempted} platform checks completed${gap ? ` · ${gap} could not establish an answer` : ""}.`}${summary.historical ? ` ${summary.historical} platforms also have historical evidence.` : ""}</p>
    </div>`;
  }

  function emailLocations(locations) {
    const row = v => `<li>${safeUrl(v.url) ? `<a href="${esc(safeUrl(v.url))}" target="_blank" rel="noopener nofollow">${esc(v.value)} ↗</a>` : esc(v.value)}<span>${esc(v.source)} · ${v.basis === "review_venue" ? "review venue" : "profile location"}${v.date_label ? " · " + esc(v.date_label) : ""}${Number.isFinite(v.latitude) && Number.isFinite(v.longitude) ? ` · ${v.latitude.toFixed(4)}, ${v.longitude.toFixed(4)}` : ""}</span></li>`;
    return `<div class="email-locations"><h3>Locations</h3>${locations.length ? `<ul>${locations.slice(0, 6).map(row).join("")}</ul>${locations.length > 6 ? `<details><summary>Show ${locations.length - 6} more locations</summary><ul>${locations.slice(6).map(row).join("")}</ul></details>` : ""}` : `<p class="hint">Not returned by checked sources</p>`}</div>`;
  }

  function emailProfileCollections(p, data = {}) {
    if (p._guest_collections_locked) return `<p class="hint">Additional finding cards are listed separately below.</p>`;
    const reviews = p.reviews || [];
    const reviewState = window.MyReconEmailOutcome.reviews?.(p, data);
    const link = (label, value) => safeUrl(value) ? `<a href="${esc(safeUrl(value))}" target="_blank" rel="noopener nofollow">${label} ↗</a>` : "";
    const reviewHTML = reviews.length ? `<div class="email-profile-collection email-google-reviews"><h3>Google reviews and ratings <span>${reviews.length} items returned${reviewState?.totalReported !== null && reviewState?.totalReported !== undefined ? ` · ${esc(reviewState.totalReported)} reviews reported by source` : ""}</span></h3>${reviewState ? `<p class="hint">${esc(reviewState.detail)}</p>` : ""}${reviews.map(r => {
      const coordinates = Number.isFinite(r.latitude) && Number.isFinite(r.longitude) ? `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}` : "";
      const maps = r.maps_url || (coordinates ? `https://www.google.com/maps?q=${r.latitude},${r.longitude}` : "");
      const rating = Number.isFinite(r.rating) && r.rating >= 0 && r.rating <= 5 ? r.rating : null;
      return `<article class="email-review"><div class="email-review-heading"><h4>${esc(r.name || "Review venue")}</h4>${rating !== null ? `<span class="email-review-rating" aria-label="${rating} out of 5 stars">${"★".repeat(Math.round(rating))}<small>${rating}/5</small></span>` : ""}</div>
        ${r.address ? `<p class="hint">${esc(r.address)}</p>` : ""}${r.text ? `<p>${esc(r.text)}</p>` : `<p class="hint">Review text not returned</p>`}
        ${r.owner_reply ? `<blockquote><span>Owner reply${r.owner_reply_date ? " · " + esc(r.owner_reply_date) : ""}</span><p>${esc(r.owner_reply)}</p></blockquote>` : ""}
        <footer><span>${esc(r.date_label || r.date || "Date not provided")}${coordinates ? " · " + esc(coordinates) : ""}${r.source || reviewState?.source ? " · " + esc(r.source || reviewState.source) : ""}</span><div>${link("Open in Maps", maps)}${link("Source", r.source_url)}</div></footer></article>`;
    }).join("")}</div>` : "";
    const careerDate = value => {
      const match = /^(\d{4})-(\d{2})$/.exec(String(value || ""));
      return match && Number(match[2]) >= 1 && Number(match[2]) <= 12
        ? `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(match[2]) - 1]} ${match[1]}` : value;
    };
    const history = (label, rows, title, subtitle) => rows?.length ? `<div class="email-profile-collection"><h3>${label}<span>${rows.length} ${rows.length === 1 ? "item" : "items"}</span></h3>${rows.map(r => `<article class="email-career"><h4>${esc(r[title] || "Not provided")}${r.current ? `<span class="pill ok">Current</span>` : ""}</h4>${r[subtitle] ? `<p>${esc(r[subtitle])}</p>` : ""}<p class="hint">${esc(careerDate(r.start) || "Start not provided")} · ${esc(r.current ? "Present" : careerDate(r.end) || "End not provided")}</p>${r.field_of_study ? `<p>${esc(r.field_of_study)}</p>` : ""}${r.description ? `<p>${esc(r.description)}</p>` : ""}${link("Source", r.url)}</article>`).join("")}</div>` : "";
    const missing = String(p.platform).toLowerCase() === "google" && !reviews.length ? `<div class="email-review-availability"><strong>${esc(reviewState?.label || "Google review details not returned")}</strong><p class="hint">${esc(reviewState?.detail || "The available source did not return individual reviews.")}</p>${link("View public Maps contributions", p.url)}</div>` : "";
    return reviewHTML + missing + history("LinkedIn positions", p.positions, "title", "company") + history("LinkedIn education", p.education, "school", "degree");
  }

  function emailRegistrations(data) {
    const rows = data.evidence_report?.registrations || [];
    if (!rows.length) return "";
    return `<section class="email-registrations"><div class="section-label">Registrations <span class="hint">${rows.length} services returned a signal</span></div><div class="chips">${rows.map(r => `<span class="pill" title="${esc(r.source || "Holehe")} · ${esc(r.reason || "Registration signal")}">${esc(r.service)}</span>`).join("")}</div></section>`;
  }

  function emailEvidenceTimeline(data) {
    const report = data.evidence_report;
    if (!report) return "";
    const rows = report.timeline || [], undated = report.undated_events || [];
    const item = (r) => `<li data-email-event="${esc(r.kind)}"><time${r.date ? ` datetime="${esc(r.date)}"` : ""}>${esc(r.date_label)}${["year", "month"].includes(r.precision) ? `<small>${esc(r.precision)} only</small>` : ""}</time><div><strong>${esc(r.title)}</strong>${r.date_conflict ? `<span class="pill">Source dates differ</span>` : ""}<span class="email-event-source">${(r.sources || []).map(esc).join(" · ")}</span>${r.detail && (r.kind !== "breach" || r.date_conflict) ? `<p>${esc(r.detail)}</p>` : ""}${r.date_evidence?.length > 1 ? `<details class="email-event-dates"><summary>Reported dates</summary><ul>${r.date_evidence.map(d => `<li>${esc(d.date_label)} · ${(d.sources || []).map(esc).join(" · ")}</li>`).join("")}</ul></details>` : ""}${safeUrl(r.url) ? `<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener nofollow">View source ↗</a>` : ""}</div></li>`;
    return `<section class="email-evidence-timeline" aria-label="Evidence timeline">
      <div class="section-label">Activity timeline<span class="hint">${rows.length} dated events</span></div>
      <p class="hint">Newest first. Breach dates describe the incident; profile dates describe the account. These are not the first or last use of this email. Compatible dates from multiple sources appear once.</p>
      ${rows.length ? `<div class="email-timeline-filters" role="group" aria-label="Filter evidence timeline">${[["all", "All evidence"], ["profile", "Profiles"], ["activity", "Public activity"], ["breach", "Breaches"]].map(([kind, label]) => `<button type="button" class="btn btn-ghost btn-sm" data-action="email-timeline-filter" data-kind="${kind}" aria-pressed="${kind === "all"}">${label}</button>`).join("")}</div><ol class="email-event-list">${rows.map(item).join("")}</ol><p class="hint email-timeline-empty" hidden>No dated events in this category.</p>`
        : `<p class="email-evidence-empty">No usable dates were returned. Undated findings are still shown below.</p>`}
      ${undated.length ? `<details class="email-undated"><summary>${undated.length} undated findings</summary><ol class="email-event-list">${undated.map(item).join("")}</ol></details>` : ""}
    </section>`;
  }

  function emailProfileCards(data) {
    const profiles = data.evidence_report?.profiles;
    if (!profiles?.length) return "";
    return `<section class="email-profiles" aria-label="Public profile details"><div class="section-label">Public profiles<span class="hint">${profiles.length} returned</span></div><div class="email-profile-grid">${profiles.map((p) => {
      const href = safeUrl(p.url);
      const details = [["Username", p.username], ["Location (source-reported)", p.location], ["Company (self-reported)", p.company], ...Object.entries(p.fields || {})];
      return `<article class="card email-profile-card${p.reviews?.length || p.positions?.length || p.education?.length ? " email-profile-wide" : ""}"><div class="card-head">${avatarHTML(p, String(p.platform).slice(0, 2), true)}<div><div class="card-title">${esc(p.platform)}</div><div class="card-url">${esc(p.display_name || p.username || p.platform)}</div></div></div>
        <span class="pill">${p.basis === "historical_commit" ? "Historical commit association" : p.basis === "provider_email" ? "Provider email association" : p.basis === "public_link" ? "Publicly linked profile" : p.basis === "historical_public_link" ? "Historical linked profile" : p.basis === "email_hash" ? "Email-hash association" : "Public email evidence"}</span>
        ${emailQualityBadges(p)}
        ${emailFieldConflicts(p)}
        ${p.bio ? `<p class="card-bio">${esc(p.bio)}</p>` : ""}
        <dl class="email-profile-fields">${details.filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}${Object.entries(p.stats || {}).map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>
        ${Object.entries(p.lists || {}).map(([k, rows]) => `<div class="email-profile-list"><h4>${esc(k)}</h4><div class="chips">${rows.map(v => `<span class="pill">${esc(v)}</span>`).join("")}</div></div>`).join("")}
        ${p.last_seen ? `<p class="hint">Last seen (source-reported): ${esc(p.last_seen)}</p>` : ""}${emailProfileCollections(p, data)}
        <p class="hint">${esc(p.evidence)}</p><p class="email-event-source">${esc(p.source)}</p>
        ${p.profile_status && p.profile_status !== "ok" ? `<p class="hint">Profile details ${esc(p.profile_status.replace(/_/g, " "))}; the original email evidence is retained.</p>` : ""}
        <div class="email-profile-links">${href ? `<a href="${esc(href)}" target="_blank" rel="noopener nofollow">Open profile ↗</a>` : ""}${safeUrl(p.evidence_url) && p.evidence_url !== p.url ? `<a href="${esc(safeUrl(p.evidence_url))}" target="_blank" rel="noopener nofollow">View email evidence ↗</a>` : ""}${safeUrl(p.website) ? `<a href="${esc(safeUrl(p.website))}" target="_blank" rel="noopener nofollow">Declared website ↗</a>` : ""}</div>
      </article>`;
    }).join("")}</div></section>`;
  }

  function renderEmail(data) {
    const a = data.analysis || {}, g = data.gravatar || {}, s = data.summary || {};
    const breaches = data.breaches || {}, hibp = data.hibp;
    let html = resultsHeader(`Email intelligence: ${esc(data.query.email)}`, "");
    html += window.MyReconPartial?.notice(data) || "";
    html += emailEvidenceOverview(data);

    const outcome = window.MyReconEmailOutcome(data);
    const exp = outcome.partial || data.partial ? null : computeExposure("email", data);
    lastExposure = exp;
    const dw = data.darkweb || {};
    const breached = outcome.found, count = s.breach_count || 0;
    html += `<div class="breach ${outcome.state === "no_match" ? "clean" : !breached ? "incomplete" : ""}" role="status">
      <h3>${esc(outcome.label)}
        <span class="sev" style="color:${breached ? "var(--danger)" : outcome.partial ? "var(--warn)" : "var(--ok)"}">${breached
          ? count > 0 ? count.toLocaleString() + (count === 1 ? " breach" : " breaches") : "detected"
          : outcome.state === "no_match" ? "no match" : outcome.state}</span>
      </h3>
      <p>${esc(outcome.coverage)}${outcome.partial ? " · coverage incomplete" : ""}.</p>
      <p>${esc(outcome.detail)}</p>
      ${outcome.partial ? `<p>Exposure score unavailable until all attempted sources respond.</p>` : ""}
      <ul class="source-coverage">${outcome.sources.map((source) => `<li><strong>${esc(source.name)}</strong>: ${esc(source.status === "ok" && source.checked !== false ? "checked" : source.status.replace(/_/g, " "))}${source.error ? ", " + esc(source.error) : ""}</li>`).join("")}</ul>
      ${outcome.partial ? `<button type="button" class="btn btn-ghost btn-sm" data-action="retry-email">Retry breach check</button>${s.retry_after ? `<p>Source suggests waiting ${esc(s.retry_after)} seconds before retrying.</p>` : ""}` : ""}
      ${breached ? `<div class="breach-metrics">
        ${dw.risk_label ? `<div class="bm"><span>Risk</span><strong>${esc(dw.risk_label)}</strong></div>` : ""}
        ${dw.records_exposed ? `<div class="bm"><span>Records in these dumps</span><strong>${fmtNum(dw.records_exposed)}</strong></div>` : ""}
        ${s.records_found ? `<div class="bm"><span>Rows naming this address</span><strong>${s.records_found.toLocaleString()}</strong></div>` : ""}
        ${dw.pastes ? `<div class="bm"><span>Pastes</span><strong>${dw.pastes}</strong></div>` : ""}
      </div>` : ""}
      ${breaches.fields && breaches.fields.length ? `<div class="chips">${breaches.fields.slice(0, 14).map((f) => {
        const danger = ["password", "hash", "ssn", "phone", "address", "dob", "ip"].includes(String(f).toLowerCase());
        return `<span class="pill ${danger ? "danger" : ""}">${esc(f)}</span>`;
      }).join("")}</div>` : ""}
      ${dw.error ? `<div class="hint" style="margin-top:10px">${esc(dw.error)}</div>` : ""}
    </div>`;

    html += emailEvidenceTimeline(data);
    html += emailBreachList(data);
    html += emailProfileCards(data);
    html += emailRegistrations(data);
    if (data.profile_enrichment?.status === "unconfigured" && data.account_checks?.enabled) html += `<p class="hint email-enrichment-gap">Google reviews and LinkedIn details are unavailable until a profile data source is connected.</p>`;
    if (data.profile_enrichment?.sources?.length) html += `<details class="registration-coverage"><summary>Profile source coverage</summary><ul class="source-coverage">${data.profile_enrichment.sources.map(r => `<li><strong>${esc(r.name)}${r.provider ? " · " + esc(r.provider) : ""}</strong>: ${esc(r.status.replace(/_/g, " "))}${r.message || r.reason ? `<p class="hint">${esc(r.message || r.reason)}</p>` : ""}${Number.isFinite(r.returned) ? `<p class="hint">${esc(r.returned)} items returned${r.limit ? " · retrieval limit " + esc(r.limit) : ""}</p>` : ""}</li>`).join("")}</ul></details>`;
    html += linkedServices(data.linked_services, data.account_checks, data.registration_checks);
    if (exp) html += exposureGauge(exp);
    else if (data.partial && !outcome.partial) html += `<p class="hint">Exposure score unavailable while linked-account source coverage is incomplete.</p>`;

    // Straight under the verdict: it is what someone who just learned they
    // were breached needs next, and the evidence below can run to 30 cards.
    html += emailNextSteps(outcome, data);
    html += breachAlertCta(outcome);

    if (dw.timeline && dw.timeline.length > 1) {
      const peak = Math.max(...dw.timeline.map((t) => t.count));
      html += `<div class="section-label">Exposure over time</div>
        <div class="timeline" role="img" aria-label="Breaches per year">
          ${dw.timeline.map((t) => `
            <div class="tl-col" title="${t.year}: ${t.count} breach${t.count === 1 ? "" : "es"}">
              <div class="tl-bar" style="height:${Math.max(6, (t.count / peak) * 100).toFixed(1)}%"></div>
              <div class="tl-y">${String(t.year).slice(2)}</div>
            </div>`).join("")}
        </div>`;
    }

    const emailDomain = baseDomain(data.query.email.split("@")[1] || "");
    html += pivotRow("Pivot", [
      pivotChip("domain", emailDomain, emailDomain),
      ...(a.mx_hosts || []).map((h) => { const d = baseDomain(h); return d && d !== emailDomain ? pivotChip("domain", d, d) : ""; }),
      data.github ? pivotChip("username", data.github.username, data.github.username) : "",
    ]);

    // Results cached before linked_services existed still show the old chips.
    if (!data.linked_services && s.linked_accounts && s.linked_accounts.length) {
      html += `<div class="section-label">Linked accounts</div>`;
      html += `<div class="chips">${s.linked_accounts.map((x) => `<span class="pill">${esc(x)}</span>`).join("")}</div>`;
    }

    if (g.exists && !data.evidence_report) {
      html += `<div class="section-label">Gravatar profile</div>`;
      html += `<div class="card"><div class="card-head">${avatarHTML(g, "G")}
        <div style="min-width:0"><div class="card-title">${esc(g.display_name || "Gravatar")}</div>
        <div class="card-url"><a href="${esc(safeUrl(g.profile_url))}" target="_blank" rel="noopener nofollow">${esc(hostOf(g.profile_url) || "gravatar.com")}</a></div></div></div>
        ${g.bio ? `<div class="card-bio">${esc(g.bio)}</div>` : ""}</div>`;
    }
    if (data.github && !data.evidence_report) {
      html += `<div class="section-label">GitHub</div>`;
      html += `<div class="card"><div class="card-head">${avatarHTML({ avatar_url: data.github.avatar_url }, "GH")}
        <div style="min-width:0"><div class="card-title">${esc(data.github.username)}</div>
        <div class="card-url"><a href="${esc(safeUrl(data.github.url))}" target="_blank" rel="noopener nofollow">github.com</a></div></div></div>
        <p class="card-bio">${esc(data.github.evidence || "Public GitHub evidence for this email")}</p>
        ${data.github.evidence_url ? `<p><a href="${esc(safeUrl(data.github.evidence_url))}" target="_blank" rel="noopener nofollow">View public commit evidence</a></p>` : ""}</div>`;
    }
    resultsEl().innerHTML = html;
    window.EmailPhotos?.wire(resultsEl(), CFG.apiBase);
    animateCountUps();
    linkBreachWriteups();
  }

  // Keep every named breach visible, even when the detailed analytics fail.
  function emailBreachRows(data) {
    const rows = new Map();
    const key = (name) => String(name || "").toLowerCase().replace(/\.(com|net|org|io|co|me|ru|de|fr|uk|in)$/, "").replace(/[^a-z0-9]/g, "");
    const add = (record, source, detailed) => {
      const id = key(record.name);
      if (!id) return;
      const existing = rows.get(id);
      if (existing) {
        if (!existing.sources.includes(source)) existing.sources.push(source);
        if (record.date && (!existing.date || (String(record.date).startsWith(String(existing.date) + "-") && /^\d{4}(?:-\d{2}){0,2}$/.test(record.date)))) existing.date = record.date;
        return;
      }
      rows.set(id, { ...record, detailed, sources: [source] });
    };
    ((data.darkweb || {}).breaches || []).forEach((b) => add(b, "XposedOrNot analytics", true));
    [data.breaches, data.fallback].forEach((source) => {
      if (!source || source.status === "skipped") return;
      (source.sources || []).forEach((b) => add(b, source.source || (source === data.breaches ? "LeakCheck" : "XposedOrNot fallback"), false));
    });
    (data.breach_details?.records || []).forEach(r => {
      add(r, "LeakCheck Pro", true);
      const row = rows.get(key(r.name));
      (row.identities ||= []).push(r);
    });
    return [...rows.values()].sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")) || a.name.localeCompare(b.name));
  }

  function emailBreachList(data) {
    const rows = emailBreachRows(data);
    if (!rows.length) return window.MyReconEmailOutcome(data).found
      ? `<p class="hint">Exposure was reported, but the responding sources supplied no breach names.</p>` : "";
    const count = Math.max(rows.length, data.summary?.breach_count || 0);
    return `<section class="email-breaches" aria-label="Breaches naming this email">
      <div class="section-label">Which breaches included this email?<span class="hint">${rows.length} named${count > rows.length ? ` of ${count} reported` : ""}</span></div>
      <p class="hint">Newest dated entries first. Exposed data describes the breach, not the exact values leaked about you. A historical entry does not confirm an account is still active.</p>
      <div class="breach-list">${rows.map((b) => `<article class="breach-card" data-bname="${esc(b.name)}" data-byear="${esc(String(b.date || "").slice(0, 4))}">
        <div class="bc-overview"><div class="bc-title"><h3 class="bc-name">${esc(b.name)}</h3><span class="bc-meta">${b.date ? `Breach date: ${esc(b.date)}` : "Date not provided"}</span></div>
          <p class="bc-source">Reported by ${b.sources.map(esc).join(" · ")}</p>
          ${(b.identities || []).map(r => `<dl class="email-profile-fields">${r.username ? `<div><dt>Historical username</dt><dd>${esc(r.username)}</dd></div>` : ""}${r.full_name ? `<div><dt>Name in this record</dt><dd>${esc(r.full_name)}</dd></div>` : ""}${r.password_exposed ? `<div><dt>Password</dt><dd>Exposure reported</dd></div>` : ""}</dl>${r.unverified ? `<p class="hint">Source marks this record as unverified.</p>` : ""}${r.compilation ? `<p class="hint">Compilation record; does not establish a platform account.</p>` : ""}`).join("")}
          ${b.password_risk === "plaintext" ? `<p class="pill danger">Plaintext passwords in this breach</p>` : ""}
          <div class="bc-fields"><strong>Data exposed</strong>${b.exposed?.length ? `<div class="chips">${b.exposed.map((f) => `<span class="pill ${/password|ssn|bank|card|phone|address|birth|token/i.test(f) ? "danger" : ""}">${esc(f)}</span>`).join("")}</div>` : `<p class="hint">Per-breach data types not provided by this source.</p>`}</div>
          ${b.details || b.records || b.industry ? `<details class="bc-details"><summary>More about this breach</summary><div class="bc-body">${b.details ? `<p>${esc(b.details)}</p>` : ""}${b.records ? `<p>${fmtNum(b.records)} records across the whole breach.</p>` : ""}${b.industry ? `<p>Industry: ${esc(b.industry)}</p>` : ""}</div></details>` : ""}
        </div>
      </article>`).join("")}</div></section>`;
  }

  // Services this address is tied to, each with the evidence that ties it.
  // Source kinds remain distinct, including optional registration signals.
  function linkedServices(ls, checks, registration) {
    if (!ls && !checks) return "";
    ls = ls || {};
    const rows = ls.services || [];
    let html = `<div class="section-label">Accounts and services linked to this email
      <span class="hint">${rows.length ? `${rows.length} service evidence entries` : "no evidence returned"}</span></div>`;
    if (rows.length) {
      html += `<ul class="svc-list">${rows.map((r) => {
        const tag = r.basis === "owner_declared" ? `<span class="pill">owner-declared link</span>`
          : r.basis === "historical_commit" ? `<span class="pill">historical commit evidence</span>`
          : r.basis === "provider_email" ? `<span class="pill">provider email association</span>`
          : r.kind === "profile" ? `<span class="pill ok">public profile evidence</span>`
          : r.kind === "registration" ? `<span class="pill">registration signal</span>`
          : `<span class="pill">historical breach${r.date ? " · " + esc(r.date) : ""}</span>`;
        const name = r.url
          ? `<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener nofollow">${esc(r.service)}</a>`
          : esc(r.service);
        return `<li><span class="svc-name">${name}</span>${tag}<span class="svc-ev">${esc(r.evidence)}${r.kind === "breach" ? ". Evidence of a past association; the account may have been closed." : ""}${r.registration_evidence ? ". " + esc(r.registration_evidence) : ""}</span></li>`;
      }).join("")}</ul>`;
    }
    if (checks?.enabled === false) {
      html += `<p class="hint">Live account checks are off. Breach-linked services still appear above. Turn on “Check linked accounts” and run the lookup for registration signals.</p>`;
    } else if (checks) {
      html += `<ul class="source-coverage">${(checks.sources || []).map((source) => `<li><strong>${esc(source.name)}</strong>: ${esc(source.status === "no_match" ? "no public match" : source.status.replace(/_/g, " "))}</li>`).join("")}</ul>`;
    }
    if (registration && registration.status !== "skipped") {
      const statuses = { found: "Registration signal", no_signal: "No registration signal", unavailable: "Unavailable", rate_limited: "Blocked or rate limited", timeout: "Timed out", skipped: "Skipped" };
      html += `<details class="registration-coverage"><summary>Email registration checks: ${registration.checked || 0} answered of ${registration.attempted || 0} eligible · ${registration.catalogue_count || 0} service checks</summary>
        <p class="hint">Every service has its own outcome. Skipped or blocked checks are not negative results.</p>
        <ul class="svc-list">${(registration.services || []).map((r) => `<li><span class="svc-name">${esc(r.service)}</span><span class="pill">${esc(statuses[r.status] || r.status)}</span><span class="svc-ev">${esc(r.engine || "Holehe")} · ${esc(r.reason)}</span></li>`).join("")}</ul></details>`;
    }
    html += `<p class="hint svc-note">Breach records show historical service associations. Registration signals are service responses, not verified profiles or proof of ownership. No signal does not prove no account. Combined leak lists are excluded from account evidence. <a href="https://github.com/megadose/holehe" target="_blank" rel="noopener">Holehe source</a></p>`;
    return html;
  }

  // What to do about an email result. Templated from the outcome, never
  // generated, and only for the two definite states, an incomplete check
  // already offers a retry, and advice would imply an answer it doesn't have.
  function emailNextSteps(outcome, data) {
    const pw = `<button type="button" class="linklike" data-action="open-password">check a password privately</button>`;
    if (outcome.found) {
      // Breach names are not listed here: many are combo lists and stealer-log
      // dumps (Collection-1, ExploitIN), which are not services with a password.
      const dw = data.darkweb || {};
      const exposed = [].concat((data.breaches || {}).fields || [], ...(dw.breaches || []).map((b) => b.exposed || []))
        .join(" ").toLowerCase();
      const steps = [
        `Change your password on each breached service you still use, and on any other account where you used the same password, reuse is what turns one breach into many.`,
        `Turn on two-factor authentication, ideally an authenticator app or a passkey rather than SMS. <a href="/guides/two-factor-authentication.html">Which kind to choose →</a>`,
        `Find out whether a password you still use is already in breach data: ${pw}, it is hashed in your browser and never sent.`,
        `Expect phishing that quotes these breaches back at you to sound credible. <a href="/guides/how-to-spot-phishing.html">How to spot it →</a>`,
      ];
      if (/phone/.test(exposed)) {
        // The field says the dump held phone numbers, not that it held this
        // person's, so the advice is conditional, not an accusation.
        steps.push(`At least one of these breaches included phone numbers. If yours may be among them, ask your carrier for a port-out or SIM PIN so the number cannot be moved to someone else's SIM. <a href="/guides/sim-swap-attacks.html">How SIM swaps work →</a>`);
      }
      steps.push(`If an account already looks taken over, <a href="/guides/account-hacked-what-to-do.html">follow the recovery steps in order →</a>`);
      return `<div class="section-label">What to do now</div><ul class="tips">${steps.map((s) => `<li>${s}</li>`).join("")}</ul>`;
    }
    if (outcome.state === "no_match") {
      return `<div class="section-label">What this does and doesn't mean</div><ul class="tips">
        <li>No match means this address isn't in the breach data these sources have published, not that it has never leaked. Breaches that were never disclosed, or not yet released, cannot appear here.</li>
        <li>A password can leak on its own, without this address beside it: ${pw}.</li>
        <li><a href="/guides/check-email-data-breach.html">How breach checks work, and where they are blind →</a></li>
      </ul>`;
    }
    return "";
  }

  // The one thing a one-off check cannot do is tell you about the next
  // breach. Offered after a definite answer only, an incomplete check gets a
  // retry, not a sales line. The app has two alerts and the copy keeps them
  // apart: the new-breach alert compares on the phone and sends nothing;
  // watching an address sends it to LeakCheck.
  // The link opens the Play custom listing that leads with alerts (Play shows
  // the main listing until it exists); the UTM tags are for Play Console.
  const PLAY_ALERTS_URL = "https://play.google.com/store/apps/details?id=com.Myrecon.osint&listing=breach-alerts"
    + "&referrer=utm_source%3Dmyrecon.xyz%26utm_medium%3Demail_result%26utm_campaign%3Dbreach_alerts";
  function breachAlertCta(outcome) {
    if (!outcome.found && outcome.state !== "no_match") return "";
    return `<div class="app-cta">
      <div class="app-cta-text">
        <strong>Get told when the next breach is published</strong>
        <p>MyRecon for Android checks for new breaches once a day, on your phone, and sends nothing to do it. It can also watch this address and tell you if it turns up in a new one, a separate switch, because that check has to send the address. Free, no account.</p>
      </div>
      <a class="btn btn-sm" href="${esc(PLAY_ALERTS_URL)}" target="_blank" rel="noopener">Get breach alerts</a>
    </div>`;
  }

  // Link a breach in an email result to our own write-up of it: a Breach
  // Files page, or a Case File. Matched on the exact normalised name, and for
  // case files the year too, because a wrong link is worse than none.
  let writeupIndex = null;
  const normName = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const sitePath = (u) => { try { return new URL(u).pathname; } catch { return ""; } };

  function loadWriteupIndex() {
    if (writeupIndex) return writeupIndex;
    const get = (u) => fetch(u).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
    writeupIndex = Promise.all([get("/assets/data/breaches.json"), get("/assets/data/case-files.json")])
      .then(([archive, cases]) => {
        const byName = new Map(), byNameYear = new Map();
        (archive.breaches || []).forEach((b) => {
          const path = sitePath(b.url), year = String(b.breach_date || "").slice(0, 4);
          if (path) [b.name, b.title].forEach((n) => n && byName.set(normName(n), { path, kind: "Breach file", year }));
        });
        (cases.cases || []).forEach((c) => {
          // "yahoo-2013-2014" → yahoo, [2013, 2014]; "marriott-starwood-2018"
          // is also reachable as "marriott", since the year pins it down.
          const m = String(c.slug || "").match(/^(.*?)-((?:\d{4}-?)+)$/);
          const path = sitePath(c.url);
          if (!m || !path) return;
          const years = m[2].split("-").filter(Boolean);
          const keys = new Set([normName(m[1]), normName(m[1].split("-")[0])]);
          keys.forEach((k) => years.forEach((y) => k && byNameYear.set(`${k}|${y}`, { path, kind: "Case file" })));
        });
        return { byName, byNameYear };
      });
    return writeupIndex;
  }

  async function linkBreachWriteups() {
    const cards = $$(".breach-card[data-bname]");
    if (!cards.length) return;
    const { byName, byNameYear } = await loadWriteupIndex();
    cards.forEach((card) => {
      const key = normName(card.dataset.bname), year = card.dataset.byear;
      const named = byName.get(key);
      // Disclosure often trails the breach, so the archive allows a year's drift.
      const sameBreach = named && (!named.year || !year || Math.abs(Number(named.year) - Number(year)) <= 1);
      const hit = byNameYear.get(`${key}|${year}`) || (sameBreach ? named : null);
      if (!hit || card.querySelector(".bc-writeup")) return;
      card.querySelector(".bc-name")?.insertAdjacentHTML("afterend",
        `<span class="pill bc-writeup">${esc(hit.kind.toLowerCase())}</span>`);
      (card.querySelector(".bc-body") || card.querySelector(".bc-overview"))?.insertAdjacentHTML("beforeend",
        `<p style="margin-top:10px"><a href="${esc(hit.path)}">Read our ${esc(hit.kind.toLowerCase())} on ${esc(card.dataset.bname)} →</a></p>`);
    });
  }

  // -- Domain results
  function renderDomain(data) {
    const w = data.whois || {}, dns = data.dns || {}, ip = data.primary_ip;
    let html = resultsHeader(`Domain intelligence: ${esc(data.query.domain)}`, "");

    html += `<div class="section-label">Registration (WHOIS / RDAP)</div>`;
    if (w.found) {
      html += datalist([
        ["Registrar", esc(w.registrar) || "-"],
        ["Created", esc(w.created) || "-"],
        ["Updated", esc(w.updated) || "-"],
        ["Expires", esc(w.expires) || "-"],
        ["DNSSEC", w.dnssec == null ? "-" : (w.dnssec ? "Enabled" : "Disabled")],
        ["Status", (w.statuses || []).map(esc).join("<br>") || "-"],
        ["Nameservers", (w.nameservers || []).map(esc).join("<br>") || "-"],
      ]);
    } else {
      html += `<div class="hint">${esc(w.message || w.error || "No registration record found.")}</div>`;
    }

    html += mailSecurityBlock(dns.mail_security);
    html += renderDnsBlock(dns);

    if (ip && ip.found) {
      html += `<div class="section-label">Primary server (${esc((data.resolved_ips || [])[0] || "")})</div>`;
      html += ipDetails(ip);
    }

    html += `<div class="section-label">Subdomains</div>
      <div id="subdomains-block">
        <button class="btn btn-ghost btn-sm" data-action="subdomains">Discover subdomains</button>
        <span class="hint" style="margin-left:10px">from public Certificate Transparency logs</span>
      </div>`;

    const primaryIp = (data.resolved_ips || [])[0];
    html += pivotRow("Pivot", [
      primaryIp ? pivotChip("ip", primaryIp, primaryIp) : "",
      ...(w.nameservers || []).map((ns) => { const d = baseDomain(ns); return pivotChip("domain", d, d); }),
    ]);
    resultsEl().innerHTML = html;
  }

  function renderDnsBlock(dns) {
    const recs = dns.records || {};
    const types = Object.keys(recs);
    if (!types.length) return `<div class="section-label">DNS records</div><div class="hint">No DNS records resolved.</div>`;
    let html = `<div class="section-label">DNS records (${dns.summary ? dns.summary.total_records : ""})</div>`;
    html += `<div class="datalist">`;
    types.forEach((t) => {
      html += `<div class="datarow"><div class="k">${esc(t)}</div><div class="v">${recs[t].map((r) => esc(r.value)).join("<br>")}</div></div>`;
    });
    html += `</div>`;
    return html;
  }

  // -- Email spoofing verdict (domain + DNS tools). Graded server-side from
  // SPF and DMARC; missing from results cached before the check existed, in
  // which case nothing renders rather than a false "exposed".
  const MAILSEC = {
    protected: { label: "Protected against spoofing", cls: "clean", color: "var(--ok)",
      text: "DMARC tells receiving mail servers to quarantine or reject mail that fails authentication, so forged mail claiming to be from this domain should not reach an inbox." },
    partial: { label: "Partly protected", cls: "incomplete", color: "var(--warn)",
      text: "Some records are published, but nothing makes receivers act on every forged message, mail pretending to come from this domain can still be delivered." },
    exposed: { label: "Open to spoofing", cls: "", color: "var(--danger)",
      text: "There is no working SPF or DMARC, so receivers have nothing to check forged mail against. Anyone can send email that claims to come from this domain." },
  };
  const SPF_ALL = { "-all": "fail (-all)", "~all": "soft fail (~all)", "?all": "neutral (?all)", "+all": "pass, anyone may send (+all)" };

  function mailSecurityBlock(ms) {
    if (!ms || !MAILSEC[ms.verdict]) return "";
    const v = MAILSEC[ms.verdict], spf = ms.spf || {}, dm = ms.dmarc || {};
    const spfText = !spf.present ? "Not published"
      : !spf.valid ? "Broken, more than one SPF record"
      : `Published · unlisted senders: ${SPF_ALL[spf.all] || (spf.redirect ? "set by the redirected record" : "not marked as failing")}`;
    const dmText = !dm.present ? `Not published (checked ${dm.checked})`
      : !dm.valid ? "Broken, more than one DMARC record"
      : `Policy p=${dm.policy || "not set"}${dm.pct < 100 ? `, applied to ${dm.pct}% of mail` : ""}`
        + `${dm.reports ? " · failure reports collected" : ""}${dm.inherited ? ` · inherited from ${dm.checked.replace(/^_dmarc\./, "")}` : ""}`;
    const rows = [["SPF", esc(spfText)], ["DMARC", esc(dmText)]];
    if (dm.record) rows.push(["DMARC record", esc(dm.record)]);
    rows.push(["DKIM", "Not checkable from outside, its key sits under a selector name only the sender knows"]);
    return `<div class="section-label">Email spoofing protection</div>
      <div class="breach ${v.cls}" role="status">
        <h3>${esc(v.label)}<span class="sev" style="color:${v.color}">${esc(ms.verdict)}</span></h3>
        <p>${esc(v.text)}</p>
        ${(ms.issues || []).length ? `<ul class="tips" style="margin-top:12px">${ms.issues.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}
      </div>
      ${datalist(rows)}
      <p class="hint" style="margin-top:10px"><a href="/guides/spf-dkim-dmarc-explained.html">How SPF, DKIM and DMARC work, and how to fix each gap →</a></p>`;
  }

  function renderDns(data) {
    let html = resultsHeader(`DNS records: ${esc(data.query.domain)}`, "");
    html += mailSecurityBlock(data.mail_security);
    html += renderDnsBlock(data);
    html += dnsPivotRow(data.records || {});
    resultsEl().innerHTML = html;
  }

  // -- IP results
  function ipDetails(data) {
    const g = data.geo || {}, n = data.network || {}, f = data.flags || {};
    return datalist([
      ["Reverse DNS", esc(data.reverse_dns) || "-"],
      ["Location", [g.city, g.region, g.country].filter(Boolean).map(esc).join(", ") || "-"],
      ["Coordinates", g.latitude != null ? `${g.latitude}, ${g.longitude}` : "-"],
      ["Timezone", esc(g.timezone) || "-"],
      ["ISP", esc(n.isp) || "-"],
      ["Organization", esc(n.organization) || "-"],
      ["ASN", esc(n.asn) || "-"],
      ["Flags", [f.hosting && "Hosting", f.proxy && "Proxy/VPN", f.mobile && "Mobile"].filter(Boolean).join(", ") || "None"],
    ]);
  }

  function renderIp(data) {
    let html = resultsHeader(`IP intelligence: ${esc(data.query.ip)}`, "");
    if (!data.found) { html += `<div class="hint">${esc(data.error || "No data available for this IP.")}</div>`; }
    else {
      html += ipDetails(data);
      if (data.reverse_dns) {
        const d = baseDomain(data.reverse_dns);
        html += pivotRow("Pivot", [pivotChip("domain", d, d)]);
      }
    }
    resultsEl().innerHTML = html;
  }

  function datalist(rows) {
    return `<div class="datalist">${rows.map(([k, v]) =>
      `<div class="datarow"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`).join("")}</div>`;
  }

  async function loadWayback(el) {
    const url = el.dataset.wayback;
    if (!url || el.dataset.busy) return;
    el.dataset.busy = "1";
    el.textContent = "checking archive…";
    try {
      const data = await api(CFG.endpoints.wayback, { url });
      const h = data.history || {};
      el.removeAttribute("data-wayback");
      if (h.rate_limited) {
        el.textContent = "archive.org is throttling, try again shortly";
        el.classList.add("wb-warn");
      } else if (h.snapshots) {
        // A range is the useful part: "first seen" dates the account, and a
        // last_seen well in the past on a dead link means it was deleted.
        el.innerHTML = `archived ${esc(h.first_seen)} → ${esc(h.last_seen)}
          (${h.snapshots} snapshot${h.snapshots === 1 ? "" : "s"})
          <a href="${esc(safeUrl(h.archive_url))}" target="_blank" rel="noopener nofollow">view</a>`;
        el.classList.add("wb-hit");
      } else {
        el.textContent = "never archived";
        el.classList.add("wb-miss");
      }
    } catch (err) {
      el.textContent = `archive lookup failed, ${err.message}`;
      el.classList.add("wb-warn");
    } finally {
      delete el.dataset.busy;
    }
  }

  function emptyState(msg) {
    return `<div class="empty"><p class="empty-title">Nothing found</p><p>${esc(msg)}</p></div>`;
  }

  // ---------------------------------------------------------------- pivoting
  // Turn a discovered value (domain, IP, handle) into a one-click
  // "investigate this" chip that switches tools and re-runs the scan.
  const PIVOT_ICON = { domain: "globe", dns: "compass", ip: "pin", email: "mail", username: "user" };

  function cleanHost(v) {
    return String(v || "").trim().replace(/^https?:\/\//i, "").split("/")[0]
      .split("?")[0].replace(/\.$/, "").toLowerCase();
  }
  // Common two-level public suffixes, so we keep 3 labels (e.g. awsdns-21.co.uk)
  // instead of wrongly collapsing to the bare suffix (co.uk).
  const TWO_LEVEL_TLDS = new Set([
    "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk", "net.uk", "ltd.uk", "plc.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "id.au",
    "co.in", "net.in", "org.in", "firm.in", "gen.in", "ind.in",
    "co.nz", "net.nz", "org.nz", "co.za", "org.za",
    "co.jp", "or.jp", "ne.jp", "ac.jp", "co.kr", "or.kr",
    "com.br", "net.br", "org.br", "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.mx", "com.tr", "com.sg", "com.hk", "com.tw", "com.ar", "com.co",
  ]);
  function baseDomain(host) {
    host = cleanHost(host);
    const parts = host.split(".").filter(Boolean);
    if (parts.length <= 2) return host;
    const lastTwo = parts.slice(-2).join(".");
    return TWO_LEVEL_TLDS.has(lastTwo) ? parts.slice(-3).join(".") : lastTwo;
  }
  function domainFromUrl(u) {
    try { return cleanHost(new URL(u).hostname); } catch { return cleanHost(u); }
  }

  function pivotChip(tool, query, label) {
    if (!TOOLS[tool] || !query) return "";
    return `<button type="button" class="pivot" data-pivot data-tool="${esc(tool)}" data-query="${esc(query)}"
      title="Investigate ${esc(query)} with the ${esc(TOOLS[tool].label)} tool">${icon(PIVOT_ICON[tool] || "search", 15)} ${esc(label || query)}</button>`;
  }
  function pivotRow(label, chips) {
    const filled = [...new Set(chips.filter(Boolean))];
    if (!filled.length) return "";
    return `<div class="pivot-row"><span class="pivot-label">${esc(label)}</span>${filled.join("")}</div>`;
  }
  function doPivot(tool, query) {
    // Secret tools are never a valid pivot target, a pivot carries a value
    // from a rendered result into the input, which must never be a password.
    if (!TOOLS[tool] || TOOLS[tool].secret || !query) return;
    switchTool(tool);
    $("#queryInput").value = query;
    if ($("#tool")) window.scrollTo({ top: $("#tool").offsetTop - 70, behavior: "smooth" });
    run();
  }

  function dnsPivotRow(recs) {
    const domains = new Set(), ips = new Set();
    (recs.A || []).forEach((r) => ips.add(r.value));
    (recs.AAAA || []).forEach((r) => ips.add(r.value));
    (recs.MX || []).forEach((r) => { const h = String(r.value).split(/\s+/).pop(); if (h) domains.add(baseDomain(h)); });
    (recs.NS || []).forEach((r) => domains.add(baseDomain(r.value)));
    (recs.CNAME || []).forEach((r) => domains.add(baseDomain(r.value)));
    return pivotRow("Pivot", [
      ...[...ips].slice(0, 3).map((ip) => pivotChip("ip", ip, ip)),
      ...[...domains].filter(Boolean).slice(0, 4).map((d) => pivotChip("domain", d, d)),
    ]);
  }

  function usernameRelatedDomains(data) {
    const out = new Set();
    const rs = data.results || {};
    [].concat(rs.profiles || [], rs.documents || [], rs.mentions || []).forEach((r) => {
      if (r.blog) out.add(baseDomain(r.blog));
      if (r.website) out.add(baseDomain(r.website));
      (String(r.bio || "").match(/https?:\/\/[^\s"'<>)]+/g) || []).forEach((u) => out.add(baseDomain(domainFromUrl(u))));
    });
    return [...out].filter((d) => d && d.includes(".") && d.length < 60).slice(0, 6);
  }

  // ---------------------------------------------------------------- exposure score
  // A shareable 0-100 "digital exposure" score computed from the scan results.
  function computeExposure(tool, data) {
    const s = data.summary || {};
    let score = 0, factors = [];
    if (tool === "username") {
      const profiles = s.profiles || 0, clusters = s.clusters || 0, docs = s.documents || 0;
      score = Math.round(profiles * 5 + clusters * 8 + docs * 3);
      factors = [
        { label: "Public profiles", value: profiles },
        { label: "Linked identities", value: clusters },
        { label: "Documents", value: docs },
      ];
    } else {
      const breached = window.MyReconEmailOutcome(data).found, bc = s.breach_count || 0;
      const linked = data.evidence_report?.profiles?.length ?? (s.linked_accounts || []).length;
      const grav = data.evidence_report?.profiles ? Number(data.evidence_report.profiles.some(p => String(p.platform).toLowerCase() === "gravatar")) : data.gravatar && data.gravatar.exists ? 1 : 0;
      score = Math.round((breached ? 35 : 0) + Math.min(bc, 45) + linked * 6 + grav * 8);
      factors = [
        { label: "Breaches", value: bc },
        { label: "Source-linked profiles", value: linked },
        { label: "Gravatar", value: grav ? "Yes" : "No" },
      ];
    }
    score = Math.max(0, Math.min(100, score));
    let label, color, message;
    if (score <= 30) {
      label = "Low exposure"; color = "var(--ok)";
      message = "A small public footprint. Not much is easy to find, nice work.";
    } else if (score <= 60) {
      label = "Moderate exposure"; color = "var(--warn)";
      message = "A noticeable footprint. Worth reviewing what's public and locking down old accounts.";
    } else {
      label = "High exposure"; color = "var(--danger)";
      message = "A large public footprint. Consider tightening privacy and rotating any breached passwords.";
    }
    return { score, label, color, message, factors };
  }

  function exposureGauge(exp) {
    const R = 52, C = 2 * Math.PI * R;
    const offset = (C * (1 - exp.score / 100)).toFixed(1);
    return `<div class="exposure" style="--gauge-c:${C.toFixed(1)}; --gauge-target:${offset}; --gauge-color:${exp.color}">
      <div class="gauge">
        <svg viewBox="0 0 120 120" width="120" height="120" aria-hidden="true">
          <circle cx="60" cy="60" r="${R}" class="gauge-bg"/>
          <circle cx="60" cy="60" r="${R}" class="gauge-val"/>
        </svg>
        <div class="gauge-center"><span class="gauge-score" data-countup="${exp.score}">0</span><span class="gauge-max">/ 100</span></div>
      </div>
      <div class="exposure-info">
        <div class="exposure-kicker">Digital exposure score</div>
        <div class="exposure-label" style="color:${exp.color}">${esc(exp.label)}</div>
        <p class="exposure-sub">${esc(exp.message)}</p>
        <div class="exposure-factors">${exp.factors.map((f) =>
          `<div class="ef"><span>${esc(f.label)}</span><strong>${esc(String(f.value))}</strong></div>`).join("")}</div>
      </div>
    </div>`;
  }

  function animateCountUps() {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    $$("[data-countup]").forEach((el) => {
      const target = parseFloat(el.dataset.countup) || 0;
      if (reduce) { el.textContent = target; return; }
      const dur = 900, start = performance.now();
      const step = (t) => {
        const p = Math.min(1, (t - start) / dur);
        el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
      // Guarantee the final value even if rAF is throttled (background tab).
      setTimeout(() => { el.textContent = target; }, dur + 120);
    });
  }

  // ---------------------------------------------------------------- password exposure
  // k-anonymity lookup against the Pwned Passwords corpus. The password is
  // hashed locally and only the first 5 hex characters of the SHA-1 leave the
  // browser; the response is padded so its size reveals nothing either. The
  // password reaches neither MyRecon's backend nor Have I Been Pwned.
  async function pwnedCount(password) {
    if (!(window.crypto && crypto.subtle)) {
      throw new Error("This browser can't hash locally, so the check was not run. It needs a secure (https) connection.");
    }
    const digest = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(password));
    const hash = Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0")).join("").toUpperCase();
    const prefix = hash.slice(0, 5), suffix = hash.slice(5);

    const res = await fetch(`https://api.pwnedpasswords.com/range/${prefix}`, {
      headers: { "Add-Padding": "true" },
    });
    if (!res.ok) throw new Error(`Breach corpus is unavailable right now (HTTP ${res.status}).`);

    for (const line of (await res.text()).split("\n")) {
      const [suf, cnt] = line.trim().split(":");
      if (suf === suffix) return parseInt(cnt, 10) || 0;
    }
    return 0; // not in the corpus, padding rows always carry a count of 0
  }

  // Entropy from the character pool actually used. This measures resistance to
  // brute force only; a breached password is weak at any entropy, which is why
  // the corpus result always outranks this number in the verdict.
  function passwordStrength(pw) {
    const pool = (/[a-z]/.test(pw) ? 26 : 0) + (/[A-Z]/.test(pw) ? 26 : 0)
               + (/[0-9]/.test(pw) ? 10 : 0) + (/[^A-Za-z0-9]/.test(pw) ? 33 : 0);
    const bits = pw.length * Math.log2(pool || 1);
    // ~100 billion guesses/sec, a mid-range GPU rig against a fast hash.
    const seconds = Math.pow(2, bits - 1) / 1e11;
    let label = "Very weak";
    if (bits >= 100) label = "Excellent";
    else if (bits >= 75) label = "Strong";
    else if (bits >= 60) label = "Reasonable";
    else if (bits >= 40) label = "Weak";
    return { bits: Math.round(bits), label, crack: humanDuration(seconds), pool };
  }

  function humanDuration(sec) {
    if (sec < 1) return "instantly";
    const units = [["second", 60], ["minute", 60], ["hour", 24], ["day", 365], ["year", Infinity]];
    let v = sec;
    for (const [name, step] of units) {
      if (v < step) {
        const n = Math.round(v);
        return `${n.toLocaleString()} ${name}${n === 1 ? "" : "s"}`;
      }
      v /= step;
    }
    return "centuries";
  }

  function renderPassword(count, pw) {
    const s = passwordStrength(pw);
    const breached = count > 0;
    const color = breached ? "var(--danger)" : "var(--ok)";
    const advice = breached
      ? "Stop using this password everywhere it appears. Attackers load exactly these lists into credential-stuffing tools, so its strength on paper no longer matters."
      : "This password isn't in the corpus. That means it hasn't turned up in a known dump, it doesn't by itself mean the password is strong.";

    resultsEl().innerHTML = `
      <div class="results-bar"><h2>Password exposure</h2>
        <span class="hint">checked privately in your browser</span></div>

      <div class="breach ${breached ? "" : "clean"}">
        <h3>${breached ? "Found in breach data" : "Not found in breach data"}
          <span class="sev" style="color:${color}">
            ${breached ? `seen ${count.toLocaleString()} time${count === 1 ? "" : "s"}` : "no match"}</span>
        </h3>
        <p class="exposure-sub" style="margin:10px 0 0">${esc(advice)}</p>
      </div>

      <div class="section-label">Brute-force resistance</div>
      ${datalist([
        ["Strength", `${esc(s.label)}, ${s.bits} bits of entropy`],
        ["Character pool", `${s.pool} possible characters per position`],
        ["Length", `${pw.length} characters`],
        ["Offline crack time", esc(s.crack)],
      ])}
      <p class="hint" style="margin-top:12px">
        Estimated against roughly 100 billion guesses per second, a mid-range GPU rig
        attacking a fast hash. A site using a slow hash such as bcrypt would take far longer.
      </p>

      <div class="section-label">What to do</div>
      <ul class="tips">
        <li>Use a unique password for every account, reuse is what turns one breach into many.</li>
        <li>Let a password manager generate and store them; length beats complexity.</li>
        <li>Turn on two-factor authentication so a leaked password isn't enough on its own.</li>
        <li><a href="/guides/strong-passwords-guide.html">Read the full guide to strong passwords →</a></li>
      </ul>`;
  }

  const RENDERERS = { username: renderUsername, email: renderEmail, domain: renderDomain, dns: renderDns, ip: renderIp };

  // ---------------------------------------------------------------- run
  async function run() {
    if (activeTool !== "email") await window.MyReconAccount?.ready;
    const tool = TOOLS[activeTool];
    const input = $("#queryInput");
    // Never trim a secret, leading and trailing spaces are part of a password.
    const value = tool.secret ? input.value : input.value.trim();
    if (!value) { input.focus(); toast("Enter something to investigate.", "err"); return; }
    if (tool.route) {
      try { sessionStorage.setItem("myrecon.deep-search.launch", JSON.stringify({ query: value })); } catch {}
      location.assign(tool.route);
      return;
    }
    enterToolMode();

    // Local-only tools resolve in the browser. They deliberately clear
    // lastResult rather than set it, so every result action (save, copy link,
    // export, print) stays inert and cannot reach the value typed above.
    if (tool.local) {
      lastResult = null;
      lastExposure = null;
      $("#runBtn").disabled = true;
      resultsEl().innerHTML = `
        <div class="loading" role="status" aria-live="polite">
          <div class="spinner"></div>
          <h3>Checking privately…</h3>
          <p>Hashing locally and comparing against the breach corpus.</p>
          <div class="progress"><i></i></div>
        </div>`;
      try {
        renderPassword(await pwnedCount(value), value);
      } catch (e) {
        setError(e.message);
      } finally {
        $("#runBtn").disabled = false;
      }
      return;
    }

    const body = { [tool.field]: value };
    if (activeTool === "email") body.check_linked_accounts = !!$("#linkedAccountsToggle")?.checked;
    if (tool.deep) {
      const scope = currentScope();
      body.deep = scope !== "quick";
      body.scope = scope === "full" || scope === "extended" ? scope : "standard";
    }

    $("#runBtn").disabled = true;
    lastResult = null;
    guestSnapshot = null;
    try { sessionStorage.removeItem(GUEST_REPORT_KEY); } catch {}
    try {
      if (activeTool === "username") {
        if (body.scope === "full" || body.scope === "extended") {
          const account = window.MyReconAccount;
          if (account) {
            await account.ready;
            if (account.load) await account.load();
          }
          if (!signedIn()) throw new GateError("Sign in before running this scan.", "sign_in_required", null, body.scope);
        }
        await runUsernameStream(value, body);
      } else {
        setLoading(activeTool);
        const data = await api(tool.endpoint, body);
        lastResult = { tool: activeTool, query: value, data };
        rememberGuestReport(activeTool, value, data);
        renderSafely(RENDERERS[activeTool] || renderIp, data);
        pushHistory(activeTool, value);
        bindActions();
      }
    } catch (e) {
      if (e instanceof GateError) setGate(e); else setError(e.message);
    } finally {
      activeScanUid = null;
      $("#runBtn").disabled = false;
      refreshScopeNote(activeTool !== "email");
    }
  }

  // ---- Results view (cards / account map) -----------------------------
  // Remembered per browser; a convenience only, so storage failures fall back
  // to cards.
  function resultsView() {
    try { return localStorage.getItem("myrecon.resultsView") === "map" ? "map" : "cards"; }
    catch { return "cards"; }
  }

  function setResultsView(view) {
    try { localStorage.setItem("myrecon.resultsView", view); } catch { /* ignore */ }
    $$("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
    $$("[data-view-pane]").forEach((p) => { p.hidden = p.dataset.viewPane !== view; });
  }

  // Once a lookup runs, the homepage becomes the tool: the marketing sections
  // below and the hero illustration are hidden by CSS until the visitor goes
  // back to the overview.
  function enterToolMode() {
    if (document.body.classList.contains("tool-mode")) return;
    document.body.classList.add("tool-mode");
  }

  // ---- Scan size and account state ---------------------------------
  // Platform counts are shown rounded (500+, 3,000+) on purpose.
  const FULL_LABEL = "500+";
  const EXTENDED_LABEL = "3,000+";

  function currentScope() {
    const picked = document.querySelector('input[name="scope"]:checked');
    return picked ? picked.value : "standard";
  }

  function signedIn() {
    const st = window.MyReconAccount && window.MyReconAccount.state();
    return !!(st && st.user);
  }

  // One line under the picker that says what the chosen size will cost.
  async function refreshScopeNote(reload) {
    const note = $("#scopeNote");
    if (!note) return;
    const A = window.MyReconAccount;
    const st = A ? A.state() : null;
    if (reload && st && st.user) await A.refreshAccount();
    const acct = st && st.user ? A.state().account : null;
    const scope = currentScope();
    if (scope !== "full" && scope !== "extended" && (!st || !st.user)) {
      note.textContent = "Guest login: Quick scans only, across 100 platforms. First 2 cards visible; the rest are blurred. No sign-up required. 5 free scans a day.";
      return;
    }
    if (scope === "extended" && (!st || !st.user)) {
      note.textContent = `Checks ${EXTENDED_LABEL} platforms in about 5 minutes. Sign in and get 10 scans for ₹99, with no expiry.`;
      return;
    }
    if (!st || !st.user) {
      note.textContent = "Standard scans require sign-in. Sign in with Google for 5 free scans a day across 500+ platforms with complete results.";
      return;
    }
    if (scope === "extended") {
      const lead = `${EXTENDED_LABEL} platforms, about 5 minutes. `;
      note.textContent = lead + (acct && acct.extended_scans_left > 0
        ? `${acct.extended_scans_left} Extended scans left. `
          + (acct.extended_legacy_scans_left > 0
            ? `${acct.extended_legacy_scans_left} from a previous pass expire ${new Date(acct.extended_legacy_until).toLocaleDateString()}; pack credits never expire.`
            : "Pack credits never expire.")
        : "Get 10 scans for ₹99, with no expiry.");
      return;
    }
    const label = scope === "full" ? "Standard 500+ platform scans" : "Quick 100-platform scans";
    note.textContent = acct && acct.standard_scans_unlimited
      ? `${label}: unlimited with your paid plan. Extended credits are separate.`
      : `${label}: ${acct ? acct.standard_scans_left : 5} of 5 free scans left today, shared across quick and standard scans. Resets at midnight UTC. The ₹99 plan unlocks unlimited standard scans.`;
  }

  // ---- Username: live streaming scan with progress -----------------
  // Platforms already drawn as live cards during this sweep.
  let liveSeen = new Set();
  let liveLocked = 0;

  function lockedProfileCard(live = false) {
    return `<div class="card card-locked" aria-label="Locked result card">
      <div class="locked-card-shape" aria-hidden="true"><div class="card-head"><div class="avatar"></div><div class="locked-lines"><i></i><i></i></div></div><div class="locked-lines"><i></i><i></i><i></i></div></div>
      <div class="locked-card-overlay">${icon("lock", 20)}<strong>Result locked</strong>${live
        ? `<span class="hint">Sign in for Standard</span>`
        : `<button type="button" class="btn btn-ghost btn-sm" data-gate="signin-full">Sign in for Standard</button>`}</div>
    </div>`;
  }

  function updateLiveTally() {
    const visible = signedIn() ? liveSeen.size : Math.min(2, liveSeen.size);
    const total = visible + liveLocked;
    const count = $("#liveCount"), tally = $("#scanTally");
    if (count) count.textContent = String(total);
    if (tally) tally.textContent = `${total} found${liveLocked ? ` · ${liveLocked} locked` : ""}`;
  }

  function addLockedLiveCard(count) {
    const grid = $("#liveGrid"), wrap = $("#liveFound");
    if (!grid || !wrap || !Number.isInteger(count) || count <= liveLocked) return;
    wrap.hidden = false;
    while (liveLocked < count) {
      grid.insertAdjacentHTML("beforeend", lockedProfileCard(true));
      liveLocked++;
    }
    updateLiveTally();
  }

  function setScanning(value, body) {
    liveSeen = new Set();
    liveLocked = 0;
    const extended = body && body.scope === "extended";
    const full = extended || (body && body.scope === "full");
    const size = extended ? EXTENDED_LABEL : (full ? FULL_LABEL : "100");
    const label = extended ? "EXTENDED" : full ? "STANDARD" : "QUICK";
    resultsEl().innerHTML = `
      <div class="loading scan retro" role="status" aria-live="polite">
        <div class="retro-title"><span>MYRECON.EXE · ${size} platforms</span><span aria-hidden="true">_ □ ×</span></div>
        <div class="retro-screen">
          <div class="retro-line">C:\\MYRECON&gt; ${label} ${esc(String(value || "").slice(0, 60))}</div>
          <div class="retro-log" id="scanLog" role="log" aria-live="off"></div>
          <div class="retro-line"><span id="scanPhase" class="retro-caret">Starting scan…</span></div>
          <div class="progress determinate"><i id="scanBar" style="width:0%"></i></div>
          <div class="retro-status"><span id="scanTally">0 found</span><span id="scanPct">0%</span></div>
          <div class="retro-line hint" id="scanDetail">Cards appear as each platform answers.</div>
        </div>
      </div>
      <div class="live-found" id="liveFound" hidden>
        <div class="section-label">Found so far: <span id="liveCount">0</span></div>
        <div class="card-grid" id="liveGrid"></div>
      </div>`;
  }

  // A hit from the stream, drawn the moment its platform answers. These are
  // a preview: the "complete" event re-renders the whole result, enriched,
  // and replaces them, so nothing here is saved, exported or shared.
  function addLiveCard(r) {
    if (!r || !r.platform || liveSeen.has(r.platform)) return;
    liveSeen.add(r.platform);
    const wrap = $("#liveFound"), grid = $("#liveGrid");
    if (!wrap || !grid) return;
    wrap.hidden = false;
    if (!signedIn() && liveSeen.size > 2) {
      liveLocked++;
      grid.insertAdjacentHTML("beforeend", lockedProfileCard(true));
    } else grid.insertAdjacentHTML("beforeend", profileCard(r, true));
    updateLiveTally();
  }

  function updateScanUI(ev) {
    const pct = Math.max(0, Math.min(100, Math.round(ev.percent || 0)));
    const bar = $("#scanBar"); if (bar) bar.style.width = pct + "%";
    const p = $("#scanPct"); if (p) p.textContent = pct + "%";
    const phase = $("#scanPhase"); if (phase && ev.phase) phase.textContent = ev.phase + "…";
    const detail = $("#scanDetail"); if (detail && ev.detail) detail.textContent = ev.detail;
    const log = $("#scanLog");
    if (log && ev.detail) {
      const row = document.createElement("div");
      row.textContent = ev.detail;
      if (/\bfound\b/i.test(ev.detail)) row.className = "hit";
      log.appendChild(row);
      while (log.childElementCount > 8) log.firstElementChild.remove();
      log.scrollTop = log.scrollHeight;
    }
  }

  async function runUsernameStream(value, body) {
    body = { ...body, request_id: body.request_id || crypto.randomUUID() };
    let jobId = null;
    const controller = new AbortController();
    const wait = { full: 720000, extended: 2400000 };
    const timer = setTimeout(() => controller.abort(), wait[body.scope] || 240000);
    try {
      try {
        await consumeUsernameStream(value, body, controller.signal, null, id => { jobId = id; });
      } catch (error) {
        // Only a durable-job acknowledgement permits a safe reconnect.
        // GET resumes the same job and never admits or charges a new scan.
        if (!jobId || error.name === "AbortError" || error instanceof GateError) throw error;
        await consumeUsernameStream(value, body, controller.signal, jobId);
      }
    }
    catch (error) {
      if (error.name === "AbortError") throw new Error("The scan reached its time limit. Try again later.");
      throw error;
    } finally { clearTimeout(timer); }
  }

  async function consumeUsernameStream(value, body, signal, resumeJob = null, onJob = () => {}) {
    setScanning(value, body);
    let res;
    const requestUid = window.MyReconAccount?.state()?.user?.uid || null;
    activeScanUid = requestUid;
    try {
      const endpoint = resumeJob ? "/api/username/jobs/" + encodeURIComponent(resumeJob) + "/stream" : CFG.endpoints.usernameStream;
      const headers = requestUid ? await authHeaders() : {};
      if (requestUid && window.MyReconAccount?.state()?.user?.uid !== requestUid) throw new Error("Your account changed. Start this lookup again.");
      res = await fetch(CFG.apiBase + endpoint, {
        method: resumeJob ? "GET" : "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: resumeJob ? undefined : JSON.stringify(body),
        signal,
      });
    } catch (error) {
      // The server may already have admitted/charged this request. Retrying
      // automatically on a transport failure can spend a second allowance.
      if (error.name === "AbortError") throw error;
      throw new Error("Could not reach the MyRecon API. Check your connection or try later.");
    }
    if (res.status === 404 && !resumeJob) return runUsernameFallback(value, body); // older backend
    if (!res.ok || !res.body) {
      let data = {};
      try { data = await res.json(); } catch {}
      throw errorFrom(res, data);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;
    let savedId = null;

    const handleLine = (line) => {
      if (requestUid && window.MyReconAccount?.state()?.user?.uid !== requestUid) throw new Error("Your account changed before the scan finished. Start this lookup again.");
      line = line.trim();
      if (!line) return;
      let ev; try { ev = JSON.parse(line); } catch { return; }
      if (ev.type === "job" && /^[a-f0-9]{32}$/.test(ev.job_id || "")) onJob(ev.job_id);
      else if (ev.type === "progress") updateScanUI(ev);
      else if (ev.type === "found") addLiveCard(ev.result);
      else if (ev.type === "found_locked") addLockedLiveCard(ev.count);
      else if (ev.type === "complete") { finalData = ev.data; savedId = ev.history_id; }
      else if (ev.type === "error") throw new Error(ev.error || "Scan failed");
    };

    try { while (true) {
      const { value: chunk, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(chunk, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        handleLine(buffer.slice(0, nl));
        buffer = buffer.slice(nl + 1);
      }
    }
    if (buffer) handleLine(buffer);
    } finally { await reader.cancel().catch(() => {}); }

    if (!finalData) throw new Error("The scan did not complete. Please try again.");
    if (!finalData.guest_access && (window.MyReconAccount?.state()?.user?.uid || null) !== requestUid) throw new Error("Your account changed before the report could be displayed.");
    lastResult = { tool: "username", query: value, data: finalData };
    rememberGuestReport("username", value, finalData);
    renderSafely(renderUsername, finalData);
    if (savedId) toast("Saved to your scans.");
    pushHistory("username", value);
    bindActions();
  }

  // A scan from the account's history, shown as it was. Nothing is rescanned
  // and nothing is charged; the result comes back from the user's own store.
  async function openSavedScan(id) {
    setLoading("username");
    try {
      if (window.MyReconAccount) await window.MyReconAccount.ready;
      if (!signedIn()) {
        throw new GateError("Sign in to open your saved scans.", "sign_in_required");
      }
      const requestUid = window.MyReconAccount.state().user.uid;
      const headers = await authHeaders();
      if (window.MyReconAccount.state().user?.uid !== requestUid) throw new Error("Your account changed. Open this scan again.");
      const res = await fetch(CFG.apiBase + "/api/history/" + encodeURIComponent(id),
        { headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") throw errorFrom(res, data);
      if (window.MyReconAccount.state().user?.uid !== requestUid) throw new Error("Your account changed before the saved scan arrived.");
      const scan = data.scan;
      const q = scan.query || {};
      $("#queryInput").value = q.username || "";
      const radio = document.querySelector(`input[name="scope"][value="${q.scope === "full" || q.scope === "extended" ? q.scope : "standard"}"]`);
      if (radio) radio.checked = true;
      lastResult = { tool: "username", query: q.username || "", data: scan };
      resultUid = window.MyReconAccount.state().user.uid;
      enterToolMode();
      renderSafely(renderUsername, scan);
      bindActions();
      refreshScopeNote(false);
      toast("Opened a saved scan. Nothing was rescanned.");
    } catch (e) {
      if (e instanceof GateError) setGate(e); else setError(e.message);
    }
  }

  async function runUsernameFallback(value, body) {
    setLoading("username");
    const data = await api(CFG.endpoints.username, body);
    lastResult = { tool: "username", query: value, data };
    rememberGuestReport("username", value, data);
    renderSafely(renderUsername, data);
    pushHistory("username", value);
    bindActions();
  }

  // ---------------------------------------------------------------- result actions
  function bindActions() {
    $$("[data-export]").forEach((btn) => btn.addEventListener("click", () => exportResult(btn.dataset.export)));
    $$("[data-action]").forEach((btn) => btn.addEventListener("click", () => {
      const a = btn.dataset.action;
      if (a === "save") saveCurrent(btn);
      else if (a === "share-native") shareNative();
      else if (a === "share") shareLink();
      else if (a === "copy") copySummary();
      else if (a === "print") printReport();
      else if (a === "subdomains") discoverSubdomains(btn);
      else if (a === "email-timeline-filter") {
        const section = btn.closest('.email-evidence-timeline');
        const kind = btn.dataset.kind;
        section.querySelectorAll('[data-kind]').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
        const rows = Array.from(section.querySelectorAll(':scope > .email-event-list > li'));
        rows.forEach((row) => { row.hidden = kind !== 'all' && row.dataset.emailEvent !== kind; });
        section.querySelector('.email-timeline-empty').hidden = rows.some((row) => !row.hidden);
      }
      // Opens the password tool empty. Nothing from the email result is
      // carried across, the only value that tool may ever hold is typed.
      else if (a === "open-password") {
        switchTool("password");
        window.scrollTo({ top: $("#tool").offsetTop - 70, behavior: "smooth" });
        $("#queryInput").focus({ preventScroll: true });
      }
      else if (a === "retry-email" && lastResult?.tool === "email") {
        const query = lastResult.query;
        switchTool("email");
        $("#queryInput").value = query;
        run();
      }
    }));
  }

  function copyText(text, okMsg) {
    const done = () => toast(okMsg || "Copied.");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
    } else { fallbackCopy(text, done); }
  }
  function fallbackCopy(text, done) {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); done(); } catch { toast("Copy failed.", "err"); }
    ta.remove();
  }

  function shareUrl() {
    return `${location.origin}/#tool=${encodeURIComponent(lastResult.tool)}&q=${encodeURIComponent(lastResult.query)}`;
  }

  function shareLink() {
    if (!lastResult || lockedResults()) return;
    copyText(shareUrl(), "Shareable link copied to clipboard.");
  }

  // Native share sheet (mobile + supported desktop browsers). Falls back to
  // copying the link when the Web Share API isn't available.
  async function shareNative() {
    if (!lastResult || lockedResults()) return;
    // lastExposure is only computed for username/email and is not cleared by the
    // other renderers, so gate on the tool or a stale score leaks into the text.
    const scored = lastResult.tool === "username" || lastResult.tool === "email";
    const scoreBit = scored && lastExposure ? `, exposure score ${lastExposure.score}/100 (${lastExposure.label})`
      : lastResult.tool === "email" && !lastResult.data.guest_access ? `, ${window.MyReconEmailOutcome(lastResult.data).label}` : "";
    const preview = lastResult.tool === "username" ? previewMeta(lastResult.data) : null;
    const previewBit = preview
      ? `, guest preview: ${preview.visible} of ${preview.checked} platform verdicts visible` : "";
    const payload = {
      title: "MyRecon, OSINT report",
      text: `${TOOLS[lastResult.tool].label} report for ${lastResult.query}${scoreBit}${previewBit}`,
      url: shareUrl(),
    };
    if (navigator.share) {
      try { await navigator.share(payload); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
    copyText(`${payload.text}\n${payload.url}`, "Copied, paste it anywhere to share.");
  }

  function copySummary() {
    if (!lastResult || lockedResults()) return;
    copyText(buildTextSummary(lastResult), "Summary copied to clipboard.");
  }

  function printReport() {
    if (!lastResult || lockedResults()) return;
    const meta = $("#printMeta");
    const preview = lastResult.tool === "username" ? previewMeta(lastResult.data) : null;
    if (meta) meta.textContent = `${TOOLS[lastResult.tool].label} report · Target: ${lastResult.query} · ${new Date().toLocaleString()}`
      + (preview ? ` · Guest preview: ${preview.visible} of ${preview.checked} platforms shown` : "");
    const prev = document.title;
    document.title = `MyRecon ${TOOLS[lastResult.tool].label} report: ${lastResult.query}`;
    const folded = $$("#results details:not([open])");
    folded.forEach(node => { node.open = true; });
    window.addEventListener("afterprint", () => folded.forEach(node => { node.open = false; }), { once: true });
    window.print();
    setTimeout(() => { document.title = prev; }, 800);
  }

  function buildTextSummary(res) {
    const d = res.data;
    const L = [`MyRecon, ${TOOLS[res.tool].label} report`, `Target: ${res.query}`, `Generated: ${new Date().toLocaleString()}`, ""];
    if (d.guest_access) {
      for (const card of d.cards || []) if (!card.locked) L.push(card.title || "Result", JSON.stringify(card.data), "");
      return L.join("\n");
    }
    if (d.partial) {
      L.push("Search partially completed. Unavailable checks do not mean no match.");
      [...new Set((d.errors || []).map((error) => error.message || `${error.source || "A source"} unavailable`))]
        .forEach((message) => L.push(`- ${message}`));
      L.push("");
    }
    const exposure = (res.tool === "username" && !previewMeta(d) && !d.guest_preview && !d.partial) || (res.tool === "email" && !d.partial && !window.MyReconEmailOutcome(d).partial)
      ? computeExposure(res.tool, d) : null;
    if (exposure) {
      L.push(`Digital exposure score: ${exposure.score}/100 (${exposure.label})`, "");
    }
    if (res.tool === "username") {
      const preview = previewMeta(d);
      if (preview) L.push(`Guest preview: ${preview.visible} of ${preview.checked} platforms shown; ${preview.hidden} platform verdicts require sign-in.`, "");
      if (d.guest_preview) L.push(`Guest preview: ${d.guest_preview.visible_cards} card details visible; ${d.guest_preview.hidden_cards} cards locked. Sign in to run Standard for complete results.`, "");
      const all = [].concat(d.results?.profiles || [], d.results?.documents || [], d.results?.mentions || []);
      L.push(`${all.length} ${preview ? "visible results" : "results"} found:`);
      all.forEach((r) => {
        L.push(`- ${r.platform || hostOf(r.url)}, ${r.url}${r.confidence ? ` [${r.confidence}]` : ""}`);
        if (r.display_name) L.push(`  Name: ${r.display_name}`);
        if (r.bio) L.push(`  Bio: ${r.bio}`);
        if (r.profile_pic_url) L.push(`  Avatar: ${r.profile_pic_url}`);
        if (r.public_links?.length) L.push(`  Public links: ${r.public_links.join(", ")}`);
        Object.entries(r.statistics || {}).forEach(([key, value]) => L.push(`  ${key.replace(/_/g, " ")}: ${value}`));
        if (r.metadata_source) L.push(`  Source: ${r.metadata_source.platform}; ${r.metadata_source.url}; ${r.metadata_source.basis}`);
      });
    } else if (res.tool === "email") {
      const a = d.analysis || {}, s = d.summary || {};
      L.push(`Provider: ${a.provider || "-"} (${a.provider_type || "-"})`);
      L.push(`Deliverable: ${a.deliverable == null ? "unknown" : a.deliverable ? "yes" : "no"} · Disposable: ${a.disposable == null ? "unknown" : a.disposable ? "yes" : "no"}`);
      const outcome = window.MyReconEmailOutcome(d);
      const platforms = window.MyReconEmailOutcome.platforms?.(d);
      if (platforms) {
        L.push(`Linked platforms: ${platforms.linked}; historical evidence: ${platforms.historical}.`, platforms.detail);
        L.push(`Platform coverage: ${platforms.coverage.completed} of ${platforms.coverage.attempted} completed; ${platforms.coverage.unavailable} inconclusive.`);
        L.push(`Source-associated platforms: ${platforms.names.join(", ") || "none returned"}`);
      }
      L.push(`Breaches: ${outcome.label}${outcome.found && s.breach_count > 0 ? ` (${s.breach_count})` : ""}`);
      L.push(`Coverage: ${outcome.coverage}${outcome.partial ? " (incomplete)" : ""}`, outcome.detail);
      outcome.sources.forEach((source) => L.push(`- ${source.name}: ${source.status}${source.error ? ", " + source.error : ""}`));
      if (outcome.partial) L.push("Exposure score: unavailable because coverage is incomplete.");
      L.push("Named breaches:");
      emailBreachRows(d).forEach((b) => L.push(`- ${b.name}: ${b.date || "date not provided"}; data exposed: ${(b.exposed || []).join(", ") || "not provided"}; source: ${b.sources.join(", ")}`));
      if (d.account_checks) {
        L.push(`Public account checks: ${d.account_checks.enabled ? "enabled" : "off"}`);
        (d.account_checks.sources || []).forEach((source) => L.push(`- ${source.name}: ${source.status}`));
      }
      if (d.registration_checks && d.registration_checks.status !== "skipped") {
        L.push(`Registration checks: ${d.registration_checks.checked || 0} answered of ${d.registration_checks.attempted || 0} eligible`);
        (d.registration_checks.services || []).forEach((r) => L.push(`- ${r.service} (${r.engine || "Holehe"}): ${r.status}; ${r.reason}`));
      }
      const svc = (d.linked_services && d.linked_services.services) || [];
      const evidence = d.evidence_report;
      if (evidence) {
        if (evidence.generated_at) L.push(`Report collected: ${evidence.generated_at}`);
        if (evidence.confidence_note) L.push(evidence.confidence_note);
        if (evidence.freshness_note) L.push(evidence.freshness_note);
        L.push("Profile summary:");
        Object.entries(evidence.identity || {}).forEach(([field, values]) => values.forEach((v) => L.push(`- ${field}: ${v.value}; source: ${v.source}; basis: ${v.basis}`)));
        L.push(evidence.identity_note, "Evidence timeline:");
        L.push(evidence.counts_note || "Counts describe returned evidence; categories can overlap.");
        [...(evidence.timeline || []), ...(evidence.undated_events || [])].forEach((event) => L.push(`- ${event.date_label}: ${event.title}; source: ${event.sources.join(', ')}; ${event.detail}${event.url ? `; ${event.url}` : ''}`));
        L.push(evidence.date_note);
        if (evidence.locations?.length) {
          L.push("Locations:");
          evidence.locations.forEach(v => L.push(`- ${v.value}; source: ${v.source}; basis: ${v.basis}${v.date_label ? `; ${v.date_label}` : ''}${v.url ? `; ${v.url}` : ''}`));
        }
        (evidence.profiles || []).forEach(p => {
          L.push(`${p.platform} profile: ${p.display_name || p.username || ''}; source: ${p.source}`);
          if (p.confidence?.scale === 4) L.push(`- Evidence strength: ${p.confidence.score}/4; ${p.confidence.label}; ${p.confidence.reason}`);
          if (p.freshness) L.push(`- Recency: ${p.freshness.label}; ${p.freshness.reason}`);
          Object.entries(p.field_conflicts || {}).forEach(([field, values]) => L.push(`- Source values differ (${field}): ${values.map(v => `${typeof v.value === 'object' ? JSON.stringify(v.value) : v.value}; source: ${v.source || 'not specified'}`).join(' | ')}`));
          Object.entries(p.fields || {}).forEach(([k, v]) => L.push(`- ${k}: ${v}`));
          Object.entries(p.lists || {}).forEach(([k, v]) => L.push(`- ${k}: ${v.join(', ')}`));
          if (String(p.platform).toLowerCase() === "google") {
            const reviews = window.MyReconEmailOutcome.reviews?.(p, d);
            if (reviews) L.push(`- Google reviews: ${reviews.label}; ${reviews.returned} records returned; source: ${reviews.source || "not specified"}.`, reviews.detail);
          }
          (p.reviews || []).forEach(r => L.push(`- Review: ${r.name || ''}; ${r.address || ''}; ${r.date_label || r.date || 'date not provided'}; ${r.rating ?? 'rating not provided'}; ${r.text || ''}${r.owner_reply ? `; Owner reply: ${r.owner_reply}` : ''}${r.source_url ? `; ${r.source_url}` : ''}`));
          (p.positions || []).forEach(r => L.push(`- Position: ${r.title || ''}; ${r.company || ''}; ${r.start || ''} to ${r.current ? 'Present' : r.end || ''}`));
          (p.education || []).forEach(r => L.push(`- Education: ${r.school || ''}; ${r.start || ''} to ${r.end || ''}`));
        });
      }
      if (svc.length) {
        L.push(`Service evidence entries (${svc.length}):`);
        svc.forEach((r) => L.push(`- ${r.service}: ${r.evidence}${r.date ? ` (${r.date})` : ""}`));
      } else if ((s.linked_accounts || []).length) L.push(`Linked accounts: ${s.linked_accounts.join(", ")}`);
    } else if (res.tool === "domain") {
      const w = d.whois || {};
      L.push(`Registrar: ${w.registrar || "-"}`);
      L.push(`Created: ${w.created || "-"} · Expires: ${w.expires || "-"}`);
      L.push(`Nameservers: ${(w.nameservers || []).join(", ") || "-"}`);
      L.push(`Resolved IP: ${(d.resolved_ips || [])[0] || "-"}`);
      const ms = (d.dns || {}).mail_security;
      if (ms && MAILSEC[ms.verdict]) L.push(`Email spoofing protection: ${MAILSEC[ms.verdict].label}`);
    } else if (res.tool === "ip") {
      const g = d.geo || {}, n = d.network || {};
      L.push(`Location: ${[g.city, g.region, g.country].filter(Boolean).join(", ") || "-"}`);
      L.push(`ISP: ${n.isp || "-"} · ASN: ${n.asn || "-"}`);
      L.push(`Reverse DNS: ${d.reverse_dns || "-"}`);
    } else if (res.tool === "dns") {
      if (d.mail_security && MAILSEC[d.mail_security.verdict]) L.push(`Email spoofing protection: ${MAILSEC[d.mail_security.verdict].label}`, "");
      Object.entries(d.records || {}).forEach(([t, recs]) => L.push(`${t}: ${recs.map((r) => r.value).join(", ")}`));
    }
    return L.join("\n") + `\n\nvia https://www.myrecon.xyz`;
  }

  async function discoverSubdomains(btn) {
    const domain = lastResult && lastResult.query;
    if (!domain) return;
    btn.disabled = true; btn.textContent = "Discovering…";
    const wrap = $("#subdomains-block");
    try {
      const data = await api(CFG.endpoints.subdomains, { domain });
      const subs = data.subdomains || [];
      if (!subs.length) { wrap.innerHTML = `<div class="hint">No subdomains found in Certificate Transparency logs.</div>`; return; }
      wrap.innerHTML =
        `<div class="hint" style="margin-bottom:8px">${data.total} found${data.truncated ? `, showing ${subs.length}` : ""} · ${esc(data.source || "CT logs")}</div>` +
        `<div class="chips">${subs.map((s) => `<a class="pill" href="https://${esc(s)}" target="_blank" rel="noopener nofollow">${esc(s)}</a>`).join("")}</div>` +
        pivotRow("Pivot", subs.slice(0, 6).map((s) => pivotChip("domain", s, s)));
    } catch (e) {
      wrap.innerHTML = `<div class="hint">Subdomain discovery failed: ${esc(e.message)}</div>`;
    }
  }

  // ---- Saved investigations (localStorage) --------------------------
  const SKEY = "myrecon-saved";
  function getSaved() {
    try {
      const saved = JSON.parse(storageGet(SKEY));
      return Array.isArray(saved) ? saved : [];
    } catch { return []; }
  }
  function saveCurrent(btn) {
    if (!lastResult || lockedResults()) return;
    let s = getSaved().filter((x) => !(x.tool === lastResult.tool && x.query === lastResult.query));
    s.unshift({ tool: lastResult.tool, query: lastResult.query, at: Date.now(), note: quickStat(lastResult) });
    if (!storageSet(SKEY, JSON.stringify(s.slice(0, 50)))) {
      toast("Browser storage is unavailable, so this result could not be saved.", "err");
      return;
    }
    renderSaved();
    if (btn) { btn.textContent = "Saved"; btn.disabled = true; }
    toast("Saved to your investigations.");
  }
  function quickStat(res) {
    const d = res.data;
    if (d.guest_access) return `${d.guest_access.total_cards} result cards`;
    if (res.tool === "username") return `${(d.summary || {}).profiles || 0} profiles`;
    if (res.tool === "email") {
      const outcome = window.MyReconEmailOutcome(d);
      return `${outcome.label}${outcome.partial && outcome.found ? " · incomplete coverage" : ""}`;
    }
    if (res.tool === "domain") return (d.whois || {}).registrar || "domain";
    if (res.tool === "ip") return [(d.geo || {}).city, (d.geo || {}).country].filter(Boolean).join(", ") || "IP";
    if (res.tool === "dns") return `${(d.summary || {}).total_records || 0} records`;
    return "";
  }
  function renderSaved() {
    const wrap = $("#saved");
    if (!wrap) return;
    const s = getSaved();
    // Hidden until there is something in it: a first visit would otherwise
    // open on two empty sections between the tool and everything else.
    $("#saved-section")?.toggleAttribute("hidden", !s.length);
    if (!s.length) { wrap.innerHTML = ""; return; }
    wrap.innerHTML = `<div class="history-list">` + s.map((x, i) => `
      <div class="history-item" data-tool="${esc(x.tool)}" data-query="${esc(x.query)}">
        <div class="ico">${icon(TOOLS[x.tool] ? TOOLS[x.tool].icon : "search", 17)}</div>
        <div class="meta"><div class="q">${esc(x.query)}</div>
          <div class="t">${TOOLS[x.tool] ? esc(TOOLS[x.tool].label) : ""}${x.note ? " · " + esc(x.tool === "email" && x.note === "no breaches" ? "Older result · rerun to verify coverage" : x.note) : ""}</div></div>
        <button type="button" class="icon-btn btn-sm" data-del="${i}" aria-label="Remove ${esc(x.query)} from saved" title="Remove ${esc(x.query)} from saved">&times;</button>
      </div>`).join("") + `</div>`;
    $$(".history-item", wrap).forEach((el) => el.addEventListener("click", (e) => {
      if (e.target.closest("[data-del]")) return;
      switchTool(el.dataset.tool); $("#queryInput").value = el.dataset.query; run();
      window.scrollTo({ top: $("#tool").offsetTop - 70, behavior: "smooth" });
    }));
    $$("[data-del]", wrap).forEach((b) => b.addEventListener("click", () => {
      const saved = getSaved();
      const index = Number(b.dataset.del);
      if (!Number.isInteger(index) || index < 0 || index >= saved.length) return;
      saved.splice(index, 1);
      if (!storageSet(SKEY, JSON.stringify(saved))) {
        toast("Browser storage is unavailable, so this item could not be removed.", "err");
        return;
      }
      renderSaved();
    }));
  }

  function download(name, text, type) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportResult(kind) {
    if (!lastResult || lockedResults()) return;
    const base = `myrecon-${lastResult.tool}-${Date.now()}`;
    if (kind === "json") {
      download(base + ".json", JSON.stringify(exportData(lastResult), null, 2), "application/json");
    } else {
      download(base + ".csv", toCSV(lastResult), "text/csv");
    }
    toast(`Exported ${kind.toUpperCase()}.`);
  }

  function exportData(res) {
    if (res.data.guest_access) return { status: res.data.status, query: res.data.query, partial: res.data.partial,
      notices: res.data.notices, cards: (res.data.cards || []).filter(c => !c.locked) };
    if (res.tool !== "email") return res.data;
    const outcome = window.MyReconEmailOutcome(res.data);
    const platforms = window.MyReconEmailOutcome.platforms?.(res.data);
    const reviewCoverage = (res.data.evidence_report?.profiles || []).filter(p => String(p.platform).toLowerCase() === "google")
      .map(p => window.MyReconEmailOutcome.reviews?.(p, res.data)).filter(Boolean);
    return { ...res.data, summary: { ...res.data.summary,
      breached: outcome.found,
      breach_outcome: outcome.state,
      coverage_incomplete: outcome.partial || !!res.data.partial,
      breach_coverage: { completed: outcome.completed, attempted: outcome.attempted, sources: outcome.sources },
      interpretation: outcome.detail,
      ...(platforms ? { linked_platforms_count: platforms.linked, platform_coverage: platforms.coverage,
        platform_coverage_incomplete: platforms.coverage.enabled !== false && (platforms.coverage.status !== "ok" || platforms.coverage.unavailable > 0 || platforms.coverage.unconfigured > 0) } : {}),
      review_coverage: reviewCoverage.map(r => ({ returned: r.returned, source: r.source, state: r.state,
        total_reported: r.totalReported, ratings_reported: r.ratingsReported,
        contributions_reported: r.contributionsReported, partial: r.partial, interpretation: r.detail })),
      review_coverage_incomplete: reviewCoverage.some(r => r.partial),
    } };
  }

  function toCSV(res) {
    const rows = [["field", "value"]];
    const walk = (obj, prefix = "") => {
      if (Array.isArray(obj)) {
        obj.forEach((v, i) => walk(v, `${prefix}[${i}]`));
      } else if (obj && typeof obj === "object") {
        Object.entries(obj).forEach(([k, v]) => walk(v, prefix ? `${prefix}.${k}` : k));
      } else {
        rows.push([prefix, String(obj ?? "")]);
      }
    };
    walk(exportData(res));
    return rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  }

  // ---------------------------------------------------------------- history
  const HKEY = "myrecon-history";
  function getHistory() {
    try {
      const history = JSON.parse(storageGet(HKEY));
      return Array.isArray(history) ? history : [];
    } catch { return []; }
  }
  function pushHistory(tool, query) {
    let h = getHistory().filter((x) => !(x.tool === tool && x.query === query));
    h.unshift({ tool, query, at: Date.now() });
    h = h.slice(0, 20);
    // Search results are still successful if optional local history cannot
    // be written (for example, in a private browser with storage disabled).
    if (!storageSet(HKEY, JSON.stringify(h))) return;
    renderHistory();
  }
  function renderHistory() {
    const wrap = $("#history");
    if (!wrap) return;
    const h = getHistory();
    $("#history-section")?.toggleAttribute("hidden", !h.length);
    if (!h.length) { wrap.innerHTML = ""; return; }
    wrap.innerHTML = `<div class="history-list">` + h.map((x) => `
      <div class="history-item" data-tool="${esc(x.tool)}" data-query="${esc(x.query)}">
        <div class="ico">${icon(TOOLS[x.tool] ? TOOLS[x.tool].icon : "search", 17)}</div>
        <div class="meta"><div class="q">${esc(x.query)}</div>
          <div class="t">${TOOLS[x.tool] ? esc(TOOLS[x.tool].label) : ""} · ${new Date(x.at).toLocaleString()}</div></div>
      </div>`).join("") + `</div>
      <button class="btn btn-ghost btn-sm" id="clearHistory" style="margin-top:12px">Clear history</button>`;
    $$(".history-item", wrap).forEach((el) => el.addEventListener("click", () => {
      switchTool(el.dataset.tool);
      $("#queryInput").value = el.dataset.query;
      run();
      window.scrollTo({ top: $("#tool").offsetTop - 70, behavior: "smooth" });
    }));
    $("#clearHistory")?.addEventListener("click", () => {
      if (!storageRemove(HKEY)) {
        toast("Browser storage is unavailable, so history could not be cleared.", "err");
        return;
      }
      renderHistory();
    });
  }

  // ---------------------------------------------------------------- tabs
  // Reveal only ever applies to the password tool; every other tool renders a
  // plain text input and keeps the button hidden.
  function setReveal(shown) {
    const q = $("#queryInput"), btn = $("#revealBtn");
    if (!q || !btn) return;
    const secret = !!(TOOLS[activeTool] && TOOLS[activeTool].secret);
    if (secret) q.type = shown ? "text" : "password";
    q.closest(".input-wrap")?.classList.toggle("revealing", secret && shown);
    btn.innerHTML = icon(shown ? "eyeOff" : "eye", 17);
    btn.setAttribute("aria-label", shown ? "Hide password" : "Show password");
    btn.setAttribute("title", shown ? "Hide password" : "Show password");
    btn.setAttribute("aria-pressed", String(shown));
  }

  function switchTool(name) {
    if (!TOOLS[name]) return;
    activeTool = name;
    lastResult = null;
    lastExposure = null;
    $$(".tab").forEach((t) => {
      const on = t.dataset.tool === name;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
    });
    $("#toolPanel")?.setAttribute("aria-labelledby", `tab-${name}`);
    const tool = TOOLS[name];
    const q = $("#queryInput");
    q.placeholder = tool.placeholder;
    q.value = "";
    q.type = tool.secret ? "password" : "text";
    q.setAttribute("aria-label", tool.secret ? "Password to check" : "Search target");
    setReveal(false);
    $("#revealBtn").hidden = !tool.secret;
    $("#panelSub").textContent = tool.sub;
    $("#deepWrap").style.display = tool.deep ? "" : "none";
    $("#emailOptions")?.toggleAttribute("hidden", name !== "email");
    const ex = $("#examples");
    if (ex) {
      ex.innerHTML = (tool.examples || []).length
        ? `<span class="ex-label">Try:</span>` + tool.examples.map((e) =>
            `<button type="button" class="ex-chip" data-ex="${esc(e)}">${esc(e)}</button>`).join("")
        : "";
    }
    resultsEl().innerHTML = defaultEmpty();
    updateDetectHint();
  }

  // Most people arrive with a question, not a tool name. Each start opens the
  // tool empty and focuses it; the active tool is left out as already chosen.
  const QUICK_STARTS = [
    ["email", "Has my email been in a breach?", "Check an address against published breach data."],
    ["username", "Where is my username in use?", "Sweep public platforms for a handle."],
    ["password", "Has my password leaked?", "Hashed in your browser, the password is never sent."],
    ["domain", "Can someone spoof my domain's email?", "Registration, DNS, and an SPF / DMARC check."],
  ];

  function defaultEmpty() {
    const starts = QUICK_STARTS.filter(([t]) => t !== activeTool && TOOLS[t]);
    return `<div class="empty">
      <p class="empty-title">Ready when you are</p>
      <p>Enter a target above, or start from a question:</p>
      <div class="quick-links">${starts.map(([t, q, d]) => `
        <button type="button" class="quick-link" data-quick="${t}">${icon(TOOLS[t].icon, 18)}
          <span><strong>${esc(q)}</strong><small>${esc(d)}</small></span><span class="quick-link-arrow" aria-hidden="true">→</span></button>`).join("")}
      </div>
    </div>`;
  }

  // ---------------------------------------------------------------- input detection
  // An email typed into the username box, or an IP into the domain box, gets a
  // one-click move to the tool that fits it. Only unambiguous shapes count,
  // "john.doe" could be a handle or a domain, so the username tool never
  // suggests Domain. The password tool is never read from or suggested: a
  // value typed there must not move anywhere.
  const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
  function detectKind(v) {
    v = String(v || "").trim();
    if (!v || /\s/.test(v)) return null;
    if (/^[^@\s/]+@[^@\s/]+\.[a-z]{2,}$/i.test(v)) return "email";
    if (IPV4.test(v) || (/^[0-9a-f:]+$/i.test(v) && (v.match(/:/g) || []).length >= 2)) return "ip";
    if (/^(https?:\/\/)?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}\/?$/i.test(v)) return "domain";
    return null;
  }
  const SUGGEST = { username: ["email", "ip"], email: ["ip", "domain"], domain: ["email", "ip"], dns: ["email", "ip"], ip: ["email", "domain"] };
  const KIND_LABEL = { email: "an email address", ip: "an IP address", domain: "a domain" };

  function updateDetectHint() {
    const hint = $("#detectHint");
    if (!hint) return;
    const tool = TOOLS[activeTool];
    const kind = tool && !tool.secret ? detectKind($("#queryInput").value) : null;
    const target = kind && (SUGGEST[activeTool] || []).includes(kind) && TOOLS[kind] && !TOOLS[kind].secret ? kind : null;
    hint.hidden = !target;
    hint.innerHTML = target
      ? `${icon(TOOLS[target].icon, 15)}<span>That looks like ${KIND_LABEL[target]}.</span>
         <button type="button" class="linklike" data-switch="${target}">Search it with the ${esc(TOOLS[target].label)} tool instead</button>`
      : "";
  }

  // ---------------------------------------------------------------- init
  function buildTabs() {
    const tabs = $("#toolTabs");
    if (!tabs) return;
    tabs.innerHTML = Object.entries(TOOLS).map(([k, t], i) =>
      `<button type="button" class="tab" role="tab" id="tab-${k}" data-tool="${k}"
        aria-controls="toolPanel" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}">
        <span class="tab-ico">${icon(t.icon, 17)}</span>${esc(t.label)}</button>`
    ).join("");
    const all = $$(".tab", tabs);
    all.forEach((el) => el.addEventListener("click", () => switchTool(el.dataset.tool)));
    tabs.addEventListener("keydown", (e) => {
      const i = all.indexOf(document.activeElement);
      if (i < 0) return;
      const last = all.length - 1;
      let next = null;
      if (e.key === "ArrowRight") next = i === last ? 0 : i + 1;
      else if (e.key === "ArrowLeft") next = i === 0 ? last : i - 1;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = last;
      if (next === null) return;
      e.preventDefault();
      switchTool(all[next].dataset.tool);
      all[next].focus();
    });
  }

  function initHeroRotate() {
    const el = $("#heroWord");
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const words = ["digital footprint", "username", "email address", "domain", "IP address"];
    let i = 0;
    setInterval(() => {
      i = (i + 1) % words.length;
      el.classList.add("swap");
      setTimeout(() => { el.textContent = words[i]; el.classList.remove("swap"); }, 250);
    }, 2600);
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initNav();
    initHeroRotate();
    buildTabs();
    if ($("#tool")) {
      // Wake the API as soon as the tool is on screen. Render's free tier sleeps
      // after 15 idle minutes and takes ~50 s to boot, so starting that boot
      // while the visitor is still typing hides most or all of it. /api/health
      // is exempt from rate limiting and does no work.
      fetch(CFG.apiBase + "/api/health", { cache: "no-store" }).catch(() => {});
      switchTool("username");
      renderHistory();
      renderSaved();
      $("#runBtn")?.addEventListener("click", run);
      $("#queryInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
      $("#queryInput")?.addEventListener("input", updateDetectHint);
      $("#detectHint")?.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-switch]");
        const target = btn && btn.dataset.switch;
        if (!TOOLS[target] || TOOLS[target].secret || TOOLS[activeTool].secret) return;
        const value = $("#queryInput").value.trim();
        switchTool(target);
        $("#queryInput").value = target === "domain" ? cleanHost(value) : value;
        run();
      });
      $("#examples")?.addEventListener("click", (e) => {
        const el = e.target.closest("[data-ex]");
        if (!el) return;
        $("#queryInput").value = el.dataset.ex;
        run();
      });
      // "/" focuses the search box, like a real tool.
      document.addEventListener("keydown", (e) => {
        if (e.key === "/" && !/^(input|textarea)$/i.test(document.activeElement.tagName)) {
          e.preventDefault(); $("#queryInput")?.focus();
        }
      });
      resultsEl().addEventListener("click", (e) => {
        const el = e.target.closest("[data-quick]");
        if (!el || !TOOLS[el.dataset.quick]) return;
        switchTool(el.dataset.quick);
        $("#queryInput").focus();
      });
      // Cross-tool pivoting: delegated so it survives result re-renders.
      resultsEl().addEventListener("click", (e) => {
        const el = e.target.closest("[data-email-username]");
        if (!el) return;
        e.preventDefault();
        const handle = el.dataset.emailUsername;
        if (!handle?.trim()) return;
        switchTool("username");
        $("#queryInput").value = handle;
        $("#panelSub").textContent = `${TOOLS.username.sub} Matches to this handle do not verify the same person as the email findings.`;
        updateDetectHint();
        $("#queryInput").focus();
        $("#tool")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      resultsEl().addEventListener("click", (e) => {
        const el = e.target.closest("[data-pivot]");
        if (!el) return;
        e.preventDefault();
        doPivot(el.dataset.tool, el.dataset.query);
      });
      // Archive history, asked for one result at a time. The tag sits inside
      // the card's anchor, so the navigation has to be stopped explicitly.
      resultsEl().addEventListener("click", (e) => {
        const el = e.target.closest("[data-wayback]");
        if (!el) return;
        e.preventDefault();
        e.stopPropagation();
        loadWayback(el);
      });
      // Sign-in / upgrade prompts. Unlock uses the query from the rendered
      // preview so editing the input cannot silently unlock a different scan.
      resultsEl().addEventListener("click", async (e) => {
        const unlock = e.target.closest("[data-guest-reveal]");
        if (unlock) {
          if (!signedIn()) {
            try { await window.MyReconAccount.signIn(); }
            catch (error) { toast(error.message || "Sign-in could not complete.", "err"); return; }
          }
          if (signedIn()) await revealGuestReport();
          return;
        }
        const el = e.target.closest("[data-gate]");
        if (!el) return;
        const want = el.dataset.gate;
        if (want === "signin" || want === "unlock" || want === "signin-full") {
          try { await window.MyReconAccount.signIn(); } catch { return; }
          if (want === "signin-full") {
            const full = document.querySelector('input[name="scope"][value="full"]');
            if (full) full.checked = true;
          }
          if (want === "unlock") {
            if (lastResult?.tool !== "username" || !previewMeta(lastResult.data)) return;
            $("#queryInput").value = lastResult.query;
            const full = document.querySelector('input[name="scope"][value="full"]');
            if (full) full.checked = true;
          }
        } else {
          const radio = document.querySelector(`input[name="scope"][value="${want}"]`);
          if (radio) radio.checked = true;
        }
        refreshScopeNote(false);
        if ($("#queryInput").value.trim()) run();
      });
      resultsEl().addEventListener("click", (e) => {
        const b = e.target.closest("[data-view]");
        if (b) setResultsView(b.dataset.view);
      });
      $$('input[name="scope"]').forEach((el) => el.addEventListener("change", () => refreshScopeNote(false)));
      if (window.MyReconAccount) window.MyReconAccount.onChange(accountChanged);
      refreshScopeNote(false);
      $("#revealBtn")?.addEventListener("click", () => {
        setReveal($("#queryInput").type === "password");
        $("#queryInput").focus();
      });
      // Deep-link support: #tool=email&q=... Secret tools are refused outright
      // so a crafted link can never pre-fill, or auto-submit, a password.
      const params = new URLSearchParams(location.hash.replace(/^#/, ""));
      const linked = params.get("tool");
      if (!linked) {
        try {
          const saved = JSON.parse(sessionStorage.getItem(GUEST_REPORT_KEY) || "null");
          if (saved && saved.tool !== "email" && RENDERERS[saved.tool] && Array.isArray(saved.data?.cards) && saved.data?.guest_access?.report_token) {
            switchTool(saved.tool);
            $("#queryInput").value = saved.query || "";
            guestSnapshot = lastResult = saved;
            enterToolMode();
            renderSafely(RENDERERS[saved.tool], saved.data);
            bindActions();
            window.MyReconAccount?.ready.then(() => { if (signedIn()) revealGuestReport(); });
          }
        } catch {}
      }
      if (linked && TOOLS[linked] && !TOOLS[linked].secret) {
        switchTool(linked);
        if (params.get("scan")) openSavedScan(params.get("scan"));
        else if (params.get("q")) { $("#queryInput").value = params.get("q"); run(); }
      }
    }
  });
})();

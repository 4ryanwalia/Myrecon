/* MyRecon, application logic (vanilla JS, no dependencies). */
(function () {
  "use strict";

  const CFG = window.MYRECON;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

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
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    const btn = $("#themeToggle");
    if (btn) btn.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }
  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const prefers = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    applyTheme(saved || prefers);
    $("#themeToggle")?.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
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
    constructor(message, code, account) {
      super(message);
      this.code = code;
      this.account = account || null;
    }
  }
  const GATE_CODES = ["sign_in_required", "upgrade_required", "guest_limit",
    "accounts_unavailable", "auth_invalid"];

  function errorFrom(res, data) {
    const msg = (data && data.error) || `Request failed (${res.status})`;
    return data && GATE_CODES.includes(data.code)
      ? new GateError(msg, data.code, data.account) : new Error(msg);
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
    const ctrl = new AbortController();
    // The full sweep checks 560 platforms and can take well over a minute.
    const timer = setTimeout(() => ctrl.abort(), body && body.scope === "full" ? 180000 : 90000);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(await authHeaders()) },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw errorFrom(res, data);
      }
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
      sub: "Provider analysis, deliverability, linked accounts, and breach exposure.",
      examples: ["test@gmail.com", "contact@github.com"],
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
    resultsEl().innerHTML = `<div class="error-box" role="alert">${esc(msg)}</div>`;
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
          body = "Guests get 5 username scans a day, and they reset at midnight UTC. Every other tool still works.";
          break;
        }
        body = "Guests get 5 scans a day. Sign in with Google (free) for unlimited standard scans and one free Pro 560-platform scan.";
        action = `<button type="button" class="btn btn-primary" data-gate="signin">Sign in with Google</button>`;
        break;
      case "sign_in_required":
      case "auth_invalid":
        title = err.code === "auth_invalid" ? "Please sign in again" : "The Pro scan needs a free account";
        body = "Sign in with Google to run the Pro 560-platform scan. Your first Pro scan is free.";
        action = `<button type="button" class="btn btn-primary" data-gate="signin">Sign in with Google</button>`;
        break;
      case "upgrade_required": {
        title = acct.tier === "pro" ? "You've used your Pro pass scans" : "You've used your free Pro scan";
        body = `A Pro pass adds more (₹99 for 50 scans over 7 days, or ₹299 for 200 over 30 days). The standard 100-platform scan stays unlimited.`;
        action = `<a class="btn btn-primary" href="/pricing.html">See Pro passes</a>
          <button type="button" class="btn btn-ghost" data-gate="standard">Run a standard scan</button>`;
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

  function avatarHTML(r, fallbackChar) {
    const pic = r.profile_pic_url || r.avatar_url;
    if (pic) {
      return `<div class="avatar"><img src="${esc(safeUrl(pic))}" alt="" loading="lazy" referrerpolicy="no-referrer"
        onerror="this.remove();this.parentElement.textContent='${esc(fallbackChar)}'"></div>`;
    }
    return `<div class="avatar">${esc(fallbackChar)}</div>`;
  }

  // -- Username results
  function renderUsername(data) {
    const r = resultsEl();
    const { profiles = [], documents = [], mentions = [] } = data.results || {};
    const s = data.summary || {};
    let html = resultsHeader(`Results for “${esc(data.query.username)}”`, `${s.total || 0} findings`);

    const exp = computeExposure("username", data);
    lastExposure = exp;
    if ((s.profiles || 0) > 0) html += exposureGauge(exp);

    html += `<div class="summary-grid">
      ${stat(s.profiles, "Profiles")}${stat(s.documents, "Documents")}
      ${stat(s.mentions, "Mentions")}${stat(s.clusters, "Identities")}
    </div>`;

    const relDomains = usernameRelatedDomains(data);
    if (relDomains.length) html += pivotRow("Related domains", relDomains.map((d) => pivotChip("domain", d, d)));

    (data.identity_clusters || []).forEach((c) => { html += clusterCard(c); });

    html += exposuresPanel(data.exposures || []);

    if (!profiles.length && !documents.length && !mentions.length) {
      html += emptyState("No public profiles were found for this username.");
    } else {
      html += `<div class="card-grid">`;
      profiles.concat(documents, mentions).forEach((item) => { html += profileCard(item); });
      html += `</div>`;
    }

    html += unverifiedPanel(data.unverified || []);
    html += rejectedPanel(data.rejected || [], s.checked || 0);
    if (data.coverage) html = html.replace(`<div class="summary-grid">`, coverageLine(data.coverage) + `<div class="summary-grid">`);
    else if ((data.query || {}).deep && !signedIn()
      && window.MyReconAccount && window.MyReconAccount.enabled) html += fullScanNudge();
    r.innerHTML = html;
    animateCountUps();
  }

  // The full sweep reports how much of the map it could actually read. A
  // clean result means little if a third of the platforms never answered.
  function coverageLine(c) {
    const decided = (c.found || 0) + (c.not_found || 0);
    return `<p class="coverage-line hint">Pro scan: ${c.total} platforms, ${decided} gave a definite answer,
      ${c.undetermined || 0} could not tell, ${c.unreachable || 0} blocked or timed out from our server
      (the <a href="/app.html">Android app</a> checks from your phone and gets through more of them).</p>`;
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
    return `<div class="panel gate slim"><p>This was the 100-platform scan. Sign in free to run the
      <strong>Pro 560-platform scan</strong> (your first one is free with sign-in).</p>
      <div class="gate-actions"><button type="button" class="btn btn-ghost btn-sm" data-gate="full">Run the Pro scan</button></div></div>`;
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
      if (x.error) {
        rows += `<div class="expo-row"><div class="expo-why">Commit check unavailable, ${esc(x.error)}</div></div>`;
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
    if (r.followers) meta += `<span class="meta-tag">${fmtNum(r.followers)} followers</span>`;
    if (r.is_verified) meta += `<span class="meta-tag">Verified</span>`;
    if (r.is_private) meta += `<span class="meta-tag">Private</span>`;
    if (r.repos) meta += `<span class="meta-tag">${fmtNum(r.repos)} repos</span>`;
    const href = r.url && /^https?:\/\//.test(r.url) ? r.url : null;
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
          <div class="card-url">${esc(hostOf(r.url))}${href ? ` <span class="open-ico">${icon("external", 12)}</span>` : ""}</div>
        </div>
        <span class="tag ${esc(cat)}">${esc(cat)}</span>
      </div>
      ${r.display_name && r.display_name !== platform ? `<div class="card-bio" style="font-weight:600;color:var(--text)">${esc(r.display_name)}</div>` : ""}
      ${r.bio ? `<div class="card-bio">${esc(r.bio.slice(0, 150))}</div>` : ""}
      ${meta ? `<div class="card-meta">${meta}</div>` : ""}`;
    if (href) {
      return `<a class="card card-link" href="${esc(safeUrl(href))}" target="_blank" rel="noopener nofollow"
        aria-label="Open ${esc(platform)} profile in a new tab">${inner}</a>`;
    }
    return `<div class="card">${inner}</div>`;
  }

  // -- Email results
  function renderEmail(data) {
    const a = data.analysis || {}, g = data.gravatar || {}, s = data.summary || {};
    const breaches = data.breaches || {}, hibp = data.hibp;
    let html = resultsHeader(`Email intelligence: ${esc(data.query.email)}`, "");

    const outcome = window.MyReconEmailOutcome(data);
    const exp = outcome.partial ? null : computeExposure("email", data);
    lastExposure = exp;
    if (exp) html += exposureGauge(exp);

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

    // Straight under the verdict: it is what someone who just learned they
    // were breached needs next, and the evidence below can run to 30 cards.
    html += emailNextSteps(outcome, data);
    html += breachAlertCta(outcome);

    if (dw.exposed_data && dw.exposed_data.length) {
      const top = dw.exposed_data.slice(0, 10), max = top[0].count || 1;
      html += `<div class="section-label">What leaked about this address</div>
        <div class="bars">${top.map((x) => `
          <div class="bar-row">
            <div class="bar-k" title="${esc(x.category)}">${esc(x.name)}</div>
            <div class="bar-track"><i style="width:${Math.max(4, (x.count / max) * 100).toFixed(1)}%"></i></div>
            <div class="bar-v">${x.count}</div>
          </div>`).join("")}</div>`;
    }

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

    if (dw.breaches && dw.breaches.length) {
      html += `<div class="section-label">Breaches naming this address
        <span class="hint">${dw.breaches.length} of ${count} shown, largest first</span></div>`;
      html += `<div class="breach-list">${dw.breaches.map((b) => `
        <details class="breach-card" data-bname="${esc(b.name)}" data-byear="${esc(String(b.date || "").slice(0, 4))}">
          <summary>
            <span class="bc-name">${esc(b.name)}</span>
            ${b.verified ? `<span class="pill ok">verified</span>` : ""}
            ${b.password_risk === "plaintext" ? `<span class="pill danger">plaintext passwords</span>` : ""}
            <span class="bc-meta">${esc(b.date)}${b.records ? " · " + fmtNum(b.records) + " records" : ""}</span>
          </summary>
          <div class="bc-body">
            ${b.details ? `<p>${esc(b.details)}</p>` : ""}
            ${b.exposed && b.exposed.length ? `<div class="chips">${b.exposed.map((f) => {
              const danger = /password|ssn|bank|card|phone|address|birth|token/i.test(f);
              return `<span class="pill ${danger ? "danger" : ""}">${esc(f)}</span>`;
            }).join("")}</div>` : ""}
            ${b.industry ? `<div class="hint" style="margin-top:8px">Industry: ${esc(b.industry)}</div>` : ""}
          </div>
        </details>`).join("")}</div>`;
    }

    html += `<div class="section-label">Address analysis</div>`;
    html += datalist([
      ["Provider", `${esc(a.provider)} (${esc(a.provider_type)})`],
      ["Deliverable", a.deliverable ? "Yes, mail server present" : "No MX record found"],
      ["Disposable", a.disposable ? "Yes (flagged)" : "No"],
      ["Plus addressing", a.plus_addressing ? "Yes" : "No"],
      ["Format", esc(a.format)],
      ["MX hosts", (a.mx_hosts || []).map(esc).join("<br>") || "-"],
    ]);

    const emailDomain = baseDomain(data.query.email.split("@")[1] || "");
    html += pivotRow("Pivot", [
      pivotChip("domain", emailDomain, emailDomain),
      ...(a.mx_hosts || []).map((h) => { const d = baseDomain(h); return d && d !== emailDomain ? pivotChip("domain", d, d) : ""; }),
      data.github ? pivotChip("username", data.github.username, data.github.username) : "",
    ]);

    if (s.linked_accounts && s.linked_accounts.length) {
      html += `<div class="section-label">Linked accounts</div>`;
      html += `<div class="chips">${s.linked_accounts.map((x) => `<span class="pill">${esc(x)}</span>`).join("")}</div>`;
    }

    if (g.exists) {
      html += `<div class="section-label">Gravatar profile</div>`;
      html += `<div class="card"><div class="card-head">${avatarHTML(g, "G")}
        <div style="min-width:0"><div class="card-title">${esc(g.display_name || "Gravatar")}</div>
        <div class="card-url"><a href="${esc(safeUrl(g.profile_url))}" target="_blank" rel="noopener nofollow">${esc(hostOf(g.profile_url) || "gravatar.com")}</a></div></div></div>
        ${g.bio ? `<div class="card-bio">${esc(g.bio)}</div>` : ""}</div>`;
    }
    if (data.github) {
      html += `<div class="section-label">GitHub</div>`;
      html += `<div class="card"><div class="card-head">${avatarHTML({ avatar_url: data.github.avatar_url }, "GH")}
        <div style="min-width:0"><div class="card-title">${esc(data.github.username)}</div>
        <div class="card-url"><a href="${esc(safeUrl(data.github.url))}" target="_blank" rel="noopener nofollow">github.com</a></div></div></div></div>`;
    }
    resultsEl().innerHTML = html;
    animateCountUps();
    linkBreachWriteups();
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
      card.querySelector("summary .bc-name")?.insertAdjacentHTML("afterend",
        `<span class="pill bc-writeup">${esc(hit.kind.toLowerCase())}</span>`);
      card.querySelector(".bc-body")?.insertAdjacentHTML("beforeend",
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
      const linked = (s.linked_accounts || []).length;
      const grav = data.gravatar && data.gravatar.exists ? 1 : 0;
      score = Math.round((breached ? 35 : 0) + Math.min(bc, 45) + linked * 6 + grav * 8);
      factors = [
        { label: "Breaches", value: bc },
        { label: "Linked accounts", value: linked },
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
    const tool = TOOLS[activeTool];
    const input = $("#queryInput");
    // Never trim a secret, leading and trailing spaces are part of a password.
    const value = tool.secret ? input.value : input.value.trim();
    if (!value) { input.focus(); toast("Enter something to investigate.", "err"); return; }

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
    if (tool.deep) {
      const scope = currentScope();
      body.deep = scope !== "quick";
      body.scope = scope === "full" ? "full" : "standard";
    }

    $("#runBtn").disabled = true;
    try {
      // The full scan needs an account; ask for one before spending a request
      // on a guaranteed 401. A closed popup just leaves the page as it was.
      if (body.scope === "full" && !signedIn()) {
        if (!(window.MyReconAccount && window.MyReconAccount.enabled)) {
          throw new GateError("Accounts are not switched on yet.", "accounts_unavailable");
        }
        try {
          await window.MyReconAccount.signIn();
        } catch (e) {
          const msg = window.MyReconAccount.friendly(e);
          if (!msg) return; // closed the popup: leave the page as it was
          throw new GateError(msg, "sign_in_required");
        }
      }
      if (activeTool === "username") {
        await runUsernameStream(value, body);
      } else {
        setLoading(activeTool);
        const data = await api(tool.endpoint, body);
        lastResult = { tool: activeTool, query: value, data };
        (RENDERERS[activeTool] || renderIp)(data);
        pushHistory(activeTool, value);
        bindActions();
      }
    } catch (e) {
      if (e instanceof GateError) setGate(e); else setError(e.message);
    } finally {
      $("#runBtn").disabled = false;
      refreshScopeNote(true);
    }
  }

  // ---- Scan size and account state ---------------------------------
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
    if (scope !== "full") {
      note.textContent = st && st.user ? "" : "No sign-in needed.";
      return;
    }
    if (!A || !A.enabled) { note.textContent = "Pro scans open soon."; return; }
    if (!st.user) { note.textContent = "You'll be asked to sign in with Google (free)."; return; }
    if (!acct) { note.textContent = ""; return; }
    note.textContent = acct.tier === "pro"
      ? `Pro: ${acct.pro_scans_left} Pro scans left until ${new Date(acct.pro_until).toLocaleDateString()}.`
      : (acct.free_scans_left > 0 ? "Your free Pro scan is ready." : "Free Pro scan used. A Pro pass adds more.");
  }

  // ---- Username: live streaming scan with progress -----------------
  // Platforms already drawn as live cards during this sweep.
  let liveSeen = new Set();

  function setScanning() {
    liveSeen = new Set();
    resultsEl().innerHTML = `
      <div class="loading scan" role="status" aria-live="polite">
        <div class="scan-head">
          <div class="spinner"></div>
          <div class="scan-meta">
            <h3 id="scanPhase">Starting scan…</h3>
            <p class="hint" id="scanDetail">Preparing the platform sweep.</p>
          </div>
          <div class="scan-pct" id="scanPct">0%</div>
        </div>
        <div class="progress determinate"><i id="scanBar" style="width:0%"></i></div>
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
    const wrap = $("#liveFound"), grid = $("#liveGrid"), n = $("#liveCount");
    if (!wrap || !grid) return;
    wrap.hidden = false;
    grid.insertAdjacentHTML("beforeend", profileCard(r, true));
    if (n) n.textContent = String(liveSeen.size);
  }

  function updateScanUI(ev) {
    const pct = Math.max(0, Math.min(100, Math.round(ev.percent || 0)));
    const bar = $("#scanBar"); if (bar) bar.style.width = pct + "%";
    const p = $("#scanPct"); if (p) p.textContent = pct + "%";
    const phase = $("#scanPhase"); if (phase && ev.phase) phase.textContent = ev.phase + "…";
    const detail = $("#scanDetail"); if (detail && ev.detail) detail.textContent = ev.detail;
  }

  async function runUsernameStream(value, body) {
    setScanning();
    let res;
    try {
      res = await fetch(CFG.apiBase + CFG.endpoints.usernameStream, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(await authHeaders()) },
        body: JSON.stringify(body),
      });
    } catch {
      return runUsernameFallback(value, body); // network hiccup → plain request
    }
    if (res.status === 404) return runUsernameFallback(value, body); // older backend
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
      line = line.trim();
      if (!line) return;
      let ev; try { ev = JSON.parse(line); } catch { return; }
      if (ev.type === "progress") updateScanUI(ev);
      else if (ev.type === "found") addLiveCard(ev.result);
      else if (ev.type === "complete") { finalData = ev.data; savedId = ev.history_id; }
      else if (ev.type === "error") throw new Error(ev.error || "Scan failed");
    };

    while (true) {
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

    if (!finalData) throw new Error("The scan did not complete. Please try again.");
    lastResult = { tool: "username", query: value, data: finalData };
    renderUsername(finalData);
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
      const res = await fetch(CFG.apiBase + "/api/history/" + encodeURIComponent(id),
        { headers: await authHeaders() });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") throw errorFrom(res, data);
      const scan = data.scan;
      const q = scan.query || {};
      $("#queryInput").value = q.username || "";
      const radio = document.querySelector(`input[name="scope"][value="${q.scope === "full" ? "full" : "standard"}"]`);
      if (radio) radio.checked = true;
      lastResult = { tool: "username", query: q.username || "", data: scan };
      renderUsername(scan);
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
    renderUsername(data);
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
    if (!lastResult) return;
    copyText(shareUrl(), "Shareable link copied to clipboard.");
  }

  // Native share sheet (mobile + supported desktop browsers). Falls back to
  // copying the link when the Web Share API isn't available.
  async function shareNative() {
    if (!lastResult) return;
    // lastExposure is only computed for username/email and is not cleared by the
    // other renderers, so gate on the tool or a stale score leaks into the text.
    const scored = lastResult.tool === "username" || lastResult.tool === "email";
    const scoreBit = scored && lastExposure ? `, exposure score ${lastExposure.score}/100 (${lastExposure.label})`
      : lastResult.tool === "email" ? `, ${window.MyReconEmailOutcome(lastResult.data).label}` : "";
    const payload = {
      title: "MyRecon, OSINT report",
      text: `${TOOLS[lastResult.tool].label} report for ${lastResult.query}${scoreBit}`,
      url: shareUrl(),
    };
    if (navigator.share) {
      try { await navigator.share(payload); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
    copyText(`${payload.text}\n${payload.url}`, "Copied, paste it anywhere to share.");
  }

  function copySummary() {
    if (!lastResult) return;
    copyText(buildTextSummary(lastResult), "Summary copied to clipboard.");
  }

  function printReport() {
    if (!lastResult) return;
    const meta = $("#printMeta");
    if (meta) meta.textContent = `${TOOLS[lastResult.tool].label} report · Target: ${lastResult.query} · ${new Date().toLocaleString()}`;
    const prev = document.title;
    document.title = `MyRecon ${TOOLS[lastResult.tool].label} report: ${lastResult.query}`;
    window.print();
    setTimeout(() => { document.title = prev; }, 800);
  }

  function buildTextSummary(res) {
    const d = res.data;
    const L = [`MyRecon, ${TOOLS[res.tool].label} report`, `Target: ${res.query}`, `Generated: ${new Date().toLocaleString()}`, ""];
    const exposure = res.tool === "username" || (res.tool === "email" && !window.MyReconEmailOutcome(d).partial)
      ? computeExposure(res.tool, d) : null;
    if (exposure) {
      L.push(`Digital exposure score: ${exposure.score}/100 (${exposure.label})`, "");
    }
    if (res.tool === "username") {
      const all = [].concat(d.results?.profiles || [], d.results?.documents || [], d.results?.mentions || []);
      L.push(`${all.length} results found:`);
      all.forEach((r) => L.push(`- ${r.platform || hostOf(r.url)}, ${r.url}${r.confidence ? ` [${r.confidence}]` : ""}`));
    } else if (res.tool === "email") {
      const a = d.analysis || {}, s = d.summary || {};
      L.push(`Provider: ${a.provider || "-"} (${a.provider_type || "-"})`);
      L.push(`Deliverable: ${a.deliverable ? "yes" : "no"} · Disposable: ${a.disposable ? "yes" : "no"}`);
      const outcome = window.MyReconEmailOutcome(d);
      L.push(`Breaches: ${outcome.label}${outcome.found && s.breach_count > 0 ? ` (${s.breach_count})` : ""}`);
      L.push(`Coverage: ${outcome.coverage}${outcome.partial ? " (incomplete)" : ""}`, outcome.detail);
      outcome.sources.forEach((source) => L.push(`- ${source.name}: ${source.status}${source.error ? ", " + source.error : ""}`));
      if (outcome.partial) L.push("Exposure score: unavailable because coverage is incomplete.");
      if ((s.linked_accounts || []).length) L.push(`Linked accounts: ${s.linked_accounts.join(", ")}`);
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
  function getSaved() { try { return JSON.parse(localStorage.getItem(SKEY)) || []; } catch { return []; } }
  function saveCurrent(btn) {
    if (!lastResult) return;
    let s = getSaved().filter((x) => !(x.tool === lastResult.tool && x.query === lastResult.query));
    s.unshift({ tool: lastResult.tool, query: lastResult.query, at: Date.now(), note: quickStat(lastResult) });
    localStorage.setItem(SKEY, JSON.stringify(s.slice(0, 50)));
    renderSaved();
    if (btn) { btn.textContent = "Saved"; btn.disabled = true; }
    toast("Saved to your investigations.");
  }
  function quickStat(res) {
    const d = res.data;
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
    wrap.innerHTML = `<div class="history-list">` + s.map((x) => `
      <div class="history-item" data-tool="${esc(x.tool)}" data-query="${esc(x.query)}">
        <div class="ico">${icon(TOOLS[x.tool] ? TOOLS[x.tool].icon : "search", 17)}</div>
        <div class="meta"><div class="q">${esc(x.query)}</div>
          <div class="t">${TOOLS[x.tool] ? esc(TOOLS[x.tool].label) : ""}${x.note ? " · " + esc(x.tool === "email" && x.note === "no breaches" ? "Older result · rerun to verify coverage" : x.note) : ""}</div></div>
        <button type="button" class="icon-btn btn-sm" data-del="${esc(x.tool)}|${esc(x.query)}" aria-label="Remove ${esc(x.query)} from saved" title="Remove ${esc(x.query)} from saved">&times;</button>
      </div>`).join("") + `</div>`;
    $$(".history-item", wrap).forEach((el) => el.addEventListener("click", (e) => {
      if (e.target.closest("[data-del]")) return;
      switchTool(el.dataset.tool); $("#queryInput").value = el.dataset.query; run();
      window.scrollTo({ top: $("#tool").offsetTop - 70, behavior: "smooth" });
    }));
    $$("[data-del]", wrap).forEach((b) => b.addEventListener("click", () => {
      const [tool, query] = b.dataset.del.split("|");
      localStorage.setItem(SKEY, JSON.stringify(getSaved().filter((x) => !(x.tool === tool && x.query === query))));
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
    if (!lastResult) return;
    const base = `myrecon-${lastResult.tool}-${Date.now()}`;
    if (kind === "json") {
      download(base + ".json", JSON.stringify(exportData(lastResult), null, 2), "application/json");
    } else {
      download(base + ".csv", toCSV(lastResult), "text/csv");
    }
    toast(`Exported ${kind.toUpperCase()}.`);
  }

  function exportData(res) {
    if (res.tool !== "email") return res.data;
    const outcome = window.MyReconEmailOutcome(res.data);
    return { ...res.data, summary: { ...res.data.summary,
      breached: outcome.found,
      breach_outcome: outcome.state,
      coverage_incomplete: outcome.partial,
      breach_coverage: { completed: outcome.completed, attempted: outcome.attempted, sources: outcome.sources },
      interpretation: outcome.detail,
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
  function getHistory() { try { return JSON.parse(localStorage.getItem(HKEY)) || []; } catch { return []; } }
  function pushHistory(tool, query) {
    let h = getHistory().filter((x) => !(x.tool === tool && x.query === query));
    h.unshift({ tool, query, at: Date.now() });
    h = h.slice(0, 20);
    localStorage.setItem(HKEY, JSON.stringify(h));
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
    $("#clearHistory")?.addEventListener("click", () => { localStorage.removeItem(HKEY); renderHistory(); });
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
      <div class="quick-starts">${starts.map(([t, q, d]) => `
        <button type="button" class="quick-start" data-quick="${t}">${icon(TOOLS[t].icon, 18)}
          <span><strong>${esc(q)}</strong><small>${esc(d)}</small></span></button>`).join("")}
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
      // Sign-in / upgrade prompts. "full" and "standard" re-run the same
      // handle at that size; "signin" signs in and re-runs what was asked.
      resultsEl().addEventListener("click", async (e) => {
        const el = e.target.closest("[data-gate]");
        if (!el) return;
        const want = el.dataset.gate;
        if (want === "signin") {
          try { await window.MyReconAccount.signIn(); } catch { return; }
        } else {
          const radio = document.querySelector(`input[name="scope"][value="${want}"]`);
          if (radio) radio.checked = true;
        }
        refreshScopeNote(false);
        if ($("#queryInput").value.trim()) run();
      });
      $$('input[name="scope"]').forEach((el) => el.addEventListener("change", () => refreshScopeNote(false)));
      if (window.MyReconAccount) window.MyReconAccount.onChange(() => refreshScopeNote(false));
      refreshScopeNote(false);
      $("#revealBtn")?.addEventListener("click", () => {
        setReveal($("#queryInput").type === "password");
        $("#queryInput").focus();
      });
      // Deep-link support: #tool=email&q=... Secret tools are refused outright
      // so a crafted link can never pre-fill, or auto-submit, a password.
      const params = new URLSearchParams(location.hash.replace(/^#/, ""));
      const linked = params.get("tool");
      if (linked && TOOLS[linked] && !TOOLS[linked].secret) {
        switchTool(linked);
        if (params.get("scan")) openSavedScan(params.get("scan"));
        else if (params.get("q")) { $("#queryInput").value = params.get("q"); run(); }
      }
    }
  });
})();

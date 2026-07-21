/* MyRecon — application logic (vanilla JS, no dependencies). */
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

  const fmtNum = (n) => {
    n = Number(n) || 0;
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
    $("#navToggle")?.addEventListener("click", () => $("#navLinks")?.classList.toggle("open"));
  }

  // ---------------------------------------------------------------- API
  async function api(endpoint, body) {
    const url = CFG.apiBase + endpoint;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 90000);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.error || `Request failed (${res.status})`);
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
      sub: "Search a username across 100+ platforms and enrich matches with avatars and bios.",
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
      sub: "WHOIS/RDAP registration, DNS records, subdomains, and the resolved server's geolocation.",
      examples: ["github.com", "stripe.com", "wikipedia.org"],
    },
    dns: {
      label: "DNS", icon: "compass", placeholder: "e.g. example.com",
      endpoint: CFG.endpoints.dns, field: "domain",
      sub: "A, AAAA, MX, NS, TXT, CNAME, SOA and CAA records via DNS-over-HTTPS.",
      examples: ["cloudflare.com", "google.com"],
    },
    ip: {
      label: "IP", icon: "pin", placeholder: "e.g. 8.8.8.8",
      endpoint: CFG.endpoints.ip, field: "ip",
      sub: "Geolocation, network/ASN ownership, hosting flags, and reverse DNS.",
      examples: ["8.8.8.8", "1.1.1.1"],
    },
  };

  let activeTool = "username";
  let lastResult = null;

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

  function resultsHeader(title, count) {
    return `
      <div class="results-bar">
        <h2>${esc(title)}</h2>
        <span class="hint">${count}</span>
        <div class="results-actions">
          <button class="btn btn-ghost btn-sm" data-action="save">Save</button>
          <button class="btn btn-ghost btn-sm" data-action="share">Copy link</button>
          <button class="btn btn-ghost btn-sm" data-action="copy">Copy</button>
          <button class="btn btn-ghost btn-sm" data-action="print">PDF</button>
          <button class="btn btn-ghost btn-sm" data-export="json">JSON</button>
          <button class="btn btn-ghost btn-sm" data-export="csv">CSV</button>
        </div>
      </div>`;
  }

  function avatarHTML(r, fallbackChar) {
    const pic = r.profile_pic_url || r.avatar_url;
    if (pic) {
      return `<div class="avatar"><img src="${esc(pic)}" alt="" loading="lazy" referrerpolicy="no-referrer"
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

    html += `<div class="summary-grid">
      ${stat(s.profiles, "Profiles")}${stat(s.documents, "Documents")}
      ${stat(s.mentions, "Mentions")}${stat(s.clusters, "Identities")}
    </div>`;

    const relDomains = usernameRelatedDomains(data);
    if (relDomains.length) html += pivotRow("Related domains", relDomains.map((d) => pivotChip("domain", d, d)));

    (data.identity_clusters || []).forEach((c) => { html += clusterCard(c); });

    if (!profiles.length && !documents.length && !mentions.length) {
      html += emptyState("No public profiles were found for this username.");
    } else {
      html += `<div class="card-grid">`;
      profiles.concat(documents, mentions).forEach((item) => { html += profileCard(item); });
      html += `</div>`;
    }
    r.innerHTML = html;
  }

  function stat(n, label) {
    return `<div class="stat"><div class="num">${fmtNum(n || 0)}</div><div class="lbl">${esc(label)}</div></div>`;
  }

  function clusterCard(c) {
    const conf = c.confidence || 0;
    const platforms = (c.platforms || []).map((p) =>
      `<a class="meta-tag" href="${esc(p.url)}" target="_blank" rel="noopener nofollow">${esc(p.platform)}</a>`
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

  function profileCard(r) {
    const platform = r.platform || r.source || hostOf(r.url) || "Result";
    const cat = r.category || "mention";
    const fallback = (platform[0] || "?").toUpperCase();
    let meta = "";
    if (r.confidence === "medium") meta += `<span class="meta-tag conf-medium">Possible match</span>`;
    else if (r.confidence === "high") meta += `<span class="meta-tag conf-high">Confirmed</span>`;
    if (r.followers) meta += `<span class="meta-tag">${fmtNum(r.followers)} followers</span>`;
    if (r.is_verified) meta += `<span class="meta-tag">Verified</span>`;
    if (r.is_private) meta += `<span class="meta-tag">Private</span>`;
    if (r.repos) meta += `<span class="meta-tag">${fmtNum(r.repos)} repos</span>`;
    const href = r.url && /^https?:\/\//.test(r.url) ? r.url : null;
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
      return `<a class="card card-link" href="${esc(href)}" target="_blank" rel="noopener nofollow"
        aria-label="Open ${esc(platform)} profile in a new tab">${inner}</a>`;
    }
    return `<div class="card">${inner}</div>`;
  }

  // -- Email results
  function renderEmail(data) {
    const a = data.analysis || {}, g = data.gravatar || {}, s = data.summary || {};
    const breaches = data.breaches || {}, hibp = data.hibp;
    let html = resultsHeader(`Email intelligence: ${esc(data.query.email)}`, "");

    const breached = s.breached, count = s.breach_count || 0;
    html += `<div class="breach ${breached ? "" : "clean"}">
      <h3>${breached ? "Breach exposure detected" : "No breaches found"}
        <span class="sev" style="color:${breached ? "var(--danger)" : "var(--ok)"}">${breached ? count + " breaches" : "clean"}</span>
      </h3>
      ${breaches.fields && breaches.fields.length ? `<div class="chips">${breaches.fields.slice(0, 14).map((f) => {
        const danger = ["password", "hash", "ssn", "phone", "address", "dob", "ip"].includes(String(f).toLowerCase());
        return `<span class="pill ${danger ? "danger" : ""}">${esc(f)}</span>`;
      }).join("")}</div>` : ""}
      ${breaches.sources && breaches.sources.length ? `<div class="chips">${breaches.sources.slice(0, 12).map((x) =>
        `<span class="pill">${esc(x.name)}${x.date ? " · " + esc(x.date) : ""}</span>`).join("")}</div>` : ""}
      ${hibp ? `<div class="hint" style="margin-top:10px">HIBP: ${hibp.breached ? esc(hibp.count) + " breaches" : "no breaches"}</div>` : ""}
    </div>`;

    html += `<div class="section-label">Address analysis</div>`;
    html += datalist([
      ["Provider", `${esc(a.provider)} (${esc(a.provider_type)})`],
      ["Deliverable", a.deliverable ? "Yes — mail server present" : "No MX record found"],
      ["Disposable", a.disposable ? "Yes (flagged)" : "No"],
      ["Plus addressing", a.plus_addressing ? "Yes" : "No"],
      ["Format", esc(a.format)],
      ["MX hosts", (a.mx_hosts || []).map(esc).join("<br>") || "—"],
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
        <div class="card-url"><a href="${esc(g.profile_url)}" target="_blank" rel="noopener nofollow">${esc(hostOf(g.profile_url) || "gravatar.com")}</a></div></div></div>
        ${g.bio ? `<div class="card-bio">${esc(g.bio)}</div>` : ""}</div>`;
    }
    if (data.github) {
      html += `<div class="section-label">GitHub</div>`;
      html += `<div class="card"><div class="card-head">${avatarHTML({ avatar_url: data.github.avatar_url }, "GH")}
        <div style="min-width:0"><div class="card-title">${esc(data.github.username)}</div>
        <div class="card-url"><a href="${esc(data.github.url)}" target="_blank" rel="noopener nofollow">github.com</a></div></div></div></div>`;
    }
    resultsEl().innerHTML = html;
  }

  // -- Domain results
  function renderDomain(data) {
    const w = data.whois || {}, dns = data.dns || {}, ip = data.primary_ip;
    let html = resultsHeader(`Domain intelligence: ${esc(data.query.domain)}`, "");

    html += `<div class="section-label">Registration (WHOIS / RDAP)</div>`;
    if (w.found) {
      html += datalist([
        ["Registrar", esc(w.registrar) || "—"],
        ["Created", esc(w.created) || "—"],
        ["Updated", esc(w.updated) || "—"],
        ["Expires", esc(w.expires) || "—"],
        ["DNSSEC", w.dnssec == null ? "—" : (w.dnssec ? "Enabled" : "Disabled")],
        ["Status", (w.statuses || []).map(esc).join("<br>") || "—"],
        ["Nameservers", (w.nameservers || []).map(esc).join("<br>") || "—"],
      ]);
    } else {
      html += `<div class="hint">${esc(w.message || w.error || "No registration record found.")}</div>`;
    }

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

  function renderDns(data) {
    let html = resultsHeader(`DNS records: ${esc(data.query.domain)}`, "");
    html += renderDnsBlock(data);
    html += dnsPivotRow(data.records || {});
    resultsEl().innerHTML = html;
  }

  // -- IP results
  function ipDetails(data) {
    const g = data.geo || {}, n = data.network || {}, f = data.flags || {};
    return datalist([
      ["Reverse DNS", esc(data.reverse_dns) || "—"],
      ["Location", [g.city, g.region, g.country].filter(Boolean).map(esc).join(", ") || "—"],
      ["Coordinates", g.latitude != null ? `${g.latitude}, ${g.longitude}` : "—"],
      ["Timezone", esc(g.timezone) || "—"],
      ["ISP", esc(n.isp) || "—"],
      ["Organization", esc(n.organization) || "—"],
      ["ASN", esc(n.asn) || "—"],
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

  function emptyState(msg) {
    return `<div class="empty"><h3>Nothing found</h3><p>${esc(msg)}</p></div>`;
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
    if (!TOOLS[tool] || !query) return;
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

  const RENDERERS = { username: renderUsername, email: renderEmail, domain: renderDomain, dns: renderDns, ip: renderIp };

  // ---------------------------------------------------------------- run
  async function run() {
    const tool = TOOLS[activeTool];
    const input = $("#queryInput");
    const value = input.value.trim();
    if (!value) { input.focus(); toast("Enter something to investigate.", "err"); return; }

    const body = { [tool.field]: value };
    if (tool.deep) body.deep = $("#deepToggle")?.checked || false;

    $("#runBtn").disabled = true;
    try {
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
      setError(e.message);
    } finally {
      $("#runBtn").disabled = false;
    }
  }

  // ---- Username: live streaming scan with progress -----------------
  function setScanning() {
    resultsEl().innerHTML = `
      <div class="loading scan" role="status" aria-live="polite">
        <div class="scan-head">
          <div class="spinner"></div>
          <div class="scan-meta">
            <h3 id="scanPhase">Starting scan…</h3>
            <p class="hint" id="scanDetail">Preparing to check 100+ platforms.</p>
          </div>
          <div class="scan-pct" id="scanPct">0%</div>
        </div>
        <div class="progress determinate"><i id="scanBar" style="width:0%"></i></div>
      </div>`;
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch {
      return runUsernameFallback(value, body); // network hiccup → plain request
    }
    if (res.status === 404) return runUsernameFallback(value, body); // older backend
    if (!res.ok || !res.body) {
      let msg = `Request failed (${res.status})`;
      try { const j = await res.json(); msg = j.error || msg; } catch {}
      throw new Error(msg);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    const handleLine = (line) => {
      line = line.trim();
      if (!line) return;
      let ev; try { ev = JSON.parse(line); } catch { return; }
      if (ev.type === "progress") updateScanUI(ev);
      else if (ev.type === "complete") finalData = ev.data;
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
    pushHistory("username", value);
    bindActions();
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
      else if (a === "share") shareLink();
      else if (a === "copy") copySummary();
      else if (a === "print") printReport();
      else if (a === "subdomains") discoverSubdomains(btn);
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

  function shareLink() {
    if (!lastResult) return;
    const url = `${location.origin}/#tool=${encodeURIComponent(lastResult.tool)}&q=${encodeURIComponent(lastResult.query)}`;
    copyText(url, "Shareable link copied to clipboard.");
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
    document.title = `MyRecon ${TOOLS[lastResult.tool].label} report — ${lastResult.query}`;
    window.print();
    setTimeout(() => { document.title = prev; }, 800);
  }

  function buildTextSummary(res) {
    const d = res.data;
    const L = [`MyRecon — ${TOOLS[res.tool].label} report`, `Target: ${res.query}`, `Generated: ${new Date().toLocaleString()}`, ""];
    if (res.tool === "username") {
      const all = [].concat(d.results?.profiles || [], d.results?.documents || [], d.results?.mentions || []);
      L.push(`${all.length} results found:`);
      all.forEach((r) => L.push(`- ${r.platform || hostOf(r.url)} — ${r.url}${r.confidence ? ` [${r.confidence}]` : ""}`));
    } else if (res.tool === "email") {
      const a = d.analysis || {}, s = d.summary || {};
      L.push(`Provider: ${a.provider || "—"} (${a.provider_type || "—"})`);
      L.push(`Deliverable: ${a.deliverable ? "yes" : "no"} · Disposable: ${a.disposable ? "yes" : "no"}`);
      L.push(`Breaches: ${s.breached ? (s.breach_count || 0) : "none"}`);
      if ((s.linked_accounts || []).length) L.push(`Linked accounts: ${s.linked_accounts.join(", ")}`);
    } else if (res.tool === "domain") {
      const w = d.whois || {};
      L.push(`Registrar: ${w.registrar || "—"}`);
      L.push(`Created: ${w.created || "—"} · Expires: ${w.expires || "—"}`);
      L.push(`Nameservers: ${(w.nameservers || []).join(", ") || "—"}`);
      L.push(`Resolved IP: ${(d.resolved_ips || [])[0] || "—"}`);
    } else if (res.tool === "ip") {
      const g = d.geo || {}, n = d.network || {};
      L.push(`Location: ${[g.city, g.region, g.country].filter(Boolean).join(", ") || "—"}`);
      L.push(`ISP: ${n.isp || "—"} · ASN: ${n.asn || "—"}`);
      L.push(`Reverse DNS: ${d.reverse_dns || "—"}`);
    } else if (res.tool === "dns") {
      Object.entries(d.records || {}).forEach(([t, recs]) => L.push(`${t}: ${recs.map((r) => r.value).join(", ")}`));
    }
    return L.join("\n") + `\n\nvia https://myrecon.xyz`;
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
    if (res.tool === "email") return (d.summary || {}).breached ? `${d.summary.breach_count} breaches` : "no breaches";
    if (res.tool === "domain") return (d.whois || {}).registrar || "domain";
    if (res.tool === "ip") return [(d.geo || {}).city, (d.geo || {}).country].filter(Boolean).join(", ") || "IP";
    if (res.tool === "dns") return `${(d.summary || {}).total_records || 0} records`;
    return "";
  }
  function renderSaved() {
    const wrap = $("#saved");
    if (!wrap) return;
    const s = getSaved();
    if (!s.length) { wrap.innerHTML = `<p class="hint">Save an investigation to pin it here (stored only in this browser).</p>`; return; }
    wrap.innerHTML = `<div class="history-list">` + s.map((x) => `
      <div class="history-item" data-tool="${esc(x.tool)}" data-query="${esc(x.query)}">
        <div class="ico">${icon(TOOLS[x.tool] ? TOOLS[x.tool].icon : "search", 17)}</div>
        <div class="meta"><div class="q">${esc(x.query)}</div>
          <div class="t">${TOOLS[x.tool] ? esc(TOOLS[x.tool].label) : ""}${x.note ? " · " + esc(x.note) : ""}</div></div>
        <button class="icon-btn btn-sm" data-del="${esc(x.tool)}|${esc(x.query)}" aria-label="Remove" title="Remove">&times;</button>
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
      download(base + ".json", JSON.stringify(lastResult.data, null, 2), "application/json");
    } else {
      download(base + ".csv", toCSV(lastResult), "text/csv");
    }
    toast(`Exported ${kind.toUpperCase()}.`);
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
    walk(res.data);
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
    if (!h.length) { wrap.innerHTML = `<p class="hint">Your recent lookups appear here (stored only in this browser).</p>`; return; }
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
  function switchTool(name) {
    if (!TOOLS[name]) return;
    activeTool = name;
    $$(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tool === name)));
    const tool = TOOLS[name];
    $("#queryInput").placeholder = tool.placeholder;
    $("#queryInput").value = "";
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
  }

  function defaultEmpty() {
    return `<div class="empty">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3" stroke-linecap="round"/></svg>
      <h3>Ready when you are</h3><p>Pick a tool, enter a target, and MyRecon will gather open-source intelligence from reliable public sources.</p>
    </div>`;
  }

  // ---------------------------------------------------------------- init
  function buildTabs() {
    const tabs = $("#toolTabs");
    if (!tabs) return;
    tabs.innerHTML = Object.entries(TOOLS).map(([k, t], i) =>
      `<button class="tab" role="tab" data-tool="${k}" aria-selected="${i === 0}">
        <span class="tab-ico">${icon(t.icon, 17)}</span>${esc(t.label)}</button>`
    ).join("");
    $$(".tab", tabs).forEach((el) => el.addEventListener("click", () => switchTool(el.dataset.tool)));
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initNav();
    buildTabs();
    if ($("#tool")) {
      switchTool("username");
      renderHistory();
      renderSaved();
      $("#runBtn")?.addEventListener("click", run);
      $("#queryInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
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
      // Cross-tool pivoting: delegated so it survives result re-renders.
      resultsEl().addEventListener("click", (e) => {
        const el = e.target.closest("[data-pivot]");
        if (!el) return;
        e.preventDefault();
        doPivot(el.dataset.tool, el.dataset.query);
      });
      // Deep-link support: #tool=email&q=...
      const params = new URLSearchParams(location.hash.replace(/^#/, ""));
      if (params.get("tool")) { switchTool(params.get("tool")); if (params.get("q")) { $("#queryInput").value = params.get("q"); run(); } }
    }
  });
})();

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
      label: "Username", icon: "👤", placeholder: "e.g. johndoe or a profile URL",
      endpoint: CFG.endpoints.username, field: "username", deep: true,
      sub: "Search a username across 100+ platforms and enrich matches with avatars and bios.",
    },
    email: {
      label: "Email", icon: "✉️", placeholder: "e.g. name@example.com",
      endpoint: CFG.endpoints.email, field: "email",
      sub: "Provider analysis, deliverability, linked accounts, and breach exposure.",
    },
    domain: {
      label: "Domain", icon: "🌐", placeholder: "e.g. example.com",
      endpoint: CFG.endpoints.domain, field: "domain",
      sub: "WHOIS/RDAP registration, DNS records, and the resolved server's geolocation.",
    },
    dns: {
      label: "DNS", icon: "🧭", placeholder: "e.g. example.com",
      endpoint: CFG.endpoints.dns, field: "domain",
      sub: "A, AAAA, MX, NS, TXT, CNAME, SOA and CAA records via DNS-over-HTTPS.",
    },
    ip: {
      label: "IP", icon: "📍", placeholder: "e.g. 8.8.8.8",
      endpoint: CFG.endpoints.ip, field: "ip",
      sub: "Geolocation, network/ASN ownership, hosting flags, and reverse DNS.",
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
    resultsEl().innerHTML = `<div class="error-box" role="alert">⚠️ ${esc(msg)}</div>`;
  }

  function resultsHeader(title, count) {
    return `
      <div class="results-bar">
        <h2>${esc(title)}</h2>
        <span class="hint">${count}</span>
        <div class="results-actions">
          <button class="btn btn-ghost btn-sm" data-export="json">Export JSON</button>
          <button class="btn btn-ghost btn-sm" data-export="csv">Export CSV</button>
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
        ${avatarHTML(c, "🔗")}
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
    if (r.followers) meta += `<span class="meta-tag">👥 ${fmtNum(r.followers)}</span>`;
    if (r.is_verified) meta += `<span class="meta-tag">✓ Verified</span>`;
    if (r.is_private) meta += `<span class="meta-tag">🔒 Private</span>`;
    if (r.repos) meta += `<span class="meta-tag">📦 ${fmtNum(r.repos)} repos</span>`;
    const href = r.url && /^https?:\/\//.test(r.url) ? r.url : null;
    const inner = `
      <div class="card-head">
        ${avatarHTML(r, fallback)}
        <div style="min-width:0">
          <div class="card-title">${esc(platform)}</div>
          <div class="card-url">${esc(hostOf(r.url))}${href ? ' <span class="open-ico" aria-hidden="true">↗</span>' : ""}</div>
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
      <h3>${breached ? "🛡️ Breach exposure detected" : "✅ No breaches found"}
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
      ["Disposable", a.disposable ? "⚠️ Yes" : "No"],
      ["Plus addressing", a.plus_addressing ? "Yes" : "No"],
      ["Format", esc(a.format)],
      ["MX hosts", (a.mx_hosts || []).map(esc).join("<br>") || "—"],
    ]);

    if (s.linked_accounts && s.linked_accounts.length) {
      html += `<div class="section-label">Linked accounts</div>`;
      html += `<div class="chips">${s.linked_accounts.map((x) => `<span class="pill">${esc(x)}</span>`).join("")}</div>`;
    }

    if (g.exists) {
      html += `<div class="section-label">Gravatar profile</div>`;
      html += `<div class="card"><div class="card-head">${avatarHTML(g, "👤")}
        <div style="min-width:0"><div class="card-title">${esc(g.display_name || "Gravatar")}</div>
        <div class="card-url"><a href="${esc(g.profile_url)}" target="_blank" rel="noopener nofollow">${esc(hostOf(g.profile_url) || "gravatar.com")}</a></div></div></div>
        ${g.bio ? `<div class="card-bio">${esc(g.bio)}</div>` : ""}</div>`;
    }
    if (data.github) {
      html += `<div class="section-label">GitHub</div>`;
      html += `<div class="card"><div class="card-head">${avatarHTML({ avatar_url: data.github.avatar_url }, "🐙")}
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
    else { html += ipDetails(data); }
    resultsEl().innerHTML = html;
  }

  function datalist(rows) {
    return `<div class="datalist">${rows.map(([k, v]) =>
      `<div class="datarow"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`).join("")}</div>`;
  }

  function emptyState(msg) {
    return `<div class="empty"><h3>Nothing found</h3><p>${esc(msg)}</p></div>`;
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
        bindExport();
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
    bindExport();
  }

  async function runUsernameFallback(value, body) {
    setLoading("username");
    const data = await api(CFG.endpoints.username, body);
    lastResult = { tool: "username", query: value, data };
    renderUsername(data);
    pushHistory("username", value);
    bindExport();
  }

  // ---------------------------------------------------------------- export
  function bindExport() {
    $$("[data-export]").forEach((btn) =>
      btn.addEventListener("click", () => exportResult(btn.dataset.export))
    );
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
        <div class="ico">${TOOLS[x.tool] ? TOOLS[x.tool].icon : "🔎"}</div>
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
        <span class="tab-ico" aria-hidden="true">${t.icon}</span>${esc(t.label)}</button>`
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
      $("#runBtn")?.addEventListener("click", run);
      $("#queryInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
      // Deep-link support: #tool=email&q=...
      const params = new URLSearchParams(location.hash.replace(/^#/, ""));
      if (params.get("tool")) { switchTool(params.get("tool")); if (params.get("q")) { $("#queryInput").value = params.get("q"); run(); } }
    }
  });
})();

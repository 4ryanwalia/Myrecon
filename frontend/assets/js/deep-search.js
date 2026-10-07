/* Deep Search: public records, recent activity and indexed pages. */
(function () {
  "use strict";
  const CFG = { apiBase: "", ...window.MYRECON }, A = window.MyReconAccount;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function safeUrl(raw) {
    if (typeof raw !== "string" || raw.length > 2048 || /[\u0000-\u0020\\]/.test(raw)) return "";
    try {
      const u = new URL(raw), host = u.hostname.toLowerCase();
      const local = !host.includes(".") || host.endsWith(".localhost") || host.endsWith(".local") ||
        host.startsWith("[") || /^(?:127|10|0)\./.test(host) || /^169\.254\./.test(host) ||
        /^192\.168\./.test(host) || /^172\.(?:1[6-9]|2\d|3[01])\./.test(host);
      return ["https:", "http:"].includes(u.protocol) && !u.username && !u.password && !local &&
        (!u.port || ["80", "443"].includes(u.port)) ? u.href : "";
    }
    catch { return ""; }
  }
  function link(url, label) {
    const href = safeUrl(url);
    return href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer nofollow">${esc(label || href)} ↗</a>` : esc(label || "Unavailable link");
  }
  let running = false, lastReport = null, activeUid = null, controller = null, renderedReport = null, stoppedByUser = false;
  let guestReport = null, guestLive = false, restoring = false, restoreAttempt = "", reportVersion = 0;
  let linkedNotice = "", renderedLive = false;
  const GUEST_STORAGE = "myrecon-deep-search-guest-v1";
  const accountState = () => A?.state?.() || { user: null, account: null };
  const hasAccess = (state = accountState()) => !!(state.user && state.account?.deep_search_enabled);
  const isLocked = (data) => !!data?.guest_access?.locked;
  function saveGuestReport(data, live = false) {
    guestReport = data;
    guestLive = live;
    try {
      // This report contains backend-redacted section metadata only, never findings.
      sessionStorage.setItem(GUEST_STORAGE, JSON.stringify({ data, live }));
    } catch {}
  }
  function forgetGuestReport() {
    guestReport = null;
    guestLive = false;
    restoreAttempt = "";
    try { sessionStorage.removeItem(GUEST_STORAGE); } catch {}
  }
  function readGuestReport() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(GUEST_STORAGE) || "null");
      if (!isLocked(saved?.data) || typeof saved.data.guest_access.report_token !== "string") return;
      const complete = !!saved.data.guest_access.complete;
      guestReport = { ...saved.data, partial: !!saved.data.partial || !complete };
      guestLive = false;
      if (saved.data.subject) $("#dsInput").value = saved.data.subject + (saved.data.context ? ", " + saved.data.context : "");
      render(guestReport, guestLive);
      $("#dsConsole").hidden = false;
      $("#dsConsole").className = complete ? "ds-console done" : "ds-console failed";
      $("#dsBar").style.width = complete ? "100%" : "0%";
      $("#dsCount").textContent = complete ? "100%" : "Partial";
      $("#dsStatus").textContent = complete
        ? "Retained guest investigation. Sign in with an eligible paid account to view findings."
        : "Retained partial preview. Sign in to check the saved investigation; it may be incomplete.";
      modeHint();
    } catch {}
  }

  const connectionLabels = {
    same_username: "Same username: handle matches; ownership is unverified.",
    profile_link: "Linked from this profile: the source profile contains this account link.",
    platform_verified: "Platform-verified connection: the platform provides verification evidence.",
  };
  function evidenceType(row) {
    // A backend verification record must accompany the stronger label.
    const v = row.verification;
    const verified = v && ((v.provider === "Mastodon" && v.verified_at) ||
      (v.provider === "Keybase" && v.state === 1 && safeUrl(v.proof_url)));
    return row.evidence_type === "platform_verified" ? (verified ? "platform_verified" : "profile_link") :
      Object.hasOwn(connectionLabels, row.evidence_type) ? row.evidence_type : "unknown";
  }
  function existence(row, data) {
    const url = safeUrl(row.destination?.url);
    const account = url && (data.activity || []).find((a) => safeUrl(a.url) === url);
    return account ? { status: "found", confidence: "Platform returned this public account", source: account.source || account.platform } :
      { status: "unverified", confidence: "Destination account has not been confirmed by this report", source: "" };
  }
  function followBody(row) {
    const a = row?.action, token = a?.body?.follow_token;
    return row?.can_follow === true && safeUrl(row.destination?.url) && a?.method === "POST" &&
      a.endpoint === "/api/investigate/stream" && a.requires_user_action === true &&
      typeof token === "string" && token.length > 0 && token.length <= 20000 ? { follow_token: token } : null;
  }
  function profileLabel(p) { return [p?.platform, p?.handle].filter(Boolean).join(" · ") || "Unknown profile"; }
  function connectionDetails(row) {
    const v = row.verification;
    return `<p class="hint">Connection strength: ${esc(connectionLabels[evidenceType(row)] || "Connection evidence unavailable.")}</p>` +
      `<p class="hint">Source profile: ${link(row.source?.url, profileLabel(row.source))}</p>` +
      `<details class="ds-connection-details"><summary>Connection evidence</summary><p>${esc(row.explanation || "No explanation returned.")}</p>` +
      `<p class="hint">Source: ${esc(row.source?.source || "Not returned")}</p>` +
      (evidenceType(row) === "platform_verified" ? `<p class="hint">Verification provider: ${esc(v.provider)}${v.verified_at ? ` · ${esc(v.verified_at)}` : ""}${v.state === 1 ? " · successful proof state" : ""}</p>${v.proof_url ? link(v.proof_url, "View verification evidence") : ""}` : "") + `</details>`;
  }
  function linkedProfiles(data, live) {
    const rows = Array.isArray(data.connections) ? data.connections : null;
    const paid = hasAccess();
    let body = linkedNotice ? `<p class="hint" role="status">${esc(linkedNotice)}</p>` : "";
    if (!rows) body += `<p class="hint">${live ? "Loading linked-profile evidence…" : "Linked-profile discovery is unavailable in this response. Existing source results remain below."}</p>`;
    else if (!rows.length) body += `<p class="hint">${live ? "Looking for explicit account links…" : (data.source_checks || []).some((s) => s.state === "unavailable") ? "No linked-profile suggestions returned. Some sources were unavailable; this does not establish absence." : "No linked-profile suggestions returned. This does not prove that no linked accounts exist."}</p>`;
    else body += rows.map((row, i) => {
      const found = existence(row, data), available = !!followBody(row);
      return `<article class="ds-evidence ds-linked-profile"><h3>${link(row.destination?.url, profileLabel(row.destination))}</h3>` +
        `<p class="hint">Account existence (${esc(found.status)}): ${esc(found.confidence)}${found.source ? ` · ${esc(found.source)}` : ""}</p>` + connectionDetails(row) +
        `<div class="ds-links"><button class="btn btn-ghost btn-sm" type="button" data-ds-follow="${i}"${live || running || !paid || !available ? " disabled" : ""} aria-label="${esc("Check this handle: " + profileLabel(row.destination))}">Check this handle</button>` +
        `<span class="hint">${live ? "Available after this search completes." : !available ? "Unavailable: follow limit reached, already followed, or action not returned." : !paid ? "Your paid access is required." : "Starts a separate handle search with source attribution."}</span></div></article>`;
    }).join("");
    if (data.connection_trail?.length) body += `<details class="ds-connection-details"><summary>Profiles followed in this search (${data.connection_trail.length})</summary>${data.connection_trail.map((row) => `<article class="ds-evidence"><h3>${link(row.destination?.url, profileLabel(row.destination))}</h3>${connectionDetails(row)}</article>`).join("")}</details>`;
    return block("Explore linked profiles", "Account existence and connection strength are separate. Found accounts may belong to different people. Each check requires your action.", body);
  }
  function exportReport(data) {
    // Signed follow actions are temporary account-bound credentials, not evidence.
    const report = JSON.parse(JSON.stringify(data, (key, value) =>
      key === "action" || key === "follow_token" ? undefined : value));
    if (Array.isArray(report.connections)) report.connections = report.connections.map((row) => ({
      ...row, connection_strength: evidenceType(row),
      connection_label: connectionLabels[evidenceType(row)] || "Connection evidence unavailable.",
      account_existence: existence(row, data),
    }));
    return report;
  }
  function download(content, type, extension) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = document.createElement("a"); a.href = url; a.download = "myrecon-deep-search." + extension; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function reportCsv(data) {
    const columns = ["record_type", "platform", "handle", "url", "source_platform", "source_handle", "source_url", "source",
      "account_existence_status", "account_existence_confidence", "connection_strength", "connection_label", "explanation", "verification", "details"];
    const rows = [{ record_type: "report", handle: data.subject, details: JSON.stringify({
      status: data.status, mode: data.mode, subject: data.subject, context: data.context,
      partial: data.partial, queries_run: data.queries_run,
    }) }];
    for (const type of ["activity", "accounts", "people", "owner_links", "source_checks", "plan", "notes"]) {
      for (const item of data[type] || []) rows.push({ record_type: type, platform: item.platform,
        handle: item.handle || item.name, url: item.url, source: item.source, details: JSON.stringify(item) });
    }
    if (data.identity) rows.push({ record_type: "identity", details: JSON.stringify(data.identity) });
    const google = data.google_public_profiles;
    if (google) {
      rows.push({ record_type: "google_lookup", platform: "Google", handle: data.subject,
        details: JSON.stringify({ query: google.query, status: google.status }) });
      for (const source of google.sources || []) rows.push({ record_type: "google_source", platform: "Google",
        source: source.name || source.provider, details: JSON.stringify(source) });
      for (const profile of google.profiles || []) {
        rows.push({ record_type: "google_profile", platform: "Google", handle: profile.display_name || data.subject,
          url: profile.url, source: profile.source, details: JSON.stringify({ ...profile, reviews: undefined }) });
        for (const review of profile.reviews || []) rows.push({ record_type: "google_review", platform: "Google",
          handle: profile.display_name || data.subject, url: review.maps_url, source_url: review.source_url,
          source: profile.review_source || profile.review_coverage?.source,
          details: JSON.stringify({ contributor_id: profile.fields?.ID, ...review }) });
      }
    }
    for (const section of data.sections || []) for (const hit of section.hits || []) rows.push({
      record_type: "indexed_page", url: hit.url, source: hit.engine, details: JSON.stringify({ section: section.label, ...hit }),
    });
    for (const type of ["connections", "connection_trail"]) for (const row of data[type] || []) {
      const found = row.account_existence || existence(row, data);
      rows.push({ record_type: type, platform: row.destination?.platform, handle: row.destination?.handle,
        url: row.destination?.url, source_platform: row.source?.platform, source_handle: row.source?.handle,
        source_url: row.source?.url, source: row.source?.source, account_existence_status: found.status,
        account_existence_confidence: found.confidence, connection_strength: evidenceType(row),
        connection_label: connectionLabels[evidenceType(row)], explanation: row.explanation,
        verification: row.verification ? JSON.stringify(row.verification) : "", details: JSON.stringify(row) });
    }
    const cell = (value) => {
      let s = String(value ?? "");
      // Quoting alone does not prevent spreadsheet formula execution.
      if (/^[\s\u0000-\u001f]*[=+@-]/.test(s)) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    };
    return "\ufeff" + [columns.map(cell).join(","), ...rows.map((row) => columns.map((key) => cell(row[key])).join(","))].join("\r\n");
  }

  function initChrome() {
    const apply = (theme) => {
      document.documentElement.setAttribute("data-theme", theme);
      const meta = $('meta[name="theme-color"]');
      if (meta) meta.content = theme === "light" ? "#f7f7f4" : "#111111";
      $("#themeToggle")?.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
    };
    let saved;
    try { saved = window.localStorage.getItem("myrecon-theme"); } catch {}
    apply(["dark", "light"].includes(saved) ? saved : "dark");
    $("#themeToggle")?.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      try { window.localStorage.setItem("myrecon-theme", next); } catch {}
      apply(next);
    });
    $("#navToggle")?.addEventListener("click", () => $("#navLinks")?.classList.toggle("open"));
  }

  function renderAccess(state) {
    state ||= accountState();
    const paid = hasAccess(state);
    const guest = !state.user;
    const pending = !!(state?.user && !state.account);
    const preview = $("#dsPreview");
    if (preview) preview.hidden = paid || guest;
    $("#dsAccess").className = "ds-access" + (paid ? " is-paid" : "");
    $("#dsAccessTitle").textContent = paid ? "Deep Search is ready" : pending ? "Checking your plan" : guest ? "Run a guest investigation" : "Deep Search requires the ₹99 paid plan";
    $("#dsAccessNote").textContent = paid
      ? "Your paid account includes name, handle and public Google email research. Deep Search does not spend Extended scan credits."
      : pending ? "Waiting for your account details. Retry if your connection was interrupted."
      : guest ? "Investigate public sources now. Section headings stay visible; sign in with an eligible paid account to view the findings."
      : guestReport ? "Your investigation is retained temporarily. The ₹99 plan is required to reveal Deep Search findings. After upgrading, refresh access to open the retained results."
      : "The ₹99 plan includes Deep Search, unlimited standard scans and 10 Extended scans. No renewal. Deep Search does not spend Extended credits.";
    $("#dsSignIn").hidden = !!state.user || !A?.enabled;
    $("#dsUpgrade").hidden = paid || pending || guest;
    $("#dsRetryAccess").hidden = !pending && !(state.user && guestReport);
    $("#dsRetryAccess").textContent = pending ? "Retry plan check" : paid && guestReport ? "Refresh retained results" : "Refresh access";
    $("#dsRun").disabled = running || restoring || (!guest && !paid);
    $("#dsExport").disabled = !paid || !lastReport || isLocked(lastReport);
    $("#dsExportCsv").disabled = $("#dsExport").disabled;
    if (!paid) { $("#dsExport").hidden = true; $("#dsExportCsv").hidden = true; }
    document.querySelectorAll("[data-ds-follow]").forEach((button) => {
      button.disabled = running || restoring || renderedLive || !paid || !followBody(renderedReport?.connections?.[Number(button.dataset.dsFollow)]);
    });
    return guest || paid;
  }

  function modeHint() {
    const subject = $("#dsInput").value.trim().split(",")[0].trim();
    $("#dsMode").textContent = !subject ? "Enter a name, handle or exact email. Add context after a comma for names and handles."
      : subject.includes("@") && !subject.startsWith("@")
        ? "Email search: public Google contributor profile and available Maps reviews. Use an exact email you own or have permission to check; no context is needed."
      : !subject.startsWith("@") && /\s/.test(subject)
        ? "Name search: public records and pages naming this person. Matches stay candidates."
        : "Handle search: public accounts, recent activity and links published by their owners.";
  }
  const aliasButton = (h) => h && /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/.test(h) ? `<button class="btn btn-ghost btn-sm" type="button" data-ds-alias="${esc(h)}">Search ${esc(h)}</button>` : "";
  const block = (title, subtitle, body) => `<section class="ds-panel"><h2 class="ds-ptitle">${esc(title)}</h2><p class="ds-psub">${esc(subtitle)}</p>${body}</section>`;
  const googleStates = {
    pending: ["Checking", "Checking the public Google profile and available Maps reviews…"],
    ok: ["Responded", "The public Google source responded. Review the original contributor profile and sources below."],
    found: ["Profile returned", "A public Google contributor profile was returned for this exact email."],
    partial: ["Partial results", "Some public data was returned, but the review collection or source coverage is incomplete."],
    no_match: ["No profile returned", "The configured source returned no public Google profile. This does not prove that no Google account exists."],
    not_found: ["No profile returned", "The configured source returned no public Google profile. This does not prove that no Google account exists."],
    disabled: ["Unavailable", "The public Google lookup is disabled. No conclusion can be drawn about this email."],
    unconfigured: ["Unavailable", "The public Google lookup is not configured. No conclusion can be drawn about this email."],
    authentication_required: ["Unavailable", "The public Google lookup needs its source connection restored. No conclusion can be drawn about this email."],
    rate_limited: ["Try later", "The public source limited this request. Try again later; no conclusion can be drawn about this email."],
    timeout: ["Timed out", "The public lookup exceeded its time limit. No conclusion can be drawn about this email."],
    unavailable: ["Unavailable", "The public source could not return usable data. No conclusion can be drawn about this email."],
    unknown: ["Inconclusive", "The public response was inconclusive. No conclusion can be drawn about this email."],
    skipped: ["Not checked", "This source was not checked."],
    credits_exhausted: ["Unavailable", "The optional review source is temporarily unavailable. Returned profile data can still be reviewed."],
  };
  const googleState = (status) => Object.prototype.hasOwnProperty.call(googleStates, status) ? googleStates[status] : googleStates.unknown;
  const googleSourceState = (status, name) => /reviews/i.test(name || "") && ["no_match", "not_found"].includes(status)
    ? ["No reviews returned", "The configured source returned no public reviews for this contributor."] : googleState(status);
  const count = (value) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
  function lockedAction() {
    const state = accountState();
    if (!state.user) return A?.enabled
      ? `<strong>Sign in to view the findings</strong><p>Deep Search findings require an eligible paid account.</p><button class="btn btn-sm" type="button" data-ds-unlock>Sign in to view findings</button>`
      : `<strong>Sign in to view the findings</strong><p>Sign-in is temporarily unavailable. The investigation can still run; try signing in again shortly.</p>`;
    if (!state.account) return `<strong>Checking your Deep Search access</strong><p>Your findings stay locked while your plan is checked.</p><button class="btn btn-ghost btn-sm" type="button" data-ds-refresh>Retry plan check</button>`;
    if (!hasAccess(state)) return `<strong>The ₹99 plan is required to view findings</strong><p>You are signed in. Upgrade your account, then refresh access to reveal this investigation.</p><a class="btn btn-sm" href="/pricing.html">Get the ₹99 plan</a><button class="btn btn-ghost btn-sm" type="button" data-ds-refresh>Refresh access</button>`;
    return `<strong>${restoring ? "Opening your findings…" : "View the retained findings"}</strong><p>Open the investigation already completed by the server.</p><button class="btn btn-sm" type="button" data-ds-reveal ${restoring ? "disabled" : ""}>View findings</button>`;
  }
  function renderLocked(data, live) {
    const access = data.guest_access;
    const sections = Array.isArray(access.sections) ? access.sections : [];
    const total = sections.reduce((n, section) => n + (count(section.count) || 0), 0);
    const out = [`<div class="ds-summary"><div><span class="ds-chip">${data.mode === "email" ? "Email" : data.mode === "name" ? "Name" : "Handle"} search${live ? " · live" : ""}</span><h2>${esc(data.subject)}</h2>${data.context ? `<p>Context: ${esc(data.context)}</p>` : ""}</div><p>${total} finding${total === 1 ? "" : "s"} returned${live ? " so far" : ""}</p></div>`];
    for (const section of sections) {
      const findings = count(section.count) || 0;
      const status = section.status || (live ? "pending" : "unknown");
      const description = findings ? `${findings} finding${findings === 1 ? "" : "s"} returned${live ? " so far" : ""}. Details are locked.`
        : ["no_match", "not_found", "empty", "ok", "found"].includes(status)
          ? "No public findings were returned for this section. This does not establish absence."
          : ["partial", "unknown"].includes(status)
            ? "The source response was incomplete or inconclusive. No conclusion can be drawn."
            : status === "pending" ? live ? "This section is still being checked." : "This section had not finished when the last results were returned."
              : "This source could not return usable findings. No conclusion can be drawn.";
      const body = findings
        ? `<div class="ds-locked-findings"><div class="ds-locked-placeholders" aria-hidden="true" inert>${Array.from({ length: Math.min(findings, 3) }, () => `<div class="ds-locked-placeholder"><span></span><span></span><span></span></div>`).join("")}</div><div class="ds-unlock-overlay">${lockedAction()}</div></div>`
        : `<p class="hint">${esc(live && status === "pending" ? "This section is still being checked." : description)}</p>`;
      out.push(block(section.label, findings ? description : "Public source availability and returned findings.", body));
    }
    if (!sections.length) out.push(`<div class="ds-panel"><p>${live ? "Checking public sources. Sections appear when the server returns them." : "No public findings were returned. This does not prove that no account or record exists."}</p></div>`);
    if (data.partial) out.push(`<aside class="ds-panel" role="status"><strong>Partial investigation</strong><p>Some public sources could not finish or returned limited data. Available findings stay locked; unavailable checks do not establish absence.</p></aside>`);
    if (access.report_token && total) out.push(`<p class="ds-retained-note">The server temporarily retains this investigation for up to 30 minutes. Sign in to reveal it without repeating the scan. A server restart can end retention sooner.</p>`);
    $("#dsOut").innerHTML = out.join("");
    $("#dsExport").hidden = true;
    $("#dsExport").disabled = true;
    $("#dsExportCsv").hidden = true;
    $("#dsExportCsv").disabled = true;
  }
  function googleLink(url, label) {
    const href = safeUrl(url);
    if (!href) return esc(label);
    const u = new URL(href);
    return u.protocol === "https:" && !u.port && ["google.com", "www.google.com", "maps.google.com"].includes(u.hostname) && u.pathname.startsWith("/maps/")
      ? link(href, label) : esc(label);
  }
  function googleProfiles(data, live) {
    const lookup = data.google_public_profiles || {};
    const profiles = Array.isArray(lookup.profiles) ? lookup.profiles : [];
    const sources = Array.isArray(lookup.sources) ? lookup.sources : [];
    const status = lookup.status || (live ? "pending" : "unavailable"), [label, message] = googleState(status);
    const cards = profiles.map((profile) => {
      const reviews = Array.isArray(profile.reviews) ? profile.reviews : [], coverage = profile.review_coverage || {};
      const reported = count(coverage.total_reported), limited = coverage.limited !== false || coverage.status === "partial";
      const coverageReason = ["no_match", "not_found"].includes(coverage.status)
        ? "The configured source returned no public reviews for this contributor."
        : coverage.reason || googleState(coverage.status)[1];
      const coverageLabel = `${reviews.length} reviews returned${reported !== null ? ` · ${reported} reported by source` : ""}`;
      const reviewRows = reviews.map((review) => {
        const rating = typeof review.rating === "number" && Number.isFinite(review.rating) && review.rating >= 1 && review.rating <= 5 ? review.rating : null;
        const date = [...new Set([review.date_label, review.date].filter(Boolean))].join(" · ");
        return `<li class="ds-google-review"><h4>${googleLink(review.maps_url, review.name || "Reviewed place")}</h4>${review.address ? `<p class="hint">${esc(review.address)}</p>` : ""}<div class="ds-links">${rating !== null ? `<span class="ds-google-rating" aria-label="${rating} out of 5 stars">★ ${rating} / 5</span>` : ""}${date ? `<span class="hint">${esc(date)}</span>` : ""}</div>${review.text ? `<p class="ds-google-text">${esc(review.text)}</p>` : `<p class="hint">Rating only; no review text returned.</p>`}${review.owner_reply ? `<div class="ds-google-reply"><strong>Reply from the owner</strong>${review.owner_reply_date ? `<span class="hint"> · ${esc(review.owner_reply_date)}</span>` : ""}<p class="ds-google-text">${esc(review.owner_reply)}</p></div>` : ""}<p>${googleLink(review.source_url, "View public source")}</p></li>`;
      }).join("");
      const stats = Object.entries(profile.stats || {}).filter(([, value]) => count(value) !== null).map(([key, value]) => `<span class="ds-chip">${esc(key)} reported: ${value}</span>`).join(" ");
      return `<article class="ds-evidence ds-google-profile"><h3>${googleLink(profile.url, profile.display_name || "Google contributor profile")}</h3><p class="hint">${esc(profile.evidence || "Returned by the exact-email Google lookup. Review the original source before linking identities.")}</p>${stats ? `<div class="ds-links">${stats}</div>` : ""}<div class="ds-google-coverage"><strong>${esc(coverageLabel)}</strong><p>${esc(coverageReason)}</p>${limited ? `<p class="hint">Partial collection. Returned reviews may be capped, filtered or unavailable; they are not a complete activity history.</p>` : ""}</div>${reviews.length ? `<ul class="ds-google-reviews">${reviewRows}</ul>` : `<p class="hint">No public review records were returned. This does not establish that the contributor has never reviewed a place.</p>`}<p class="hint">${esc(profile.review_source || coverage.source || profile.source || "Google public contributions")}</p></article>`;
    }).join("");
    const checks = sources.length ? `<div class="ds-source-checks">${sources.map((source) => {
      const [sourceLabel, sourceMessage] = googleSourceState(source.status, source.name);
      return `<div><span>${esc(source.name || source.provider || "Google source")}</span><span class="ds-chip">${esc(sourceLabel)}</span></div><p class="hint">${esc(sourceMessage)}</p>`;
    }).join("")}</div>` : "";
    return block("Google Maps contributor & public reviews", "Exact-email public Google research. Only public contributor data and reviews returned by the source are shown.", `<p class="ds-google-status" role="status"><span class="ds-chip">${esc(label)}</span> ${esc(message)}</p>${cards}${checks}`);
  }
  function render(data, live = false) {
    renderedReport = data;
    renderedLive = live;
    if (isLocked(data)) {
      saveGuestReport(data, live);
      renderLocked(data, live);
      return;
    }
    const activity = data.activity || [], accounts = data.accounts || [], people = data.people || [], sections = data.sections || [];
    const pages = sections.reduce((n, s) => n + (s.hits || []).length, 0);
    const emailMode = data.mode === "email";
    const google = data.google_public_profiles || {}, googleRows = Array.isArray(google.profiles) ? google.profiles : [];
    const reviewCount = googleRows.reduce((n, profile) => n + (Array.isArray(profile.reviews) ? profile.reviews.length : 0), 0);
    const summary = emailMode ? `${googleRows.length} public Google profiles · ${reviewCount} reviews returned${live ? " so far" : ""}` : `${activity.length} public accounts · ${accounts.length + people.length} name candidates · ${pages} indexed pages`;
    const out = [`<div class="ds-summary"><div><span class="ds-chip">${emailMode ? "Email" : data.mode === "name" ? "Name" : "Handle"} search${live ? " · live" : ""}</span><h2>${esc(data.subject)}</h2>${data.context ? `<p>Context: ${esc(data.context)}</p>` : ""}</div><p>${esc(summary)}</p></div>`];
    if (emailMode || data.google_public_profiles) out.push(googleProfiles(data, live));
    if (!emailMode) out.push(linkedProfiles(data, live));
    if (people.length) out.push(block("Public figure records", "Wikidata candidates. Check each record's description before making a connection.", people.map((p) =>
      `<article class="ds-evidence"><h3>${link(p.url, p.name)}</h3><p>${esc(p.description)}</p><div class="ds-links">${Object.entries(p.facts || {}).map(([k, v]) => `<span class="ds-chip">${esc(k)}: ${esc(v)}</span>`).join(" ")}</div><div class="ds-links">${(p.links || []).map((l) => link(l.url, l.label)).join(" ")}</div><p class="hint">${esc(p.source)} · candidate</p></article>`).join("")));
    if (accounts.length) out.push(block("Name matches", "Records carrying this name. A shared name does not confirm identity.", accounts.map((a) =>
      `<article class="ds-evidence"><h3>${link(a.url, a.platform + " · " + (a.handle || data.subject))}</h3><p>${esc(a.detail)}</p><p class="hint">${esc(a.source)} · candidate</p></article>`).join("")));
    if (activity.length) out.push(block("Public accounts & recent activity", "Each account was returned by its platform. Accounts using the same handle may belong to different people.", activity.map((a) => {
      const posts = a.posts || [];
      return `<article class="ds-evidence"><h3>${link(a.url, a.platform + " · " + a.handle)}</h3>${a.display_name ? `<p><strong>${esc(a.display_name)}</strong></p>` : ""}<p>${esc(a.bio || "")}</p><div class="ds-links">${Object.entries(a.stats || {}).filter(([, v]) => v != null).map(([k, v]) => `<span class="ds-chip">${esc(k)}: ${esc(v)}</span>`).join(" ")}${a.since ? `<span class="ds-chip">Since ${esc(a.since)}</span>` : ""}</div><p class="hint">Source: ${esc(a.source)}</p>${posts.length ? `<ul class="ds-posts">${posts.map((p) => `<li><p>${esc(p.text)}</p><span class="hint">${esc([p.context, p.date].filter(Boolean).join(" · "))}</span> ${link(p.url, "View source")}</li>`).join("")}</ul>` : ""}${a.activity_available === false ? `<p class="hint">The account responded, but its recent activity could not be checked.</p>` : !posts.length ? `<p class="hint">No recent public posts were returned by this source.</p>` : ""}</article>`;
    }).join("")));
    if (data.owner_links?.length) out.push(block("Links declared by account owners", "These links were published on the source profile. They are owner statements, not independently confirmed identities.", data.owner_links.map((l) =>
      `<article class="ds-evidence">${link(l.url, l.label)} ${Array.isArray(data.connections) ? "" : aliasButton(l.alias)}<p class="hint">Published on ${esc(l.declared_on)}${l.source_url ? " · " + link(l.source_url, "Source profile") : ""}</p></article>`).join("")));
    if (data.identity) out.push(block("Keybase published proofs", "Proofs reported by Keybase. MyRecon has not independently revalidated the signatures.", (data.identity.proofs || []).map((p) =>
      `<article class="ds-evidence">${link(p.url, p.platform + " · " + p.handle)}${!Array.isArray(data.connections) && p.is_alias && /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/.test(p.handle) ? `<span class="ds-chip">Different handle</span><button class="btn btn-ghost btn-sm" type="button" data-ds-alias="${esc(p.handle)}">Search this handle</button>` : ""}</article>`).join("") || `<p class="hint">No public account proofs returned.</p>`));
    for (const section of sections) if (section.hits?.length) out.push(block(section.label, "Indexed pages, with the query and search provider attached. A mention is not proof of account ownership.", section.hits.map((h) =>
      `<article class="ds-evidence"><h3>${link(h.url, h.title || h.url)}</h3><p>${esc(h.snippet)}</p><div class="ds-links"><span class="ds-chip">${h.profile ? "Account page URL" : "Indexed mention"}</span>${h.matches_context ? `<span class="ds-chip">Matches context</span>` : ""}</div><p class="hint">${esc(h.engine)} · <code>${esc(h.query)}</code></p></article>`).join("")));
    if (!live) {
      if (!emailMode && !activity.length && !accounts.length && !people.length && !pages && !data.connections?.length) out.push(`<div class="ds-panel"><p>No public results were returned. Review source availability and try the query links below; this does not prove that no account or record exists.</p></div>`);
      out.push(block("Sources & limits", "Unavailable sources could not be checked. An empty response is not a conclusion about a person.", `<div class="ds-source-checks">${(data.source_checks || []).map((s) => `<div><span>${esc(s.source)}</span><span class="ds-chip">${esc(emailMode ? googleSourceState(s.state, s.source)[0] : s.state === "unavailable" ? "Unavailable" : s.state === "not_found" ? "No account returned" : "Responded")}</span></div>`).join("")}</div><ul class="ds-notes">${(data.notes || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`));
      if (!emailMode) out.push(`<details class="ds-panel ds-plan"><summary>Continue with the search queries (${Number(data.queries_run) || 0} ran here)</summary><p class="ds-psub">Open a query to run it in Google. Browser links remain available when a provider refuses this server.</p>${(data.plan || []).map((q) => `<div class="ds-query-link"><span class="ds-chip">${q.executed ? "Ran here" : "Browser link"}</span><span>${esc(q.label)}</span>${link(q.google, q.text)}</div>`).join("")}</details>`);
    }
    $("#dsOut").innerHTML = out.join("");
  }
  async function revealGuestReport(force = false) {
    const state = accountState(), token = guestReport?.guest_access?.report_token;
    if (!token || !hasAccess(state) || running || restoring) return;
    const attempt = `${state.user.uid}:${token}:${guestReport.guest_access.complete ? "complete" : "partial"}`;
    if (!force && restoreAttempt === attempt) return;
    restoreAttempt = attempt;
    const uid = state.user.uid, version = reportVersion;
    let errorMessage = "";
    const restoreController = new AbortController();
    const restoreTimer = setTimeout(() => restoreController.abort(), 20000);
    restoring = true;
    renderAccess(state);
    renderLocked(guestReport, guestLive);
    try {
      const headers = await A.authHeaders();
      if (accountState().user?.uid !== uid) return;
      const res = await fetch(CFG.apiBase + "/api/guest-reports/reveal", {
        method: "POST", cache: "no-store", headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ report_token: token }), signal: restoreController.signal,
      });
      const report = await res.json().catch(() => ({}));
      if (version !== reportVersion || accountState().user?.uid !== uid) return;
      if (!res.ok || report.tool !== "deep_search" || !report.data) {
        if (report.account) renderAccess({ ...accountState(), account: report.account });
        throw new Error(res.status === 410
          ? "This retained investigation has expired or the server restarted. Investigate again to obtain fresh results."
          : report.error || "Could not open the retained investigation. Try again shortly.");
      }
      if (!hasAccess()) return;
      const failed = report.data.status === "error";
      const complete = !!report.complete && !failed && report.data.status !== "pending";
      lastReport = complete ? report.data : null;
      render({ ...report.data, partial: !!report.data.partial || !complete });
      $("#dsConsole").hidden = false;
      $("#dsConsole").className = complete ? "ds-console done" : "ds-console failed";
      $("#dsStatus").textContent = complete
        ? report.data.partial ? "Retained investigation opened with source limits. Review unavailable sources below." : "Retained investigation opened. The scan was not repeated."
        : failed ? "The retained investigation failed. Available partial findings are shown; the scan was not repeated."
          : "Retained partial results opened. This snapshot is incomplete; refresh retained results to check for updates.";
      if (failed) $("#dsOut").insertAdjacentHTML("afterbegin", `<div class="error-box" role="alert">${esc(report.data.error || "The investigation could not finish. Available partial findings are shown below.")}</div>`);
      $("#dsBar").style.width = complete ? "100%" : "0%";
      $("#dsCount").textContent = complete ? "100%" : "Partial";
      $("#dsExport").hidden = !complete;
      $("#dsExportCsv").hidden = !complete;
    } catch (err) {
      if (version === reportVersion && accountState().user?.uid === uid) {
        errorMessage = err.name === "AbortError" ? "Opening the retained investigation timed out. Try View findings again." : err.message || "Could not open the retained investigation.";
      }
    } finally {
      clearTimeout(restoreTimer);
      restoring = false;
      renderAccess(accountState());
      if (isLocked(renderedReport)) renderLocked(renderedReport, guestLive);
      if (errorMessage) {
        $("#dsAccessNote").textContent = errorMessage;
        $("#dsOut").insertAdjacentHTML("afterbegin", `<div class="error-box" role="alert">${esc(errorMessage)}</div>`);
      }
    }
  }
  function resetConsole() {
    reportVersion++;
    forgetGuestReport();
    $("#dsConsole").hidden = false;
    $("#dsConsole").className = "ds-console running";
    $("#dsBar").style.width = "0%";
    $("#dsStatus").textContent = "Starting Deep Search…";
    $("#dsCount").textContent = "";
    $("#dsOut").innerHTML = "";
    $("#dsOut").setAttribute?.("aria-busy", "true");
    $("#dsExport").hidden = true;
    $("#dsExportCsv").hidden = true;
    lastReport = null;
    renderedReport = null;
  }
  function handleEvent(ev) {
    if (ev.type === "progress") {
      const percent = Math.max(0, Math.min(100, Math.round(Number(ev.percent) || 0)));
      $("#dsBar").style.width = percent + "%";
      $("#dsCount").textContent = percent + "%";
      $("#dsStatus").textContent = ev.detail || ev.phase || "Checking sources…";
    } else if (ev.type === "partial") render(ev.data, true);
    else if (ev.type === "error") throw new Error(ev.error || "Deep Search failed.");
    else if (ev.type === "complete") {
      if (!ev.data || ev.data.status === "error") throw new Error(ev.data?.error || "Deep Search failed.");
      lastReport = isLocked(ev.data) ? null : ev.data;
      render(ev.data);
      $("#dsConsole").className = "ds-console done";
      $("#dsBar").style.width = "100%";
      $("#dsCount").textContent = "100%";
      const hasGuestFindings = ev.data.guest_access?.sections?.some((section) => (count(section.count) || 0) > 0);
      $("#dsStatus").textContent = isLocked(ev.data)
        ? !hasGuestFindings ? "Investigation finished without returned findings. Review source availability below; this does not establish absence."
          : ev.data.partial ? "Investigation finished with source limits. Sign in with an eligible paid account to view returned findings." : "Investigation complete. Sign in with an eligible paid account to view the findings."
        : ev.data.mode === "email"
        ? `Google lookup finished: ${googleState(ev.data.google_public_profiles?.status || ev.data.status)[0].toLowerCase()}.`
        : ev.data.partial ? "Complete with source limits. Review unavailable sources below." : "Deep Search complete.";
      $("#dsExport").hidden = isLocked(ev.data) || !hasAccess();
      $("#dsExportCsv").hidden = $("#dsExport").hidden;
      return true;
    }
    return false;
  }
  async function run(requestBody = null) {
    if (running || restoring) return;
    await A?.ready;
    if (running || restoring) return;
    if (!renderAccess(accountState())) return;
    if (requestBody && !hasAccess()) return;
    const input = $("#dsInput"), query = input.value.trim();
    if (!requestBody && !query) { input.focus(); return; }
    const previousReport = requestBody && !isLocked(lastReport) ? lastReport : null;
    running = true;
    stoppedByUser = false;
    linkedNotice = "";
    const uid = accountState().user?.uid || null;
    $("#dsRun").disabled = true;
    $("#dsStop").hidden = false;
    resetConsole();
    if (previousReport) {
      linkedNotice = "Checking this handle… Source evidence remains visible while the new check runs.";
      render(previousReport);
    }
    controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 100000);
    let reader, completed = false, deniedAccount = null;
    try {
      // Bind request authorization to the identity captured above. Signing in
      // during a guest run must never turn that run into a private stream.
      const authHeaders = uid && A ? await A.authHeaders() : {};
      if (uid && accountState().user?.uid !== uid) throw new Error("Your account changed. Run a new search with your current account.");
      const res = await fetch(CFG.apiBase + "/api/investigate/stream", {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(requestBody || { query }), signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        const failure = await res.json().catch(() => ({}));
        deniedAccount = failure.account || null;
        throw new Error(failure.error || `Deep Search failed (HTTP ${res.status}).`);
      }
      reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const line = (s) => {
        if (uid && accountState().user?.uid !== uid) throw new Error("Your account changed. Run a new search with your current account.");
        if (s.trim()) completed = handleEvent(JSON.parse(s)) || completed;
      };
      for (;;) {
        const { done, value } = await reader.read();
        // A guest may sign in while the redacted stream continues. Private streams
        // stop as soon as their authenticated account changes.
        if (uid && accountState().user?.uid !== uid) throw new Error("Your account changed. Run a new search with your current account.");
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const entry of lines) line(entry);
      }
      buffer += decoder.decode();
      line(buffer);
      if (!completed) throw new Error("The search ended before completion. Results shown so far may be incomplete.");
    } catch (err) {
      $("#dsConsole").className = "ds-console failed";
      const message = err.name === "AbortError"
        ? (stoppedByUser ? "Search cancelled. Results shown so far may be incomplete." : "Search timed out. Results shown so far may be incomplete.") : err.message;
      if (uid && accountState().user?.uid !== uid) return;
      if (previousReport) {
        lastReport = previousReport;
        linkedNotice = "Handle check did not complete. The source report is shown; you can retry the check.";
        render(previousReport);
        $("#dsExport").hidden = !hasAccess();
        $("#dsExportCsv").hidden = !hasAccess();
      } else if (!completed && renderedReport?.mode === "email" && !isLocked(renderedReport) && accountState().user?.uid === uid) {
        const status = err.name === "AbortError" ? (stoppedByUser ? "unknown" : "timeout") : "unavailable";
        render({ ...renderedReport, status, partial: true,
          google_public_profiles: { ...renderedReport.google_public_profiles, status } });
      }
      if (!previousReport && !completed && renderedReport && (isLocked(renderedReport) || renderedReport.mode !== "email")) render({ ...renderedReport, partial: true });
      $("#dsStatus").textContent = message || "Deep Search failed.";
      $("#dsOut").insertAdjacentHTML("afterbegin", `<div class="error-box" role="alert">${esc(message)}</div>`);
    } finally {
      clearTimeout(timer);
      if (reader) await reader.cancel().catch(() => {});
      running = false;
      $("#dsOut").setAttribute?.("aria-busy", "false");
      controller = null;
      $("#dsStop").hidden = true;
      if (A) await A.refreshAccount().catch(() => {});
      renderAccess(deniedAccount ? { ...accountState(), account: deniedAccount } : accountState());
      if (guestReport && hasAccess()) await revealGuestReport();
    }
  }
  document.addEventListener("DOMContentLoaded", async () => {
    initChrome(); modeHint();
    let launchQuery = "";
    try {
      const launch = JSON.parse(sessionStorage.getItem("myrecon.deep-search.launch") || "null");
      sessionStorage.removeItem("myrecon.deep-search.launch");
      if (typeof launch?.query === "string") launchQuery = launch.query.slice(0, 254).trim();
    } catch {}
    if (!launchQuery) readGuestReport();
    else { $("#dsInput").value = launchQuery; modeHint(); }
    $("#dsInput")?.addEventListener("input", modeHint);
    $("#dsInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); run(); } });
    $("#dsRun")?.addEventListener("click", () => run());
    $("#dsStop")?.addEventListener("click", () => { stoppedByUser = true; controller?.abort(); });
    const signIn = async () => {
      if (!A?.enabled) { $("#dsAccessNote").textContent = "Sign-in is temporarily unavailable. Try again shortly."; return; }
      try { await A.signIn(); await A.refreshAccount(); onState(A.state()); await revealGuestReport(true); }
      catch (e) { $("#dsAccessNote").textContent = A.friendly(e) || e.message; }
    };
    const refreshAccess = async () => {
      try { await A?.refreshAccount(); onState(accountState()); await revealGuestReport(true); }
      catch { $("#dsAccessNote").textContent = "Could not check your plan. Try again shortly."; }
    };
    $("#dsSignIn")?.addEventListener("click", signIn);
    $("#dsRetryAccess")?.addEventListener("click", refreshAccess);
    $("#dsOut")?.addEventListener("click", (e) => {
      if (e.target.closest("[data-ds-unlock]")) { signIn(); return; }
      if (e.target.closest("[data-ds-refresh]")) { refreshAccess(); return; }
      if (e.target.closest("[data-ds-reveal]")) { revealGuestReport(true); return; }
      if (isLocked(renderedReport) || !hasAccess()) return;
      const follow = e.target.closest("[data-ds-follow]");
      if (follow) {
        if (follow.disabled || running || restoring || renderedLive) return;
        const row = renderedReport?.connections?.[Number(follow.dataset.dsFollow)], body = followBody(row);
        if (!body) return;
        $("#dsInput").value = "@" + row.destination.handle;
        modeHint(); run(body);
        $("#dsConsole").scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      const b = e.target.closest("[data-ds-alias]");
      if (b && /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/.test(b.dataset.dsAlias)) {
        $("#dsInput").value = "@" + b.dataset.dsAlias;
        modeHint(); run();
        $("#dsInput").scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
    $("#dsExport")?.addEventListener("click", () => {
      if (!lastReport || isLocked(lastReport) || !hasAccess() || running || restoring) return;
      download(JSON.stringify(exportReport(lastReport), null, 2), "application/json", "json");
    });
    $("#dsExportCsv")?.addEventListener("click", () => {
      if (!lastReport || isLocked(lastReport) || !hasAccess() || running || restoring) return;
      download(reportCsv(exportReport(lastReport)), "text/csv;charset=utf-8", "csv");
    });
    const onState = (state) => {
      const uid = state?.user?.uid || null;
      if (activeUid && activeUid !== uid) {
        reportVersion++;
        controller?.abort(); lastReport = null; renderedReport = null; linkedNotice = "";
        forgetGuestReport();
        $("#dsOut").innerHTML = ""; $("#dsExport").hidden = true; $("#dsExportCsv").hidden = true;
      } else if (!hasAccess(state) && renderedReport && !isLocked(renderedReport)) {
        lastReport = null;
        if (guestReport) { renderedReport = guestReport; renderLocked(guestReport, guestLive); }
        else { renderedReport = null; $("#dsOut").innerHTML = ""; }
      }
      activeUid = uid; renderAccess(state);
      if (isLocked(renderedReport)) renderLocked(renderedReport, guestLive);
      if (hasAccess(state)) revealGuestReport();
    };
    if (A) { A.onChange(onState); await A.ready; }
    onState(accountState());
    if (launchQuery) run();
  });
})();

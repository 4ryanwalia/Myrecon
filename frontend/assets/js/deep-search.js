/* Paid Deep Search: public records, recent activity and indexed pages. */
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
  let running = false, lastReport = null, activeUid = null, controller = null, renderedReport = null;
  let linkedNotice = "", stoppedByUser = false, renderedLive = false;
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
    const paid = !!A?.state()?.account?.deep_search_enabled;
    let body = linkedNotice ? `<p class="hint" role="status">${esc(linkedNotice)}</p>` : "";
    if (!rows) body += `<p class="hint">${live ? "Loading linked-profile evidence…" : "Linked-profile discovery is unavailable in this response. Existing source results remain below."}</p>`;
    else if (!rows.length) body += `<p class="hint">${live ? "Looking for explicit account links…" : (data.source_checks || []).some((s) => s.state === "unavailable") ? "No linked-profile suggestions returned. Some sources were unavailable; this does not establish absence." : "No linked-profile suggestions returned. This does not prove that no linked accounts exist."}</p>`;
    else body += rows.map((row, i) => {
      const found = existence(row, data), available = !!followBody(row);
      return `<article class="ds-evidence ds-linked-profile"><h3>${link(row.destination?.url, profileLabel(row.destination))}</h3>` +
        `<p class="hint">Account existence (${esc(found.status)}): ${esc(found.confidence)}${found.source ? ` · ${esc(found.source)}` : ""}</p>` + connectionDetails(row) + (window.MyReconMatchChoices?.controls(row.destination?.url) || "") +
        `<div class="ds-links"><button class="btn btn-ghost btn-sm" type="button" data-ds-follow="${i}"${live || running || !paid || !available ? " disabled" : ""} aria-label="${esc("Check this handle: " + profileLabel(row.destination))}">Check this handle</button>` +
        `<span class="hint">${live ? "Available after this search completes." : !available ? "Unavailable: follow limit reached, already followed, or action not returned." : !paid ? "Your paid access is required." : "Starts a separate handle search with source attribution."}</span></div></article>`;
    }).join("");
    if (data.connection_trail?.length) body += `<details class="ds-connection-details"><summary>Profiles followed in this search (${data.connection_trail.length})</summary>${data.connection_trail.map((row) => `<article class="ds-evidence"><h3>${link(row.destination?.url, profileLabel(row.destination))}</h3>${connectionDetails(row)}${window.MyReconMatchChoices?.controls(row.destination?.url) || ""}</article>`).join("")}</details>`;
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
    return window.MyReconMatchChoices?.annotate(report) || report;
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
    const paid = !!(state?.user && state.account?.deep_search_enabled);
    const pending = !!(state?.user && !state.account);
    const preview = $("#dsPreview");
    if (preview) preview.hidden = paid;
    $("#dsAccess").className = "ds-access" + (paid ? " is-paid" : "");
    $("#dsAccessTitle").textContent = paid ? "Deep Search is ready" : pending ? "Checking your plan" : "Included in the ₹99 paid plan";
    $("#dsAccessNote").textContent = paid
      ? "Your paid account includes name, handle and public Google email research. Deep Search does not spend Extended scan credits."
      : pending ? "Waiting for your account details. Retry if your connection was interrupted."
      : "Public comments, indexed mentions and links declared by account owners. Includes unlimited standard scans and 10 Extended scans. No renewal.";
    $("#dsSignIn").hidden = !!state?.user;
    $("#dsUpgrade").hidden = paid || pending;
    $("#dsRetryAccess").hidden = !pending;
    $("#dsRun").disabled = running || !paid;
    document.querySelectorAll("[data-ds-follow]").forEach((button) => {
      button.disabled = running || renderedLive || !paid || !followBody(renderedReport?.connections?.[Number(button.dataset.dsFollow)]);
    });
    return paid;
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
      return `<article class="ds-evidence ds-google-profile"><h3>${googleLink(profile.url, profile.display_name || "Google contributor profile")}</h3>${window.MyReconMatchChoices?.controls(profile.url) || ""}<p class="hint">${esc(profile.evidence || "Returned by the exact-email Google lookup. Review the original source before linking identities.")}</p>${stats ? `<div class="ds-links">${stats}</div>` : ""}<div class="ds-google-coverage"><strong>${esc(coverageLabel)}</strong><p>${esc(coverageReason)}</p>${limited ? `<p class="hint">Partial collection. Returned reviews may be capped, filtered or unavailable; they are not a complete activity history.</p>` : ""}</div>${reviews.length ? `<ul class="ds-google-reviews">${reviewRows}</ul>` : `<p class="hint">No public review records were returned. This does not establish that the contributor has never reviewed a place.</p>`}<p class="hint">${esc(profile.review_source || coverage.source || profile.source || "Google public contributions")}</p></article>`;
    }).join("");
    const checks = sources.length ? `<div class="ds-source-checks">${sources.map((source) => {
      const [sourceLabel, sourceMessage] = googleSourceState(source.status, source.name);
      return `<div><span>${esc(source.name || source.provider || "Google source")}</span><span class="ds-chip">${esc(sourceLabel)}</span></div><p class="hint">${esc(sourceMessage)}</p>`;
    }).join("")}</div>` : "";
    return block("Google Maps contributor & public reviews", "Exact-email public Google research. Only public contributor data and reviews returned by the source are shown.", `<p class="ds-google-status" role="status"><span class="ds-chip">${esc(label)}</span> ${esc(message)}</p>${cards}${checks}`);
  }
  function render(data, live = false) {
    renderedReport = data; renderedLive = live;
    const activity = data.activity || [], accounts = data.accounts || [], people = data.people || [], sections = (data.sections || []).map(s => ({ ...s, hits: (s.hits || []).filter(h => safeUrl(h.url)) }));
    const pages = sections.reduce((n, s) => n + (s.hits || []).length, 0);
    const emailMode = data.mode === "email";
    const google = data.google_public_profiles || {}, googleRows = Array.isArray(google.profiles) ? google.profiles : [];
    const reviewCount = googleRows.reduce((n, profile) => n + (Array.isArray(profile.reviews) ? profile.reviews.length : 0), 0);
    const summary = emailMode ? `${googleRows.length} public Google profiles · ${reviewCount} reviews returned${live ? " so far" : ""}` : `${activity.length} public accounts · ${accounts.length + people.length} name candidates · ${pages} indexed pages`;
    const out = [`<div class="ds-summary"><div><span class="ds-chip">${emailMode ? "Email" : data.mode === "name" ? "Name" : "Handle"} search${live ? " · live" : ""}</span><h2>${esc(data.subject)}</h2>${data.context ? `<p>Context: ${esc(data.context)}</p>` : ""}</div><p>${esc(summary)}</p></div>`];
    if (emailMode || data.google_public_profiles) out.push(googleProfiles(data, live));
    if (people.length) out.push(block("Public figure records", "Wikidata candidates. Check each record's description before making a connection.", people.map((p) =>
      `<article class="ds-evidence"><h3>${link(p.url, p.name)}</h3>${window.MyReconMatchChoices?.controls(p.url) || ""}<p>${esc(p.description)}</p><div class="ds-links">${Object.entries(p.facts || {}).map(([k, v]) => `<span class="ds-chip">${esc(k)}: ${esc(v)}</span>`).join(" ")}</div><div class="ds-links">${(p.links || []).map((l) => link(l.url, l.label)).join(" ")}</div><p class="hint">${esc(p.source)} · candidate</p></article>`).join("")));
    if (accounts.length) out.push(block("Name matches", "Records carrying this name. A shared name does not confirm identity.", accounts.map((a) =>
      `<article class="ds-evidence"><h3>${link(a.url, a.platform + " · " + (a.handle || data.subject))}</h3>${window.MyReconMatchChoices?.controls(a.url) || ""}<p>${esc(a.detail)}</p><p class="hint">${esc(a.source)} · candidate</p></article>`).join("")));
    if (activity.length) out.push(block("Public accounts & recent activity", "Each account was returned by its platform. Accounts using the same handle may belong to different people.", activity.map((a) => {
      const posts = a.posts || [];
      return `<article class="ds-evidence"><h3>${link(a.url, a.platform + " · " + a.handle)}</h3>${window.MyReconMatchChoices?.controls(a.url) || ""}${a.display_name ? `<p><strong>${esc(a.display_name)}</strong></p>` : ""}<p>${esc(a.bio || "")}</p><div class="ds-links">${Object.entries(a.stats || {}).filter(([, v]) => v != null).map(([k, v]) => `<span class="ds-chip">${esc(k)}: ${esc(v)}</span>`).join(" ")}${a.since ? `<span class="ds-chip">Since ${esc(a.since)}</span>` : ""}</div><p class="hint">Source: ${esc(a.source)}</p>${posts.length ? `<ul class="ds-posts">${posts.map((p) => `<li><p>${esc(p.text)}</p><span class="hint">${esc([p.context, p.date].filter(Boolean).join(" · "))}</span> ${link(p.url, "View source")}</li>`).join("")}</ul>` : ""}${a.activity_available === false ? `<p class="hint">The account responded, but its recent activity could not be checked.</p>` : !posts.length ? `<p class="hint">No recent public posts were returned by this source.</p>` : ""}</article>`;
    }).join("")));
    if (!emailMode) out.push(linkedProfiles(data, live));
    if (data.owner_links?.length) out.push(block("Links declared by account owners", "These links were published on the source profile. They are owner statements, not independently confirmed identities.", data.owner_links.map((l) =>
      `<article class="ds-evidence">${link(l.url, l.label)} ${Array.isArray(data.connections) ? "" : aliasButton(l.alias)}<p class="hint">Published on ${esc(l.declared_on)}</p></article>`).join("")));
    if (data.identity) out.push(block("Keybase published proofs", "Proofs reported by Keybase. MyRecon has not independently revalidated the signatures.", (data.identity.proofs || []).map((p) =>
      `<article class="ds-evidence">${link(p.url, p.platform + " · " + p.handle)}${!Array.isArray(data.connections) && p.is_alias && /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/.test(p.handle) ? `<span class="ds-chip">Different handle</span><button class="btn btn-ghost btn-sm" type="button" data-ds-alias="${esc(p.handle)}">Search this handle</button>` : ""}</article>`).join("") || `<p class="hint">No public account proofs returned.</p>`));
    for (const section of sections) if (section.hits?.length) out.push(block(section.label, "Tap a result to open the original page. Previews come from search engines; a mention does not confirm ownership.", section.hits.map((h) => {
      const url = new URL(safeUrl(h.url)), host = url.hostname.replace(/^www\./, "");
      const brands = { "instagram.com": "Instagram", "reddit.com": "Reddit", "youtube.com": "YouTube", "facebook.com": "Facebook", "x.com": "X", "twitter.com": "X", "tiktok.com": "TikTok" };
      const domain = Object.keys(brands).find(d => host === d || host.endsWith("." + d));
      const platform = brands[domain] || host;
      const kind = h.profile ? "profile" : platform === "Instagram" && url.pathname.startsWith("/p/") ? "post" : platform === "Instagram" && url.pathname.startsWith("/reel/") ? "reel" : platform === "Reddit" && url.pathname.includes("/comments/") ? "discussion" : "page";
      return `<article class="ds-evidence ds-result-card"><div class="ds-result-heading"><img class="ds-platform-logo" src="https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&amp;sz=64" alt="${esc(platform)} logo" width="36" height="36" loading="lazy" referrerpolicy="no-referrer"><div><span class="hint">${esc(platform)} · ${kind}</span><h3>${esc(h.title || host)}</h3></div></div><p>${esc(h.snippet || "Open the original page to read this result.")}</p><p class="hint">Search preview · ${esc(host)}</p><div class="ds-result-action">${link(h.url, `Open ${platform} ${kind}`)}</div>${window.MyReconMatchChoices?.controls(h.url) || ""}${h.matches_context ? `<span class="ds-chip">Matches context</span>` : ""}</article>`;
    }).join("")));
    if (!live) {
      if (!emailMode && !activity.length && !accounts.length && !people.length && !pages && !data.connections?.length) out.push(`<div class="ds-panel"><p>No public results were returned. Review source availability or try again later; this does not prove that no account or record exists.</p></div>`);
      out.push(block("Sources & limits", "Unavailable sources could not be checked. An empty response is not a conclusion about a person.", `<div class="ds-source-checks">${(data.source_checks || []).map((s) => `<div><span>${esc(s.source)}</span><span class="ds-chip">${esc(emailMode ? googleSourceState(s.state, s.source)[0] : s.state === "unavailable" ? "Unavailable" : s.state === "not_found" ? "No account returned" : "Responded")}</span></div>`).join("")}</div><ul class="ds-notes">${(data.notes || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`));

    }
    $("#dsOut").innerHTML = out.join("");
  }
  function resetConsole() {
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
      lastReport = ev.data;
      linkedNotice = "";
      render(ev.data);
      $("#dsConsole").className = "ds-console done";
      $("#dsBar").style.width = "100%";
      $("#dsCount").textContent = "100%";
      $("#dsStatus").textContent = ev.data.mode === "email"
        ? `Google lookup finished: ${googleState(ev.data.google_public_profiles?.status || ev.data.status)[0].toLowerCase()}.`
        : ev.data.partial ? "Complete with source limits. Review unavailable sources below." : "Deep Search complete.";
      $("#dsExport").hidden = false;
      $("#dsExportCsv").hidden = false;
      return true;
    }
    return false;
  }
  async function run(requestBody = null) {
    if (running) return;
    await A?.ready;
    if (running) return;
    if (!A?.enabled || !renderAccess(A.state())) return;
    const input = $("#dsInput"), query = input.value.trim();
    if (!requestBody && !query) { input.focus(); return; }
    const previousReport = requestBody ? lastReport : null;
    linkedNotice = ""; stoppedByUser = false;
    running = true;
    const uid = A.state().user.uid;
    $("#dsRun").disabled = true;
    $("#dsStop").hidden = false;
    resetConsole();
    if (previousReport) {
      linkedNotice = "Checking this handle… Use Cancel to stop. Source evidence remains visible.";
      render(previousReport);
    } else {
      const emailQuery = query.includes("@") && !query.startsWith("@");
      render({ subject: query, mode: emailQuery ? "email" : undefined, connections: [], source_checks: [],
        google_public_profiles: emailQuery ? { status: "pending", profiles: [], sources: [] } : undefined }, true);
    }
    controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 100000);
    let reader, completed = false, deniedAccount = null;
    try {
      const res = await fetch(CFG.apiBase + "/api/investigate/stream", {
        method: "POST", headers: { "Content-Type": "application/json", ...(await A.authHeaders()) },
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
      const line = (s) => { if (s.trim()) completed = handleEvent(JSON.parse(s)) || completed; };
      for (;;) {
        const { done, value } = await reader.read();
        if (A.state().user?.uid !== uid) throw new Error("Your account changed. Run a new search with your current account.");
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
      const message = err.name === "AbortError" ? (stoppedByUser ? "Search cancelled. Results shown so far may be incomplete." : "Search timed out. Results shown so far may be incomplete.") : err.message;
      if (A.state().user?.uid !== uid) return;
      if (previousReport) {
        lastReport = previousReport; linkedNotice = "Handle check did not complete. The source report is shown; you can retry the check.";
        render(previousReport);
        $("#dsExport").hidden = false; $("#dsExportCsv").hidden = false;
      } else if (!completed && renderedReport?.mode === "email") {
        const status = err.name === "AbortError" ? (stoppedByUser ? "unknown" : "timeout") : "unavailable";
        render({ ...renderedReport, status, partial: true,
          google_public_profiles: { ...renderedReport.google_public_profiles, status } });
      }
      $("#dsStatus").textContent = message || "Deep Search failed.";
      $("#dsOut").insertAdjacentHTML("afterbegin", `<div class="error-box" role="alert">${esc(message)}</div>`);
    } finally {
      clearTimeout(timer);
      if (reader) await reader.cancel().catch(() => {});
      running = false;
      $("#dsOut").setAttribute?.("aria-busy", "false");
      controller = null;
      $("#dsStop").hidden = true;
      await A.refreshAccount().catch(() => {});
      renderAccess(deniedAccount ? { ...A.state(), account: deniedAccount } : A.state());
    }
  }
  document.addEventListener("DOMContentLoaded", async () => {
    initChrome(); modeHint();
    $("#dsInput")?.addEventListener("input", modeHint);
    $("#dsInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); run(); } });
    $("#dsRun")?.addEventListener("click", () => run());
    $("#dsStop")?.addEventListener("click", () => { stoppedByUser = true; controller?.abort(); });
    $("#dsSignIn")?.addEventListener("click", async () => {
      try { await A?.signIn(); await A?.refreshAccount(); renderAccess(A?.state()); }
      catch (e) { $("#dsAccessNote").textContent = A?.friendly(e) || e.message; }
    });
    $("#dsRetryAccess")?.addEventListener("click", async () => {
      try { await A?.refreshAccount(); renderAccess(A?.state()); }
      catch { $("#dsAccessNote").textContent = "Could not check your plan. Try again shortly."; }
    });
    $("#dsOut")?.addEventListener("click", (e) => {
      const follow = e.target.closest("[data-ds-follow]");
      if (follow) {
        if (follow.disabled || running || renderedLive) return;
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
      if (!lastReport) return;
      download(JSON.stringify(exportReport(lastReport), null, 2), "application/json", "json");
    });
    $("#dsExportCsv")?.addEventListener("click", () => {
      if (lastReport) download(reportCsv(exportReport(lastReport)), "text/csv;charset=utf-8", "csv");
    });
    if (A) await A.ready;
    if (!A?.enabled) {
      $("#dsAccessTitle").textContent = "Sign-in is temporarily unavailable";
      $("#dsAccessNote").textContent = "Deep Search needs your paid account. Try again shortly.";
      $("#dsSignIn").hidden = true; return;
    }
    const onState = (state) => {
      const uid = state?.user?.uid || null;
      if (activeUid && activeUid !== uid) {
        controller?.abort(); lastReport = null; renderedReport = null; linkedNotice = "";
        $("#dsOut").innerHTML = ""; $("#dsExport").hidden = true; $("#dsExportCsv").hidden = true;
      }
      activeUid = uid; renderAccess(state);
    };
    A.onChange(onState); onState(A.state());
  });
})();

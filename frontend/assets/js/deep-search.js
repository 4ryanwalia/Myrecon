/* Paid Deep Search: public records, recent activity and indexed pages. */
(function () {
  "use strict";
  const CFG = { apiBase: "", ...window.MYRECON }, A = window.MyReconAccount;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function safeUrl(raw) {
    try { const u = new URL(String(raw || "")); return ["https:", "http:"].includes(u.protocol) && !u.username ? u.href : ""; }
    catch { return ""; }
  }
  function link(url, label) {
    const href = safeUrl(url);
    return href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer nofollow">${esc(label || href)} ↗</a>` : esc(label || "Unavailable link");
  }
  let running = false, lastReport = null, activeUid = null, controller = null;

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
    $("#dsAccess").className = "ds-access" + (paid ? " is-paid" : "");
    $("#dsAccessTitle").textContent = paid ? "Deep Search is ready" : pending ? "Checking your plan" : "Included in the ₹99 paid plan";
    $("#dsAccessNote").textContent = paid
      ? "Your paid account includes name and handle research. Deep Search does not spend Extended scan credits."
      : pending ? "Waiting for your account details. Retry if your connection was interrupted."
      : "Public comments, indexed mentions and links declared by account owners. Includes unlimited standard scans and 10 Extended scans. No renewal.";
    $("#dsSignIn").hidden = !!state?.user;
    $("#dsUpgrade").hidden = paid || pending;
    $("#dsRetryAccess").hidden = !pending;
    $("#dsRun").disabled = running || !paid;
    return paid;
  }

  function modeHint() {
    const subject = $("#dsInput").value.trim().split(",")[0].trim();
    $("#dsMode").textContent = !subject ? "Enter a name or handle. Add a city, employer or topic after a comma."
      : !subject.startsWith("@") && /\s/.test(subject)
        ? "Name search: public records and pages naming this person. Matches stay candidates."
        : "Handle search: public accounts, recent activity and links published by their owners.";
  }
  const aliasButton = (h) => h && /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/.test(h) ? `<button class="btn btn-ghost btn-sm" type="button" data-ds-alias="${esc(h)}">Search ${esc(h)}</button>` : "";
  const block = (title, subtitle, body) => `<section class="ds-panel"><h2 class="ds-ptitle">${esc(title)}</h2><p class="ds-psub">${esc(subtitle)}</p>${body}</section>`;
  function render(data, live = false) {
    const activity = data.activity || [], accounts = data.accounts || [], people = data.people || [], sections = data.sections || [];
    const pages = sections.reduce((n, s) => n + (s.hits || []).length, 0);
    const out = [`<div class="ds-summary"><div><span class="ds-chip">${data.mode === "name" ? "Name" : "Handle"} search${live ? " · live" : ""}</span><h2>${esc(data.subject)}</h2>${data.context ? `<p>Context: ${esc(data.context)}</p>` : ""}</div><p>${activity.length} public accounts · ${accounts.length + people.length} name candidates · ${pages} indexed pages</p></div>`];
    if (people.length) out.push(block("Public figure records", "Wikidata candidates. Check each record's description before making a connection.", people.map((p) =>
      `<article class="ds-evidence"><h3>${link(p.url, p.name)}</h3><p>${esc(p.description)}</p><div class="ds-links">${Object.entries(p.facts || {}).map(([k, v]) => `<span class="ds-chip">${esc(k)}: ${esc(v)}</span>`).join(" ")}</div><div class="ds-links">${(p.links || []).map((l) => link(l.url, l.label)).join(" ")}</div><p class="hint">${esc(p.source)} · candidate</p></article>`).join("")));
    if (accounts.length) out.push(block("Name matches", "Records carrying this name. A shared name does not confirm identity.", accounts.map((a) =>
      `<article class="ds-evidence"><h3>${link(a.url, a.platform + " · " + (a.handle || data.subject))}</h3><p>${esc(a.detail)}</p><p class="hint">${esc(a.source)} · candidate</p></article>`).join("")));
    if (activity.length) out.push(block("Public accounts & recent activity", "Each account was returned by its platform. Accounts using the same handle may belong to different people.", activity.map((a) => {
      const posts = a.posts || [];
      return `<article class="ds-evidence"><h3>${link(a.url, a.platform + " · " + a.handle)}</h3>${a.display_name ? `<p><strong>${esc(a.display_name)}</strong></p>` : ""}<p>${esc(a.bio || "")}</p><div class="ds-links">${Object.entries(a.stats || {}).filter(([, v]) => v != null).map(([k, v]) => `<span class="ds-chip">${esc(k)}: ${esc(v)}</span>`).join(" ")}${a.since ? `<span class="ds-chip">Since ${esc(a.since)}</span>` : ""}</div><p class="hint">Source: ${esc(a.source)}</p>${posts.length ? `<ul class="ds-posts">${posts.map((p) => `<li><p>${esc(p.text)}</p><span class="hint">${esc([p.context, p.date].filter(Boolean).join(" · "))}</span> ${link(p.url, "View source")}</li>`).join("")}</ul>` : ""}${a.activity_available === false ? `<p class="hint">The account responded, but its recent activity could not be checked.</p>` : !posts.length ? `<p class="hint">No recent public posts were returned by this source.</p>` : ""}</article>`;
    }).join("")));
    if (data.owner_links?.length) out.push(block("Links declared by account owners", "These links were published on the source profile. They are owner statements, not independently confirmed identities.", data.owner_links.map((l) =>
      `<article class="ds-evidence">${link(l.url, l.label)} ${aliasButton(l.alias)}<p class="hint">Published on ${esc(l.declared_on)}${l.verified ? " · platform verified the link back" : ""}</p></article>`).join("")));
    if (data.identity) out.push(block("Keybase published proofs", "Proofs reported by Keybase. MyRecon has not independently revalidated the signatures.", (data.identity.proofs || []).map((p) =>
      `<article class="ds-evidence">${link(p.url, p.platform + " · " + p.handle)}${p.is_alias && /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/.test(p.handle) ? `<span class="ds-chip">Different handle</span><button class="btn btn-ghost btn-sm" type="button" data-ds-alias="${esc(p.handle)}">Search this handle</button>` : ""}</article>`).join("") || `<p class="hint">No public account proofs returned.</p>`));
    for (const section of sections) if (section.hits?.length) out.push(block(section.label, "Indexed pages, with the query and search provider attached. A mention is not proof of account ownership.", section.hits.map((h) =>
      `<article class="ds-evidence"><h3>${link(h.url, h.title || h.url)}</h3><p>${esc(h.snippet)}</p><div class="ds-links"><span class="ds-chip">${h.profile ? "Account page URL" : "Indexed mention"}</span>${h.matches_context ? `<span class="ds-chip">Matches context</span>` : ""}</div><p class="hint">${esc(h.engine)} · <code>${esc(h.query)}</code></p></article>`).join("")));
    if (!live) {
      if (!activity.length && !accounts.length && !people.length && !pages) out.push(`<div class="ds-panel"><p>No public results were returned. Review source availability and try the query links below; this does not prove that no account or record exists.</p></div>`);
      out.push(block("Sources & limits", "Unavailable sources could not be checked. An empty response is not a conclusion about a person.", `<div class="ds-source-checks">${(data.source_checks || []).map((s) => `<div><span>${esc(s.source)}</span><span class="ds-chip">${s.state === "unavailable" ? "Unavailable" : s.state === "not_found" ? "No account returned" : "Responded"}</span></div>`).join("")}</div><ul class="ds-notes">${(data.notes || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`));
      out.push(`<details class="ds-panel ds-plan"><summary>Continue with the search queries (${Number(data.queries_run) || 0} ran here)</summary><p class="ds-psub">Open a query to run it in Google. Browser links remain available when a provider refuses this server.</p>${(data.plan || []).map((q) => `<div class="ds-query-link"><span class="ds-chip">${q.executed ? "Ran here" : "Browser link"}</span><span>${esc(q.label)}</span>${link(q.google, q.text)}</div>`).join("")}</details>`);
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
    lastReport = null;
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
      render(ev.data);
      $("#dsConsole").className = "ds-console done";
      $("#dsBar").style.width = "100%";
      $("#dsCount").textContent = "100%";
      $("#dsStatus").textContent = ev.data.partial ? "Complete with source limits. Review unavailable sources below." : "Deep Search complete.";
      $("#dsExport").hidden = false;
      return true;
    }
    return false;
  }
  async function run() {
    if (running) return;
    await A?.ready;
    if (!A?.enabled || !renderAccess(A.state())) return;
    const input = $("#dsInput"), query = input.value.trim();
    if (!query) { input.focus(); return; }
    running = true;
    const uid = A.state().user.uid;
    $("#dsRun").disabled = true;
    $("#dsStop").hidden = false;
    resetConsole();
    controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 100000);
    let reader, completed = false, deniedAccount = null;
    try {
      const res = await fetch(CFG.apiBase + "/api/investigate/stream", {
        method: "POST", headers: { "Content-Type": "application/json", ...(await A.authHeaders()) },
        body: JSON.stringify({ query }), signal: controller.signal,
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
      const message = err.name === "AbortError" ? "Search stopped. Results shown so far may be incomplete." : err.message;
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
    $("#dsRun")?.addEventListener("click", run);
    $("#dsStop")?.addEventListener("click", () => controller?.abort());
    $("#dsSignIn")?.addEventListener("click", async () => {
      try { await A?.signIn(); await A?.refreshAccount(); renderAccess(A?.state()); }
      catch (e) { $("#dsAccessNote").textContent = A?.friendly(e) || e.message; }
    });
    $("#dsRetryAccess")?.addEventListener("click", async () => {
      try { await A?.refreshAccount(); renderAccess(A?.state()); }
      catch { $("#dsAccessNote").textContent = "Could not check your plan. Try again shortly."; }
    });
    $("#dsOut")?.addEventListener("click", (e) => {
      const b = e.target.closest("[data-ds-alias]");
      if (b && /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/.test(b.dataset.dsAlias)) {
        $("#dsInput").value = "@" + b.dataset.dsAlias;
        modeHint(); run();
        $("#dsInput").scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
    $("#dsExport")?.addEventListener("click", () => {
      if (!lastReport) return;
      const url = URL.createObjectURL(new Blob([JSON.stringify(lastReport, null, 2)], { type: "application/json" }));
      const a = document.createElement("a"); a.href = url; a.download = "myrecon-deep-search.json"; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
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
        controller?.abort(); lastReport = null;
        $("#dsOut").innerHTML = ""; $("#dsExport").hidden = true;
      }
      activeUid = uid; renderAccess(state);
    };
    A.onChange(onState); onState(A.state());
  });
})();

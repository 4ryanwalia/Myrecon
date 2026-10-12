/* Ownership assertions never replace source evidence or establish identity. */
(function () {
  "use strict";
  const labels = { mine: "Mine", not_mine: "Not mine", unsure: "Unsure" };
  const guestKey = "myrecon.match-choices.guest.v1";
  let owner, values = {}, ready = false, generation = 0, saving = false, loadError = "";
  const uid = () => window.MyReconAccount?.state()?.user?.uid || "";
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function key(raw) {
    try {
      const u = new URL(raw);
      if (!["https:", "http:"].includes(u.protocol) || u.username || u.password) return "";
      const parsed = window.MyReconProfileInput?.parse(raw);
      if (parsed?.url) return parsed.url;
      u.hash = "";
      return u.href;
    } catch { return ""; }
  }
  function choice(url) {
    if (owner !== uid() || !ready) return null;
    const row = values[key(url)];
    return row && Object.hasOwn(labels, row.choice) ? row : null;
  }
  async function request(method, body) {
    const headers = await window.MyReconAccount.authHeaders();
    const response = await fetch((window.MYRECON?.apiBase || "") + "/api/match-choices", {
      method, headers: { ...headers, "Content-Type": "application/json" },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) throw new Error("Your choices could not be saved or loaded. Please retry.");
    return (await response.json()).choices;
  }
  function index(rows) {
    return Object.fromEntries(Object.values(rows || {}).filter(r => r && key(r.url) && Object.hasOwn(labels, r.choice)).map(r => [key(r.url), r]));
  }
  async function load() {
    const current = uid(), ticket = ++generation;
    owner = current; ready = false; values = {}; saving = false; loadError = "";
    paint("Loading your choices…");
    try {
      const rows = current ? await request("GET") : JSON.parse(localStorage.getItem(guestKey) || "{}");
      if (ticket !== generation || current !== uid()) return;
      values = index(rows); ready = true; paint();
    } catch {
      if (ticket === generation) { loadError = "Choices unavailable. Reload to retry."; paint(loadError); }
    }
  }
  function controls(url) {
    url = key(url);
    if (!url) return "";
    const selected = choice(url)?.choice || "";
    return `<div class="match-choice" data-match-url="${esc(url)}"><label>Your ownership choice <select aria-label="Your ownership choice" data-match-choice${!ready || owner !== uid() ? " disabled" : ""}><option value="">Not reviewed</option>${Object.entries(labels).map(([v, text]) => `<option value="${v}"${selected === v ? " selected" : ""}>${text}</option>`).join("")}</select></label><div data-cleanup-wrap${selected === "mine" ? "" : " hidden"}><label>My cleanup record <select data-cleanup aria-label="My cleanup record">${Object.entries({review:"Review",keep:"Keep",requested:"Removal requested",completed:"Completed (recorded by me)"}).map(([v,t]) => `<option value="${v}">${t}</option>`).join("")}</select></label><p class="hint">User-recorded, not independently verified. An unavailable source does not prove deletion.</p><a href="/privacy/">Account-removal guidance</a></div><p class="hint" role="status" data-match-status>${esc(message(url))}</p></div>`;
  }
  function message(url) {
    if (loadError) return loadError;
    if (!ready || owner !== uid()) return "Loading your choices…";
    const row = choice(url);
    return `${row ? "Your choice: " + labels[row.choice] + ". " : ""}${owner ? "Choices save to your account." : "Choices save in this browser only."} A username match alone does not establish identity; your choice is self-reported.`;
  }
  function paint(error) {
    document.querySelectorAll("[data-match-url]").forEach(el => {
      const select = el.querySelector("[data-match-choice]");
      select.value = choice(el.dataset.matchUrl)?.choice || "";
      select.disabled = saving || !ready || owner !== uid();
      const cleanup = el.querySelector("[data-cleanup]");
      cleanup.value = choice(el.dataset.matchUrl)?.cleanup || "review";
      cleanup.disabled = select.disabled;
      el.querySelector("[data-cleanup-wrap]").hidden = select.value !== "mine";
      el.querySelector("[data-match-status]").textContent = error || message(el.dataset.matchUrl);
    });
    document.dispatchEvent(new Event("myrecon-choices-changed"));
  }
  function annotate(data) {
    if (Array.isArray(data)) return data.map(annotate);
    if (!data || typeof data !== "object") return data;
    const copy = Object.fromEntries(Object.entries(data).filter(([k]) => k !== "ownership_choice").map(([k, v]) => [k, annotate(v)]));
    const row = choice(data.url);
    if (row) copy.ownership_choice = { ...row, basis: "user_assertion" };
    return copy;
  }
  document.addEventListener("change", async e => {
    const select = e.target.closest?.("[data-match-choice], [data-cleanup]");
    if (!select || saving || !ready || owner !== uid()) return;
    const wrap = select.closest("[data-match-url]"), url = wrap.dataset.matchUrl, selected = select.matches("[data-cleanup]") ? choice(url)?.choice : select.value;
    const cleanup = select.matches("[data-cleanup]") ? select.value : (choice(url)?.cleanup || "review");
    const current = owner, ticket = generation;
    saving = true; paint("Saving your choice…");
    try {
      let next;
      if (current) next = index(await request("POST", { url, choice: selected, cleanup }));
      else {
        next = { ...values };
        if (selected) next[url] = { url, choice: selected, cleanup: selected === "mine" ? cleanup : "review", basis: "user_assertion", updated_at: Date.now() };
        else delete next[url];
        localStorage.setItem(guestKey, JSON.stringify(next));
      }
      if (ticket !== generation || current !== uid()) return;
      values = next; saving = false; paint();
    } catch {
      if (ticket !== generation || current !== uid()) return;
      saving = false; paint();
      wrap.querySelector("[data-match-status]").textContent = "Choice not saved. Please try again.";
    }
  });
  window.MyReconMatchChoices = { controls, annotate, choice, key, refresh: load, paint };
  const start = async () => {
    await window.MyReconAccount?.ready;
    window.MyReconAccount?.onChange(() => { if (owner !== uid()) load(); });
    load();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();

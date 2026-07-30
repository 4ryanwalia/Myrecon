/* MyRecon — Deep Search console.
 *
 * Streams /api/investigate/stream as NDJSON and renders the investigation
 * graph. Confidence and provenance travel with every element on screen: a
 * finding the backend scored `low` must never look authoritative here.
 */
(function () {
  "use strict";

  const CFG = window.MYRECON || { apiBase: "", endpoints: {} };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const THEME_KEY = "myrecon.theme";
  // --ds-* aliases, not the raw semantic tokens: the base palette's --ok/--warn
  // are tuned for the dark ground and fail contrast on white. See deep-search.css.
  const stripeFor = (band) =>
    band === "high" ? "var(--ds-ok)" : band === "medium" ? "var(--ds-warn)" : "var(--ds-mute)";

  // ---------------------------------------------------------------- chrome
  function initChrome() {
    const apply = (t) => document.documentElement.setAttribute("data-theme", t);
    const saved = localStorage.getItem(THEME_KEY);
    apply(saved || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
    $("#themeToggle")?.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      apply(next);
    });
    $("#navToggle")?.addEventListener("click", () => $("#navLinks")?.classList.toggle("open"));
  }

  // ---------------------------------------------------------------- console
  let lineCount = 0;

  function resetConsole() {
    lineCount = 0;
    const box = $("#dsConsole");
    box.hidden = false;
    box.className = "ds-console running";
    $("#dsFeed").innerHTML = "";
    $("#dsBar").style.width = "0";
    $("#dsCount").textContent = "";
    $("#dsStatus").textContent = "Starting…";
    $("#dsOut").innerHTML = "";
  }

  function pushEvent(ev) {
    const pct = Math.max(0, Math.min(100, Math.round(ev.percent || 0)));
    $("#dsBar").style.width = pct + "%";
    $("#dsStatus").textContent = ev.phase || "Working…";
    $("#dsCount").textContent = pct + "%";

    const row = document.createElement("div");
    row.className = "ds-line";
    row.innerHTML =
      `<span class="ds-state on">step</span>` +
      `<span class="ds-phase">${esc(ev.detail || ev.phase || "")}</span>` +
      `<span class="ds-pct">${pct}%</span>`;
    $("#dsFeed").prepend(row);
    lineCount++;
  }

  // ---------------------------------------------------------------- render
  function profileCard(node) {
    const a = node.attrs || {};
    const c = node.confidence || { score: 0, band: "low" };
    const plat = a.platform || node.label || "";
    const initials = plat.slice(0, 2).toUpperCase();
    const avatar = a.avatar
      ? `<img src="${esc(a.avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer"
             onerror="this.remove()">`
      : esc(initials);

    const chips = (c.factors || []).slice(0, 3).map((f) => {
      const strong = /verified|multiple/.test(f.name);
      return `<span class="ds-chip${strong ? " good" : ""}">${esc(f.name.replace(/_/g, " "))}</span>`;
    }).join("");

    return `
      <div class="ds-card" style="--stripe:${stripeFor(c.band)}">
        <div class="ds-av">${avatar}</div>
        <div class="ds-who">
          <div class="ds-plat">${esc(plat)}</div>
          <div class="ds-url"><a href="${esc(a.url || "#")}" target="_blank" rel="noopener nofollow">${esc(a.url || "")}</a></div>
          <div class="ds-why">${chips}</div>
        </div>
        <div class="ds-conf">
          <div class="ds-cval">${c.score}</div>
          <div class="ds-cband">${esc(c.band)}</div>
        </div>
      </div>`;
  }

  // Radial layout: hub centred, members on a ring. Deterministic, so the same
  // graph always draws the same way — a layout that jitters between runs makes
  // findings look unstable.
  function graphSvg(cluster, nodesById) {
    const members = cluster.members.map((id) => nodesById[id]).filter(Boolean);
    if (members.length < 2) return "";
    const hub = members.find((n) => n.type === "username") || members[0];
    const ring = members.filter((n) => n !== hub).slice(0, 14);

    const W = 320, H = 250, cx = W / 2, cy = H / 2, R = 92;
    const pts = ring.map((n, i) => {
      const ang = (2 * Math.PI * i) / ring.length - Math.PI / 2;
      return { n, x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) };
    });

    const edges = pts.map((p) =>
      `<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}"></line>`).join("");
    const dots = pts.map((p) => {
      const col = stripeFor((p.n.confidence || {}).band);
      const label = esc(((p.n.attrs || {}).platform || p.n.label || "").slice(0, 12));
      const ty = p.y < cy ? p.y - 15 : p.y + 20;
      return `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="10" fill="${col}">
                <title>${esc(p.n.label)} — ${(p.n.confidence || {}).score}/100</title></circle>
              <text x="${p.x.toFixed(1)}" y="${ty.toFixed(1)}">${label}</text>`;
    }).join("");

    return `<svg class="ds-graph" viewBox="0 0 ${W} ${H}" role="img"
              aria-label="Graph of ${ring.length} accounts linked to ${esc(hub.label)}">
        ${edges}
        <circle cx="${cx}" cy="${cy}" r="19" fill="var(--accent)"></circle>
        <text x="${cx}" y="${cy + 3}" fill="#fff">${esc(String(hub.value || "").slice(0, 11))}</text>
        ${dots}
      </svg>`;
  }

  function render(data) {
    const g = data.graph || {};
    const nodes = g.nodes || [];
    const clusters = g.clusters || [];
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const profiles = nodes.filter((n) => n.type === "social_profile");
    const a = data.assessment || {};
    const band = (a.confidence || {}).band || "low";

    const clusterBlocks = clusters.length
      ? clusters.map((c) => `
          <div class="ds-cluster">
            <div class="ds-chead2">
              <span class="ds-cname">${esc(c.label)}</span>
              <span class="ds-chip" style="color:${stripeFor(c.confidence.band)}">${c.confidence.score}/100 ${esc(c.confidence.band)}</span>
              <span class="ds-cmeta">${c.size} entities</span>
            </div>
            ${graphSvg(c, byId)}
          </div>`).join("")
      : `<p class="hint">No cluster formed — findings are unconnected.</p>`;

    $("#dsOut").innerHTML = `
      <div class="ds-split">
        <div class="ds-panel">
          <div class="ds-ptitle">Accounts found</div>
          <div class="ds-psub">${profiles.length} public account${profiles.length === 1 ? "" : "s"},
            ranked by correlation confidence. None of these is a confirmed identity.</div>
          ${profiles.length ? profiles.map(profileCard).join("")
                            : `<p class="hint">No public accounts matched.</p>`}
        </div>
        <div class="ds-panel">
          <div class="ds-ptitle">Correlation cluster</div>
          <div class="ds-psub">Accounts linked by the shared handle.</div>
          ${clusterBlocks}
        </div>
      </div>

      <div class="ds-verdict" style="--vb:${stripeFor(band)}">
        <h3>Assessment — ${esc(band)} confidence (${(a.confidence || {}).score || 0}/100)</h3>
        <p>${esc(a.text || "")}</p>
        ${(a.notes || []).length
          ? `<ul class="ds-notes">${a.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`
          : ""}
        <p class="hint" style="margin-top:10px">Summary ${esc(a.generated_by || "")}.</p>
      </div>`;
  }

  // ---------------------------------------------------------------- run
  async function run() {
    const input = $("#dsInput");
    const query = input.value.trim();
    if (!query) { input.focus(); return; }

    const btn = $("#dsRun");
    btn.disabled = true;
    resetConsole();

    try {
      const res = await fetch(CFG.apiBase + "/api/investigate/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, deep: $("#dsDeep").checked }),
      });
      if (!res.ok || !res.body) throw new Error(`Request failed (HTTP ${res.status}).`);

      // NDJSON: one JSON object per line, so hold a buffer across chunks and
      // only parse on a newline — a chunk boundary can land mid-object.
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let ev;
          try { ev = JSON.parse(line); } catch { continue; }
          if (ev.type === "progress") pushEvent(ev);
          else if (ev.type === "error") throw new Error(ev.error || "Investigation failed.");
          else if (ev.type === "complete") finish(ev.data);
        }
      }
    } catch (err) {
      const box = $("#dsConsole");
      box.className = "ds-console failed";
      $("#dsStatus").textContent = err.message || "Investigation failed.";
      $("#dsOut").innerHTML = `<div class="error-box" role="alert">${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false;
    }
  }

  function finish(data) {
    const box = $("#dsConsole");
    box.className = "ds-console done";
    $("#dsBar").style.width = "100%";
    $("#dsCount").textContent = "100%";
    const n = ((data.graph || {}).summary || {}).entities || 0;
    $("#dsStatus").textContent = `Complete — ${n} entit${n === 1 ? "y" : "ies"} for ${data.handle || ""}`;
    render(data);
  }

  document.addEventListener("DOMContentLoaded", () => {
    initChrome();
    $("#dsRun")?.addEventListener("click", run);
    $("#dsInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
    // Warn on a pasted name before the request, rather than letting the server
    // reject it — the user needs to know this takes handles, not people.
    $("#dsInput")?.addEventListener("input", (e) => {
      $("#dsMode").textContent = e.target.value.trim().includes(" ")
        ? "That looks like a name — enter a username instead"
        : "Handles only — no spaces";
    });
  });
})();

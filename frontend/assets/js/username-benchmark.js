(function () {
  "use strict";
  const labels = { myrecon: "MyRecon", sherlock: "Sherlock", maigret: "Maigret", osintsearch: "OSINTsearch" };
  const engines = ["myrecon", "sherlock", "maigret"];
  function validCase(data) {
    if (data?.schema_version !== 1 || typeof data.username !== "string" || !Array.isArray(data.results)) return false;
    return engines.every((tool) => {
      const run = data.tools?.[tool];
      if (!run || run.metadata?.status !== "measured" || !Array.isArray(run.checks)) return false;
      const s = run.summary;
      return ["checked", "reported", "unique_reported", "duplicates", "source_supported", "source_contradicted", "unverified", "unknown_predictions"]
        .every((key) => Number.isInteger(s?.[key]) && s[key] >= 0)
        && s.checked === run.checks.length
        && s.reported === run.checks.filter((c) => c.reported).length
        && s.reported === s.unique_reported + s.duplicates
        && s.unique_reported === s.source_supported + s.source_contradicted + s.unverified;
    });
  }
  function comparisonSeries(data, scope = "full") {
    return engines.map((tool) => {
      const s = data.tools[tool][scope === "shared" ? "shared_summary" : "summary"];
      return { tool, label: labels[tool], checked: s.checked, raw: s.reported, total: s.unique_reported,
        supported: s.source_supported, falsePositives: s.source_contradicted, unverified: s.unverified };
    });
  }
  if (typeof module === "object" && module.exports) module.exports = { validCase, comparisonSeries };
  if (typeof document === "undefined") return;
  const node = (tag, value) => { const n = document.createElement(tag); if (value !== undefined) n.textContent = value; return n; };
  const put = (id, value) => { document.getElementById(id).textContent = value; };
  function drawComparison(data, scope) {
    const series = comparisonSeries(data, scope), max = Math.max(1, ...series.map((s) => s.total));
    const chart = document.getElementById("usernameCaseGraph");
    const categories = [["supported", "Source-supported"], ["falsePositives", "Observed false positives"], ["unverified", "Unverified"]];
    const legend = node("div"); legend.className = "case-legend";
    categories.forEach(([key, label]) => { const item = node("span", label), swatch = node("i"); swatch.className = `case-swatch case-${key}`; swatch.setAttribute("aria-hidden", "true"); item.prepend(swatch); legend.append(item); });
    const rows = series.map((s) => {
      const row = node("div"); row.className = "case-graph-row"; row.dataset.tool = s.tool;
      const heading = node("div"); heading.className = "case-graph-label";
      heading.append(node("strong", s.label), node("small", `${s.raw} reported hits · ${s.checked.toLocaleString()} checks`));
      const plot = node("div"); plot.className = "case-graph-plot";
      const track = node("div"); track.className = "case-graph-track"; track.setAttribute("aria-hidden", "true");
      categories.forEach(([key, label]) => { const bar = node("span"); bar.className = `case-bar case-${key}`; bar.style.width = `${s[key] / max * 100}%`; bar.title = `${label}: ${s[key]}`; track.append(bar); });
      const counts = node("div"); counts.className = "case-graph-counts";
      categories.forEach(([key, label]) => { const value = node("span", `${s[key]} ${label.toLowerCase()}`); value.className = `case-count-${key}`; counts.append(value); });
      plot.append(track, counts);
      const total = node("div"); total.className = "case-graph-total"; total.append(node("strong", s.total), node("small", "unique leads"));
      row.append(heading, plot, total); return row;
    });
    chart.replaceChildren(legend, ...rows);
    const highest = [...series].sort((a, b) => b.total - a.total)[0];
    put("usernameCaseGraphNote", `${highest.label} returned the most unique leads in this view (${highest.total}). Bar lengths share one scale; they count unique profile URLs, so duplicate hits are excluded. ${scope === "shared" ? `All three tools checked the same ${data.shared_address_count} profile addresses.` : "Catalogue sizes differ. More reported leads does not mean more verified profiles."}`);
  }
  function table(headings, rows, caption) {
    const t = node("table"); t.className = "benchmark-table";
    t.append(node("caption", caption));
    const header = node("thead"), hr = node("tr");
    headings.forEach((value) => { const cell = node("th", value); cell.scope = "col"; hr.append(cell); });
    header.append(hr); t.append(header);
    const body = node("tbody");
    rows.forEach((values) => {
      const row = node("tr");
      values.forEach((value, i) => {
        const cell = node(i === 0 ? "th" : "td"); if (i === 0) cell.scope = "row";
        if (typeof value === "object") cell.append(value); else cell.textContent = String(value);
        row.append(cell);
      }); body.append(row);
    }); t.append(body); return t;
  }
  function render(data) {
    let scope = "full", filter = "all";
    put("usernameCaseHeading", `Recorded results for ${data.username}`);
    const my = data.tools.myrecon.summary, sh = data.tools.sherlock.summary, mg = data.tools.maigret.summary;
    put("usernameCaseTakeaway", `MyRecon reported ${my.reported} hits, Sherlock ${sh.reported} and Maigret ${mg.reported}. Source review found ${my.source_contradicted}, ${sh.source_contradicted} and ${mg.source_contradicted} observed false positives respectively. The graph shows what was supported, contradicted or still unverified.`);
    const recovered = (data.myrecon_before_recovery?.recovered_source_supported || [])
      .map((name) => name === "Buymeacoffee" ? "Buy Me a Coffee" : name);
    put("usernameCaseCorrection", `We fixed a RubyGems handle mismatch, added exact creator and OpenStreetMap identity checks, and tightened Reddit's API validation. The fresh full scan recovered ${recovered.length ? recovered.join(", ") : "no additional source-supported profiles"}. Blocked profiles remain unknown even when a separate review confirms existence. Earlier runs and corrections are retained in the evidence.`);
    put("usernameCaseDiagnostic", `Sherlock's unfiltered bundled rules reported ${data.sherlock_bundled_diagnostic.summary.reported} hits, including ${data.sherlock_bundled_diagnostic.excluded_reported} on sites its current exclusion list removes. The main comparison honors that list.`);
    const draw = () => {
      const shared = scope === "shared";
      drawComparison(data, scope);
      const rows = engines.map((tool) => {
        const stats = data.tools[tool][shared ? "shared_summary" : "summary"];
        return [labels[tool], stats.checked, stats.reported, stats.unique_reported, stats.source_supported,
          stats.source_contradicted, stats.unverified, stats.unknown_predictions];
      });
      const preview = data.tools.osintsearch;
      if (!shared) rows.push([labels.osintsearch + " (free preview)", `${preview.endpoints_checked} endpoints`,
        `${preview.grouped_matches} grouped / ${preview.endpoint_hits} endpoint hits`, "N/A", "N/A", "N/A",
        `${preview.named_matches} named; ${preview.hidden_matches} hidden`, "N/A"]);
      document.getElementById("usernameCaseSummary").replaceChildren(table(
        ["Tool", "Checked", "Reported hits", "Unique URLs", "Supported", "Contradicted", "Unverified", "Unknown checks"], rows,
        shared ? `${data.shared_address_count} exact profile addresses shared by the three local engines. Counts reuse the full runs; OSINTsearch hides its URLs.`
          : "Different catalogues. Reported hits include native positive verdicts; a duplicate URL counts once for source review. Supported means profile existence, not ownership."));
      let leads = data.results.filter((r) => !shared || r.shared);
      if (filter !== "all") leads = leads.filter((r) => r.reference.verdict === filter);
      const details = leads.map((r) => {
        const link = node("a", r.address.replace(/^https?:\/\//, ""));
        if (/^https?:\/\//.test(r.address)) { link.href = r.address; link.target = "_blank"; link.rel = "noopener noreferrer"; }
        const ref = r.reference;
        const verdict = ref.verdict === "found" ? "Source-supported" : ref.verdict === "not_found" ? "Source-contradicted" : "Unverified";
        const evidence = ref.note || [ref.evidence.replaceAll("_", " "), ref.title].filter(Boolean).join(" · ");
        return [link, ...engines.map((tool) => {
          const c = r.tools[tool]; return !c ? "Not checked" : c.reported ? (c.verdict === "unknown" ? "Reported hit; HTTP error" : "Reported hit") : c.verdict === "unknown" ? "Unknown" : c.verdict === "not_found" ? "No match" : "Found";
        }), verdict, evidence];
      });
      document.getElementById("usernameCaseLeads").replaceChildren(table(
        ["Source profile", "MyRecon", "Sherlock", "Maigret", "Source review", "Evidence"], details,
        `${leads.length} unique reported addresses in this view. Unverified leads are not counted as false positives.`));
    };
    document.getElementById("usernameCaseScope").onchange = (event) => { scope = event.target.value; draw(); };
    document.getElementById("usernameCaseFilter").onchange = (event) => { filter = event.target.value; draw(); };
    const preview = data.tools.osintsearch;
    put("usernameCasePreview", `OSINTsearch displayed ${preview.grouped_matches} grouped matches and ${preview.endpoint_hits} endpoint hits across ${preview.endpoints_checked} endpoints. The free preview named ${preview.named_matches} platforms and hid ${preview.hidden_matches} matches plus all profile links. Those hidden results cannot be scored.`);
    document.getElementById("usernameCaseNamed").replaceChildren(...preview.platforms.map((name) => node("li", name)));
    put("usernameCaseWhen", `Local runs: ${data.tools.myrecon.started_at_utc.slice(0, 10)}. This is a recorded case study; the daily regression sample below updates separately.`);
    draw();
  }
  async function load() {
    const target = document.getElementById("usernameCaseContent"); if (!target) return;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch("/data/username-benchmark.json", { signal: controller.signal, cache: "no-store" });
      if (!response.ok) throw new Error("Missing case study");
      const data = await response.json(); if (!validCase(data)) throw new Error("Invalid case study");
      render(data); target.hidden = false;
    } catch {
      put("usernameCaseTakeaway", "Case-study evidence is unavailable. No comparison or winner can be inferred from missing measurements.");
    } finally { clearTimeout(timeout); }
  }
  load();
}());

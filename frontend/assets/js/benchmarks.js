(function () {
  "use strict";
  const TOOLS = ["myrecon", "http200_baseline"];
  const LABELS = { myrecon: "MyRecon", http200_baseline: "HTTP 200 baseline" };
  const MODES = {
    fp: { key: "FP", title: "False positives", unit: "count" },
    accuracy: { key: "accuracy_percent", title: "Accuracy on definitive checks", unit: "%" },
    coverage: { key: "coverage_percent", title: "Definitive scored coverage", unit: "%" },
    speed: { key: "p50_seconds", title: "Median time per username", unit: "seconds" }
  };
  function graphSeries(runs, mode) {
    const key = MODES[mode].key;
    return TOOLS.map((tool) => ({ tool, values: runs.map((run) => {
      const stats = run.tools[tool];
      // An outage is a gap, never a measured zero false-positive point.
      if (mode === "fp" && stats.negative_denominator === 0) return null;
      return Number.isFinite(stats[key]) ? stats[key] : null;
    }) }));
  }
  function validRun(run) {
    if (!run || !Number.isFinite(Date.parse(run.started_at_utc)) || !Number.isFinite(Date.parse(run.finished_at_utc)) || !run.tools) return false;
    return TOOLS.every((tool) => {
      const s = run.tools[tool];
      if (!s) return false;
      const counts = ["TP", "TN", "FP", "FN", "unknown", "unscored", "unknown_negative", "total", "scored", "negative_denominator"];
      const rates = {
        false_positive_rate_percent: s.negative_denominator ? 100 * s.FP / s.negative_denominator : null,
        accuracy_percent: s.scored ? 100 * (s.TP + s.TN) / s.scored : null,
        coverage_percent: s.total ? 100 * s.scored / s.total : 0
      };
      return counts.every((key) => Number.isInteger(s[key]) && s[key] >= 0)
        && s.scored === s.TP + s.TN + s.FP + s.FN
        && s.total === s.scored + s.unknown + s.unscored
        && s.negative_denominator === s.FP + s.TN
        && s.unknown_negative <= s.unknown
        && Object.entries(rates).every(([key, expected]) => expected === null ? s[key] === null : Number.isFinite(s[key]) && Math.abs(s[key] - expected) < .011)
        && ["false_positive_rate_percent", "accuracy_percent", "coverage_percent", "p50_seconds", "p95_seconds"].every((key) => s[key] === null || (Number.isFinite(s[key]) && s[key] >= 0));
    });
  }
  // Also used by the offline scoring/graph tests.
  if (typeof module === "object" && module.exports) module.exports = { graphSeries, validRun };
  if (typeof document === "undefined") return;
  let history = [], mode = "fp", refreshTimer, inspectedRun = null;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const text = (id, value) => { document.getElementById(id).textContent = value; };
  const percent = (value) => value === null ? "Unavailable" : value.toFixed(1).replace(/\.0$/, "") + "%";
  const seconds = (value) => value === null ? "Unavailable" : value.toFixed(2) + "s";
  const stamp = (run) => run.started_at_utc.replace("T", " ").slice(0, 16) + " UTC";
  function table(headings, rows, caption) {
    const grid = el("table", undefined, "benchmark-table");
    if (caption) grid.append(el("caption", caption));
    const head = el("thead"), headRow = el("tr");
    headings.forEach((heading) => { const cell = el("th", heading); cell.scope = "col"; headRow.append(cell); });
    head.append(headRow); grid.append(head);
    const body = el("tbody");
    rows.forEach((values) => {
      const row = el("tr");
      values.forEach((value, i) => { const cell = el(i === 0 ? "th" : "td", String(value)); if (i === 0) cell.scope = "row"; row.append(cell); });
      body.append(row);
    });
    grid.append(body);
    return grid;
  }
  function svgNode(tag, attrs, content) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (content !== undefined) node.textContent = content;
    return node;
  }
  function renderGraph() {
    const runs = history.slice(-14), series = graphSeries(runs, mode), settings = MODES[mode];
    const graph = document.getElementById("benchmarkGraph");
    graph.replaceChildren();
    const picker = document.getElementById("benchmarkRunPicker");
    picker.replaceChildren(...runs.map((run, i) => {
      const option = el("option", stamp(run) + (i === runs.length - 1 ? " · latest" : ""));
      option.value = run.started_at_utc;
      return option;
    }));
    if (!runs.some((run) => run.started_at_utc === inspectedRun)) inspectedRun = runs.at(-1).started_at_utc;
    let selectedLine;
    const inspect = (i) => {
      inspectedRun = runs[i].started_at_utc;
      picker.value = inspectedRun;
      const readout = document.getElementById("benchmarkReadout");
      const date = el("span", stamp(runs[i]), "readout-date");
      readout.replaceChildren(date, ...series.map((s) => {
        const value = s.values[i];
        const formatted = value === null ? "Unavailable" : settings.unit === "%" ? percent(value) : settings.unit === "seconds" ? seconds(value) : String(value);
        const item = el("span", undefined, "readout-" + s.tool);
        item.append(el("span", LABELS[s.tool]), el("strong", formatted));
        return item;
      }));
      if (selectedLine) {
        selectedLine.setAttribute("x1", selectedLine.dataset["x" + i]);
        selectedLine.setAttribute("x2", selectedLine.dataset["x" + i]);
      }
    };
    picker.onchange = () => inspect(runs.findIndex((run) => run.started_at_utc === picker.value));
    const values = series.flatMap((s) => s.values.filter((v) => v !== null));
    if (!values.length) {
      graph.append(el("p", "No definitive measurements for this graph. Unknown checks remain excluded.", "benchmark-empty"));
    } else {
      const w = Math.max(300, Math.min(900, graph.clientWidth || 900));
      const h = w < 500 ? 260 : 300, left = 46, right = 32, top = 32, bottom = 48;
      const max = settings.unit === "%" ? 100 : Math.max(1, Math.ceil(Math.max(...values) * 1.15));
      const firstTime = Date.parse(runs[0].started_at_utc), lastTime = Date.parse(runs.at(-1).started_at_utc);
      const x = (i) => firstTime === lastTime ? (left + w - right) / 2 : left + (Date.parse(runs[i].started_at_utc) - firstTime) / (lastTime - firstTime) * (w - left - right);
      const y = (value) => h - bottom - value * (h - top - bottom) / max;
      const chart = svgNode("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": `${settings.title}: MyRecon and HTTP 200 baseline. Read exact values in the table below.` });
      chart.append(svgNode("title", {}, settings.title + " by UTC run date"));
      selectedLine = svgNode("line", { y1: top, y2: h - bottom, class: "graph-selected" });
      runs.forEach((run, i) => { selectedLine.dataset["x" + i] = String(x(i)); });
      chart.append(selectedLine);
      const ticks = mode === "fp" && max <= 4 ? Array.from({ length: max + 1 }, (_, i) => i) : Array.from({ length: 5 }, (_, i) => max * i / 4);
      ticks.forEach((tick) => {
        chart.append(svgNode("line", { x1: left, x2: w - right, y1: y(tick), y2: y(tick), class: "graph-grid" }));
        chart.append(svgNode("text", { x: left - 12, y: y(tick) + 4, "text-anchor": "end", class: "graph-axis" }, String(Number(tick.toFixed(1)))));
      });
      chart.append(svgNode("text", { x: left, y: 17, class: "graph-axis" }, settings.unit));
      const tickCount = runs.length === 1 ? 1 : w < 500 ? 3 : 5;
      for (let i = 0; i < tickCount; i++) {
        const ratio = tickCount === 1 ? .5 : i / (tickCount - 1);
        const time = new Date(firstTime + (lastTime - firstTime) * ratio).toISOString();
        const tickX = tickCount === 1 ? x(0) : left + ratio * (w - left - right);
        const label = svgNode("text", { x: tickX, y: h - 23, "text-anchor": "middle", class: "graph-axis" }, time.slice(5, 10));
        label.append(svgNode("tspan", { x: tickX, dy: 16 }, time.slice(11, 16)));
        chart.append(label);
      }
      series.forEach((s) => {
        // Start a new segment after missing data; don't bridge outage gaps.
        let path = "", previous = false;
        s.values.forEach((value, i) => {
          if (value === null) { previous = false; return; }
          path += `${previous ? "L" : "M"}${x(i)},${y(value)} `;
          previous = true;
        });
        chart.append(svgNode("path", { d: path, class: "graph-line graph-" + s.tool }));
        s.values.forEach((value, i) => {
          if (value === null) return;
          // A ring and filled dot keep coinciding zero-count series visible.
          const label = `${stamp(runs[i])}: ${LABELS[s.tool]} ${value} ${settings.unit}`;
          const point = svgNode("circle", { cx: x(i), cy: y(value), r: s.tool === "myrecon" ? 6 : 3, class: "graph-point graph-" + s.tool, tabindex: 0, role: "img", "aria-label": label });
          point.append(svgNode("title", {}, label));
          point.addEventListener("pointerenter", () => inspect(i));
          point.addEventListener("focus", () => inspect(i));
          point.addEventListener("click", () => inspect(i));
          chart.append(point);
        });
      });
      graph.append(chart);
    }
    inspect(runs.findIndex((run) => run.started_at_utc === inspectedRun));
    const rows = runs.map((run, i) => [stamp(run), ...series.map((s) => s.values[i] === null ? "Unavailable" : `${s.values[i]} ${settings.unit}`)]);
    document.getElementById("benchmarkGraphTable").replaceChildren(table(["Date (UTC)", "MyRecon", "HTTP 200 baseline"], rows));
    const scopeNote = mode === "fp" ? "Counts use each tool's definitive reference negatives. See coverage and unknowns below; the denominators can differ."
      : mode === "accuracy" ? "Accuracy excludes unknown and unscored checks. Higher accuracy with lower coverage is not an overall ranking."
      : mode === "coverage" ? "The share of all checks with a definitive prediction and a usable reference. Unknown and unscored outcomes reduce coverage."
      : "Different validation work and concurrency settings make these timings descriptive, not a fair speed ranking.";
    text("benchmarkChartNote", (runs.length === 1 ? "First run recorded. Daily history will build from the next run. " : "") + scopeNote);
  }
  function renderDetails(run) {
    const wrap = document.getElementById("benchmarkRunDetails"), summary = el("div", undefined, "benchmark-table-wrap");
    summary.append(table(["Tool", "True +", "True −", "False +", "False −", "Unknown", "Unscored", "Coverage"], TOOLS.map((tool) => {
      const s = run.tools[tool]; return [LABELS[tool], s.TP, s.TN, s.FP, s.FN, s.unknown, s.unscored, percent(s.coverage_percent)];
    }), "Unknown predictions and unavailable reference checks are excluded from scored outcomes."));
    const controls = el("div", undefined, "benchmark-table-wrap");
    const handles = [...new Set((run.checks || []).map((check) => check.username))];
    controls.append(table(["Public control", "Checked", "Reference unknown", "MyRecon false +", "MyRecon unknown"], handles.map((handle) => {
      const checks = run.checks.filter((check) => check.username === handle);
      return [handle, checks.length, checks.filter((c) => c.reference.verdict === "unknown").length,
        checks.filter((c) => c.reference.verdict === "not_found" && c.myrecon.verdict === "found").length,
        checks.filter((c) => c.myrecon.verdict === "unknown").length];
    }), "Five public accounts and five synthetic controls. Full per-platform verdicts are in the raw JSON."));
    const meta = el("p", `Run ${run.started_at_utc} to ${run.finished_at_utc}. Environment: ${run.network_environment}. Revision: ${run.version_or_commit}.`, "benchmark-run-meta");
    wrap.replaceChildren(summary, controls, meta);
  }
  function render(data) {
    if (data.schema_version !== 2 || !Array.isArray(data.runs) || !data.runs.length || !data.runs.every(validRun)) throw new Error("Invalid measurements");
    history = data.runs.slice().sort((a, b) => a.started_at_utc.localeCompare(b.started_at_utc));
    const run = history[history.length - 1], stats = run.tools.myrecon;
    text("benchmarkFP", stats.negative_denominator ? String(stats.FP) : "Unavailable");
    text("benchmarkFPRate", percent(stats.false_positive_rate_percent));
    text("benchmarkFPCoverage", `${stats.FP} / ${stats.negative_denominator} definitive negatives. ${stats.unknown_negative} negative checks unknown. A small sample, not a zero-error guarantee.`);
    text("benchmarkAccuracy", percent(stats.accuracy_percent));
    text("benchmarkCoverage", `${stats.scored} / ${stats.total} checks scored. ${stats.unknown} unknown; ${stats.unscored} without a usable reference.`);
    text("benchmarkCoverageRate", percent(stats.coverage_percent));
    text("benchmarkSpeed", seconds(stats.p50_seconds));
    text("benchmarkP95", seconds(stats.p95_seconds));
    const age = Date.now() - Date.parse(run.finished_at_utc);
    text("benchmarkSchedule", age > 30 * 3600000 ? "Update overdue: showing last successful run" : "Scheduled every 24 hours");
    document.getElementById("benchmarkSchedule").classList.toggle("benchmark-stale", age > 30 * 3600000);
    text("benchmarkUpdated", `Last run: ${run.finished_at_utc.replace("T", " ").replace("Z", " UTC")}`);
    renderGraph(); renderDetails(run);
  }
  async function load() {
    const target = document.getElementById("benchmarkContent");
    if (!target) return;
    target.setAttribute("aria-busy", "true");
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000);
    const error = document.getElementById("benchmarkError");
    try {
      const response = await fetch("/data/benchmarks.json", { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("Unavailable measurements");
      render(await response.json()); error.hidden = true; error.replaceChildren();
    } catch {
      if (history.length) {
        const stale = Date.now() - Date.parse(history[history.length - 1].finished_at_utc) > 30 * 3600000;
        text("benchmarkSchedule", stale ? "Update overdue: showing last successful run" : "Scheduled every 24 hours");
        document.getElementById("benchmarkSchedule").classList.toggle("benchmark-stale", stale);
      }
      error.hidden = false;
      error.replaceChildren(el("p", history.length ? "Latest update unavailable. Showing the last loaded measurements." : "Benchmark measurements are temporarily unavailable. You can still run a lookup or open the raw evidence."));
      const retry = el("button", "Retry measurements", "btn btn-ghost btn-sm"); retry.type = "button"; retry.addEventListener("click", load); error.append(retry);
      if (!history.length) {
        text("benchmarkUpdated", "Measurements unavailable");
        document.getElementById("benchmarkGraph").replaceChildren(el("p", "No measurements loaded. No zero-error result is implied.", "benchmark-empty"));
      }
    } finally { clearTimeout(timeout); target.removeAttribute("aria-busy"); }
  }
  document.addEventListener("DOMContentLoaded", () => {
    if (!document.getElementById("benchmarkContent")) return;
    document.querySelectorAll("[data-benchmark-chart]").forEach((button) => button.addEventListener("click", () => {
      mode = button.dataset.benchmarkChart;
      document.querySelectorAll("[data-benchmark-chart]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      if (history.length) renderGraph();
    }));
    load();
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => { if (history.length) renderGraph(); }, 150);
    });
    // Keep long-open tabs current without repeatedly probing any platform.
    refreshTimer = setInterval(load, 15 * 60 * 1000);
    window.addEventListener("pagehide", () => clearInterval(refreshTimer), { once: true });
  });
})();

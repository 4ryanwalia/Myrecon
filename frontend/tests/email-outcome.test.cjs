const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const outcome = require("../assets/js/email-outcome.js");

const checked = { status: "ok", checked: true, breached: false };
const unavailable = { status: "unavailable", checked: false, error: "Source unreachable" };
function report(primary = checked, analytics = checked) {
  return { query: { email: "fixture@example.com" }, analysis: {},
    breaches: primary, darkweb: analytics, fallback: { status: "skipped" },
    summary: { breached: false, breach_count: 0 } };
}

test("only completed source checks permit no_match", () => {
  const r = outcome(report());
  assert.equal(r.state, "no_match");
  assert.equal(r.completed, 2);
  assert.equal(r.attempted, 2);
  assert.equal(r.partial, false);
});

test("partial and total outages cannot become clean results", () => {
  assert.equal(outcome(report(checked, unavailable)).state, "incomplete");
  assert.equal(outcome(report(unavailable, unavailable)).state, "unavailable");
  assert.equal(outcome({ summary: { breached: false } }).state, "unavailable");
});

test("a positive finding survives partial coverage", () => {
  const r = outcome(report({ ...checked, breached: true }, unavailable));
  assert.equal(r.state, "found");
  assert.equal(r.partial, true);
  assert.equal(r.found, true);
});

test("legacy aggregate failures and contradictory checked flags remain incomplete", () => {
  const old = report();
  old.summary.breach_status = "partial_rate_limited";
  assert.equal(outcome(old).state, "incomplete");
  assert.equal(outcome(report({ ...checked, checked: false })).state, "incomplete");
  assert.equal(outcome(report({ ...checked, error: "Broken response" })).state, "incomplete");
});

test("backend coverage excludes skipped fallback and respects unavailable sources", () => {
  const data = report();
  data.summary.breach_coverage = { sources: [
    { name: "LeakCheck", ...checked }, { name: "Analytics", ...unavailable },
    { name: "Fallback", status: "skipped", checked: false },
  ] };
  const r = outcome(data);
  assert.equal(r.state, "incomplete");
  assert.equal(r.completed, 1);
  assert.equal(r.attempted, 2);
});

// Exercise the shipped renderer and export paths in a tiny DOM without running
// page startup or any network requests. The test-only adapter is injected here.
function browser() {
  const results = { innerHTML: "" };
  const context = {
    window: { MYRECON: { endpoints: {} }, MyReconEmailOutcome: outcome, matchMedia: () => ({ matches: true }) }, URL,
    location: { href: "https://myrecon.xyz/" },
    document: { addEventListener() {}, querySelector: () => results, querySelectorAll: () => [] },
  };
  const source = fs.readFileSync(path.join(__dirname, "../assets/js/app.js"), "utf8")
    .replace(/\}\)\(\);\s*$/, "globalThis.adapter = { renderEmail, buildTextSummary, quickStat, toCSV, exportData };})();");
  vm.runInNewContext(source, context);
  return { api: context.adapter, results };
}

for (const [name, data, label] of [
  ["partial", report(checked, unavailable), "Breach check incomplete"],
  ["unavailable", report(unavailable, unavailable), "Breach check unavailable"],
]) {
  test(`${name} UI, saved notes, copied text and exports preserve the gap`, () => {
    const { api, results } = browser();
    const res = { tool: "email", query: "fixture@example.com", data };
    api.renderEmail(data);
    assert.ok(results.innerHTML.includes(label));
    assert.ok(results.innerHTML.includes('data-action="retry-email"'));
    assert.ok(!results.innerHTML.includes('class="breach clean'));
    assert.ok(!results.innerHTML.includes('class="exposure"'));
    assert.equal(api.quickStat(res), label);
    assert.ok(api.buildTextSummary(res).includes(label));
    assert.ok(api.buildTextSummary(res).includes("Exposure score: unavailable"));
    assert.equal(api.exportData(res).summary.coverage_incomplete, true);
    assert.ok(api.toCSV(res).includes('"summary.coverage_incomplete","true"'));
  });
}

test("completed negatives show scoped no-match language", () => {
  const { api, results } = browser();
  api.renderEmail(report());
  assert.ok(results.innerHTML.includes("No match in checked sources"));
  assert.ok(!results.innerHTML.includes("No breaches found"));
  assert.ok(!results.innerHTML.includes('data-action="retry-email"'));
});

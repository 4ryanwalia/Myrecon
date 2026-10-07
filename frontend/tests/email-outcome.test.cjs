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
    .replace(/\}\)\(\);\s*$/, "globalThis.adapter = { renderEmail, emailBreachRows, linkedServices, buildTextSummary, quickStat, toCSV, exportData };})();");
  vm.runInNewContext(source, context);
  return { api: context.adapter, results };
}

test("breach names from every source stay visible above advice and merge duplicates", () => {
  const data = report({ ...checked, breached: true, sources: [{ name: "Canva.com", date: "2019" }, { name: "Adobe", date: "2013" }] });
  data.darkweb = { ...checked, breaches: [{ name: "Canva", date: "2019", exposed: ["Passwords"] }] };
  data.fallback = { status: "ok", source: "Fallback", sources: [{ name: "Dropbox" }] };
  data.summary = { breached: true, breach_count: 3 };
  const { api, results } = browser();
  assert.equal(api.emailBreachRows(data).length, 3);
  api.renderEmail(data);
  assert.match(results.innerHTML, /Which breaches included this email/);
  assert.match(results.innerHTML, /Date not provided/);
  assert.match(results.innerHTML, /Per-breach data types not provided/);
  assert.ok(results.innerHTML.indexOf("Which breaches included") < results.innerHTML.indexOf("What to do"));
  assert.match(api.buildTextSummary({ tool: "email", query: "fixture@example.com", data }), /Dropbox/);
});

test("account checks show off and unavailable states without relabeling historical breaches", () => {
  const { api } = browser();
  const ls = { services: [{ service: "Adobe", kind: "breach", evidence: "Historical breach" }] };
  assert.match(api.linkedServices(ls, { enabled: false }), /Live account checks are off/);
  const html = api.linkedServices(ls, { enabled: true, sources: [{ name: "GitHub", status: "rate_limited" }] });
  assert.match(html, /rate limited/);
  assert.match(html, /svc-name[^>]*>Adobe/);
  assert.match(html, /historical breach/);
});

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

test("historical aliases merge into breach cards and preserve Pro source coverage", () => {
  const data = report();
  data.breach_details = { status: "partial", checked: false, breached: true, records: [{ name: "Example incident", date: "2019-04", username: "<old-handle>", full_name: "Example Person", password_exposed: true, source: "LeakCheck Pro" }] };
  const { api, results } = browser();
  api.renderEmail(data);
  assert.equal(outcome(data).found, true);
  assert.equal(outcome(data).partial, true);
  assert.match(results.innerHTML, /&lt;old-handle&gt;/);
  assert.match(results.innerHTML, /Exposure reported/);
  assert.match(results.innerHTML, /LeakCheck Pro/);
  assert.doesNotMatch(results.innerHTML, /Email infrastructure|SMTP verification|MX hosts by priority/);
});

test("a failed profile source cannot produce a complete exposure score", () => {
  const data = { ...report(), partial: true, profile_enrichment: { status: 'unavailable' } };
  const { api, results } = browser();
  api.renderEmail(data);
  assert.doesNotMatch(results.innerHTML, /class="exposure"/);
  assert.match(results.innerHTML, /profile-source coverage is incomplete/);
  const res = { tool: 'email', query: 'fixture@example.com', data };
  assert.doesNotMatch(api.buildTextSummary(res), /Exposure score: \d+/);
  assert.equal(api.exportData(res).summary.coverage_incomplete, true);
});

test("merged breach cards prefer compatible precise dates", () => {
  const data = report({ ...checked, sources: [{ name: 'Canva.com', date: '2019-05' }] });
  data.darkweb = { ...checked, breaches: [{ name: 'Canva', date: '2019' }] };
  assert.equal(browser().api.emailBreachRows(data)[0].date, '2019-05');
});

test("shared photo URLs render once in the gallery without merging distinct accounts", () => {
  const data = report();
  data.evidence_report = { profiles: [{ platform: 'Google', avatar_url: 'https://lh3.googleusercontent.com/example', stats: {} }, { platform: 'LinkedIn', avatar_url: 'https://lh3.googleusercontent.com/example', stats: {} }] };
  const { api, results } = browser();
  api.renderEmail(data);
  assert.equal((results.innerHTML.match(/<figure>/g) || []).length, 1);
  assert.match(results.innerHTML, /Google · LinkedIn<\/figcaption>/);
  assert.equal((results.innerHTML.match(/card email-profile-card/g) || []).length, 2);
  assert.doesNotMatch(results.innerHTML, /onerror=/);
});

test("timeline keeps source date evidence and moves repeated breach prose out of rows", () => {
  const data = report();
  data.evidence_report = { timeline: [{ kind: 'breach', title: 'Example breach', date: '2019-05', date_label: 'May 2019', precision: 'month', sources: ['One', 'Two'], detail: 'Most precise reported breach date; source dates are retained.', date_evidence: [{ date_label: '2019', sources: ['One'] }, { date_label: 'May 2019', sources: ['Two'] }] }] };
  const { api, results } = browser();
  api.renderEmail(data);
  assert.match(results.innerHTML, /Reported dates/);
  assert.doesNotMatch(results.innerHTML, /Most precise reported breach date/);
  assert.match(results.innerHTML, /May 2019 · Two/);
});

test("registration coverage exposes Spotify signals and unknown services separately", () => {
  const { api } = browser();
  const data = { status: "ok", checked: 1, attempted: 111, catalogue_count: 123, services: [
    { service: "Spotify", status: "found", reason: "Registration signal" },
    { service: "Instagram", status: "rate_limited", reason: "Provider blocked" },
    { service: "<unsafe>", status: "timeout", reason: "Timed out" }] };
  const html = api.linkedServices({ services: [{ service: "Spotify", kind: "registration", evidence: "Registration signal" }] }, { enabled: true }, data);
  assert.match(html, /1 answered of 111 eligible/);
  assert.match(html, /123 service checks/);
  assert.match(html, /Blocked or rate limited/);
  assert.match(html, /&lt;unsafe&gt;/);
  assert.doesNotMatch(html, /<unsafe>/);
});

test("selected services stay registration evidence in coverage summaries and exports", () => {
  const { api } = browser();
  const data = {
    registration_checks: { status: "ok", checked: 1, attempted: 2, catalogue_count: 125, services: [
      { service: "Hugging Face", domain: "huggingface.co", engine: "MyRecon selected checks", status: "found", reason: "Registration signal; ownership unverified" },
      { service: "HackerRank", domain: "hackerrank.com", engine: "MyRecon selected checks", status: "unavailable", reason: "Unknown response" }] },
    account_checks: { enabled: true },
    linked_services: { services: [{ service: "Hugging Face", kind: "registration", evidence: "Registration signal" }] },
  };
  const html = api.linkedServices(data.linked_services, data.account_checks, data.registration_checks);
  assert.match(html, /Hugging Face/);
  assert.match(html, /HackerRank/);
  assert.match(html, /MyRecon selected checks/);
  assert.match(html, /Unavailable/);
  const exported = api.buildTextSummary({ tool: "email", query: "fixture@example.com", data });
  assert.match(exported, /Hugging Face \(MyRecon selected checks\): found/);
  assert.match(exported, /HackerRank \(MyRecon selected checks\): unavailable/);
  const summary = outcome.platforms(data);
  assert.equal(summary.registrationSignals, 1);
  assert.equal(summary.publicProfiles, 0);
  assert.equal(api.exportData({ tool: "email", data }).registration_checks.services.length, 2);
});

test("evidence summary, dated timeline and profile details preserve attribution in exports", () => {
  const data = report();
  data.evidence_report = { counts: { public_profiles: 1, registration_signals: 2, historical_services: 3, named_breaches: 4 },
    identity: { display_name: [{ value: '<untrusted name>', source: 'GitHub', basis: 'historical_commit' }], username: [], location: [] },
    earliest: { date_label: '2019' }, latest: { date_label: 'Jan 1, 2020' },
    date_note: 'Range of returned evidence only.', identity_note: 'Self-reported fields do not establish ownership.',
    timeline: [{ date: '2019', date_label: '2019', precision: 'year', kind: 'breach', title: 'Canva breach', sources: ['LeakCheck'], detail: 'Breach date, not email creation.', url: '' }],
    undated_events: [{ date: '', date_label: 'Date not provided', precision: 'unknown', kind: 'breach', title: 'Undated breach', sources: ['Fallback'], detail: 'Date unknown.' }],
    profiles: [{ platform: 'GitHub', username: 'dev', basis: 'historical_commit', source: 'GitHub API', profile_status: 'rate_limited', url: 'javascript:alert(1)', website: 'javascript:alert(2)', bio: '<script>bad()</script>', stats: { Followers: 0 } }] };
  const { api, results } = browser();
  api.renderEmail(data);
  assert.match(results.innerHTML, /Earliest dated evidence/);
  assert.match(results.innerHTML, /year only/);
  assert.match(results.innerHTML, /1 undated findings/);
  assert.match(results.innerHTML, /Historical commit association/);
  assert.match(results.innerHTML, /&lt;untrusted name&gt;/);
  assert.doesNotMatch(results.innerHTML, /javascript:|<script>bad/);
  assert.ok(results.innerHTML.indexOf('Activity timeline') < results.innerHTML.indexOf('What this does'));
  const res = { tool: 'email', query: 'fixture@example.com', data };
  assert.match(api.buildTextSummary(res), /2019: Canva breach; source: LeakCheck/);
  assert.match(api.buildTextSummary(res), /Range of returned evidence only/);
  assert.equal(api.exportData(res).evidence_report.profiles[0].profile_status, 'rate_limited');
  assert.match(api.toCSV(res), /evidence_report.timeline\[0\].precision/);
});

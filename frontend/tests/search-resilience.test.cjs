const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const script = (file) => fs.readFileSync(path.join(__dirname, "../assets/js", file), "utf8");

function partial() {
  const context = { window: {} };
  vm.runInNewContext(script("partial-results.js"), context);
  return context.window.MyReconPartial;
}

test("source failure notices stay specific, deduplicate errors and escape provider text", () => {
  const html = partial().notice({ partial: true, errors: [
    { source: "LeakCheck", code: "unavailable" },
    { source: "google_dork", message: "<script>unsafe</script>" },
    { source: "google_dork", message: "<script>unsafe</script>" },
  ] });
  assert.match(html, /LeakCheck API currently unreachable, displaying other results/);
  assert.match(html, /Unavailable checks do not mean no match/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.equal(html.split("unsafe").length - 1, 1);
  assert.equal(partial().notice({ partial: false, errors: [] }), "");
});

function appRenderer() {
  const results = { innerHTML: "", querySelectorAll: () => [] };
  const context = { window: { MYRECON: { endpoints: {} }, MyReconPartial: partial(), matchMedia: () => ({ matches: true }) }, URL,
    location: { href: "https://myrecon.xyz/" },
    document: { addEventListener() {}, querySelector: (s) => s === "#results" ? results : null, querySelectorAll: () => [] } };
  vm.runInNewContext(script("app.js").replace(/\}\)\(\);\s*$/,
    "globalThis.adapter = { renderUsername, renderSafely, buildTextSummary };})();"), context);
  return { results, api: context.adapter };
}

test("username results keep completed profiles beside an outage warning and in copied reports", () => {
  const { api, results } = appRenderer();
  const data = { query: { username: "fixture" }, summary: { total: 1, profiles: 1 },
    results: { profiles: [{ platform: "Fixture", url: "https://example.com/fixture", confidence: "high" }] },
    partial: true, errors: [{ source: "google_dork", message: "Google web search unavailable" }] };
  api.renderUsername(data);
  assert.match(results.innerHTML, /Search partially completed/);
  assert.match(results.innerHTML, /https:\/\/example.com\/fixture/);
  assert.match(api.buildTextSummary({ tool: "username", query: "fixture", data }), /Google web search unavailable/);
});

test("a malformed result view offers recovery and JSON download", () => {
  const { api, results } = appRenderer();
  api.renderSafely(() => { throw new Error("render failure"); }, {});
  assert.match(results.innerHTML, /could not be displayed/);
  assert.match(results.innerHTML, /data-export="json"/);
});

test("guest report keeps two card details, locked placeholders and an honest copied preview", () => {
  const { api, results } = appRenderer();
  const data = { query: { username: "guest-fixture", scope: "standard", deep: true },
    summary: { total: 5, profiles: 5, checked: 100 },
    results: { profiles: [
      { platform: "First", url: "https://first.example/fixture", confidence: "high" },
      { platform: "Second", url: "https://second.example/fixture", confidence: "high" },
    ] }, guest_preview: { visible_cards: 2, hidden_cards: 3, requires_sign_in: true } };
  api.renderUsername(data);
  assert.equal((results.innerHTML.match(/>Open profile /g) || []).length, 2);
  assert.equal((results.innerHTML.match(/class="card card-locked"/g) || []).length, 3);
  assert.match(results.innerHTML, /Only the first 2 result cards are visible/);
  assert.match(results.innerHTML, /https:\/\/first.example/);
  assert.match(results.innerHTML, /https:\/\/second.example/);
  const copied = api.buildTextSummary({ tool: "username", query: "guest-fixture", data });
  assert.match(copied, /2 card details visible; 3 cards locked/);
  assert.doesNotMatch(copied, /Digital exposure score/);
});

test("Deep Search source links reject script URLs and escape provider content", () => {
  const context = { window: { MYRECON: {} }, URL,
    location: { href: "https://myrecon.xyz/deep-search.html" },
    document: { addEventListener() {}, querySelector() { return null; } } };
  vm.runInNewContext(script("deep-search.js").replace(/\}\)\(\);\s*$/,
    "globalThis.adapter = { link };})();"), context);
  const html = context.adapter.link("javascript:alert(1)", '<img src=x onerror="alert(2)">');
  assert.doesNotMatch(html, /(?:href|src)="javascript:/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});

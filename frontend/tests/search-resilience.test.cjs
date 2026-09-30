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

test("Deep Search profile rendering can access the URL validator and rejects script URLs", () => {
  const context = { window: { MYRECON: {} }, URL,
    location: { href: "https://myrecon.xyz/deep-search.html" },
    document: { addEventListener() {} } };
  vm.runInNewContext(script("deep-search.js").replace(/\}\)\(\);\s*$/,
    "globalThis.adapter = { profileCard };})();"), context);
  const html = context.adapter.profileCard({ attrs: { platform: "Fixture", url: "javascript:alert(1)", avatar: "javascript:alert(2)" } });
  assert.doesNotMatch(html, /(?:href|src)="javascript:/);
  assert.match(html, /href="#"/);
});

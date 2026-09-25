const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");


function renderer() {
  const context = {
    window: { MYRECON: { endpoints: {} }, matchMedia: () => ({ matches: true }) },
    URL,
    location: { href: "https://myrecon.xyz/" },
    document: { addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] },
  };
  const source = fs.readFileSync(path.join(__dirname, "../assets/js/app.js"), "utf8")
    .replace(/\}\)\(\);\s*$/, "globalThis.adapter = { platformChecksPanel };})();");
  vm.runInNewContext(source, context);
  return context.adapter;
}


test("platform-check panel states every actual outcome without treating uncertainty as absence", () => {
  const html = renderer().platformChecksPanel([
    { platform: "Confirmed", url: "https://example.com/a", verdict: "found", reason: "API confirmed" },
    { platform: "Weak evidence", url: "https://example.com/b", verdict: "possible", reason: "Weak profile signals" },
    { platform: "Absent", url: "https://example.com/c", verdict: "not_found", reason: "404" },
    { platform: "Blocked", url: "javascript:alert(1)", verdict: "unknown", unreachable: true, reason: "Blocked" },
  ], 4, "@octocat");

  assert.match(html, /4 platforms checked for @octocat/);
  assert.match(html, /Profile found/);
  assert.match(html, /Possible/);
  assert.match(html, /No match/);
  assert.match(html, /Unavailable/);
  assert.match(html, /href="\/data\/platforms\.json"/);
  assert.match(html, /Download the current platform catalogue/);
  assert.doesNotMatch(html, /javascript:/);
});

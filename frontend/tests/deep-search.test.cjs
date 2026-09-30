const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

function load(state = {}) {
  const elements = {};
  for (const id of ["dsAccess", "dsAccessTitle", "dsAccessNote", "dsSignIn", "dsUpgrade", "dsRetryAccess", "dsRun", "dsInput", "dsMode", "dsOut", "dsConsole", "dsBar", "dsCount", "dsStatus", "dsExport", "dsStop"]) {
    elements["#" + id] = { textContent: "", innerHTML: "", style: {}, value: "", focus() {},
      insertAdjacentHTML(position, html) { this.innerHTML = html + this.innerHTML; } };
  }
  const context = { URL, TextDecoder, AbortController, setTimeout, clearTimeout,
    document: { querySelector: (s) => elements[s], addEventListener() {} },
    window: { MYRECON: {}, MyReconAccount: { enabled: true, ready: Promise.resolve(), state: () => state,
      authHeaders: async () => ({ Authorization: "Bearer signed-token" }), refreshAccount: async () => {} } } };
  const script = fs.readFileSync(path.join(__dirname, "../assets/js/deep-search.js"), "utf8");
  vm.runInNewContext(script.replace(/\}\)\(\);\s*$/, "globalThis.adapter = { renderAccess, render, modeHint, handleEvent, run };})();"), context);
  return { elements, api: context.adapter, context };
}

test("guest, free and pending accounts cannot run Deep Search", async () => {
  for (const state of [{}, { user: { uid: "u" }, account: { deep_search_enabled: false } }, { user: { uid: "u" } }]) {
    const { api, elements, context } = load(state);
    assert.equal(api.renderAccess(state), false);
    assert.equal(elements["#dsRun"].disabled, true);
    context.fetch = () => { throw new Error("unpaid request must not run"); };
    await api.run();
  }
});

test("spent pack retains paid access and name mode ignores context whitespace", () => {
  const state = { user: { uid: "u" }, account: { deep_search_enabled: true, extended_scans_left: 0 } };
  const { api, elements } = load(state);
  assert.equal(api.renderAccess(state), true);
  assert.equal(elements["#dsRun"].disabled, false);
  assert.equal(elements["#dsUpgrade"].hidden, true);
  assert.match(elements["#dsAccessNote"].textContent, /does not spend Extended/);
  elements["#dsInput"].value = "@torvalds, Linux kernel";
  api.modeHint();
  assert.match(elements["#dsMode"].textContent, /Handle search/);
  elements["#dsInput"].value = "Satya Nadella, Microsoft";
  api.modeHint();
  assert.match(elements["#dsMode"].textContent, /Name search/);
});

test("split NDJSON sends auth and displays partial source evidence", async () => {
  const state = { user: { uid: "u" }, account: { deep_search_enabled: true } };
  const { api, elements, context } = load(state);
  elements["#dsInput"].value = "octocat";
  const data = { status: "ok", mode: "handle", subject: "octocat", activity: [], source_checks: [{ source: "Reddit", state: "unavailable" }], notes: ["A source could not be checked."], partial: true };
  const text = JSON.stringify({ type: "partial", data }) + "\n" + JSON.stringify({ type: "complete", data });
  const bytes = new TextEncoder().encode(text);
  const chunks = [bytes.slice(0, 13), bytes.slice(13, 61), bytes.slice(61)];
  let called = false;
  context.fetch = async (url, options) => {
    called = true;
    assert.equal(options.headers.Authorization, "Bearer signed-token");
    assert.equal(url, "/api/investigate/stream");
    return { ok: true, body: { getReader: () => ({ read: async () => chunks.length ? { value: chunks.shift(), done: false } : { done: true }, cancel: async () => {} }) } };
  };
  await api.run();
  assert.equal(called, true);
  assert.match(elements["#dsOut"].innerHTML, /Unavailable/);
  assert.match(elements["#dsStatus"].textContent, /source limits/);
  assert.equal(elements["#dsExport"].hidden, false);
  assert.equal(elements["#dsRun"].disabled, false);
});

test("server rejection removes paid access and incomplete streams stay incomplete", async () => {
  const state = { user: { uid: "u" }, account: { deep_search_enabled: true } };
  const rejected = load(state);
  rejected.elements["#dsInput"].value = "octocat";
  rejected.context.fetch = async () => ({ ok: false, json: async () => ({ error: "Paid plan required", account: { deep_search_enabled: false } }) });
  await rejected.api.run();
  assert.equal(rejected.elements["#dsRun"].disabled, true);
  assert.equal(rejected.elements["#dsUpgrade"].hidden, false);
  const interrupted = load(state);
  interrupted.elements["#dsInput"].value = "octocat";
  interrupted.context.fetch = async () => ({ ok: true, body: { getReader: () => ({ read: async () => ({ done: true }), cancel: async () => {} }) } });
  await interrupted.api.run();
  assert.match(interrupted.elements["#dsStatus"].textContent, /ended before completion/);
  assert.equal(interrupted.elements["#dsExport"].hidden, true);
});

test("result groups preserve provenance, candidate status and safe links", () => {
  const { api, elements } = load();
  api.render({ subject: "<script>", mode: "name", people: [{ name: "<img>", description: "Candidate", url: "javascript:evil", links: [] }],
    accounts: [{ platform: "GitHub", handle: "candidate", detail: "Same name", source: "Registry", url: "https://github.com/candidate" }],
    owner_links: [{ label: "Owner link", url: "https://example.com", declared_on: "GitHub · candidate" }], sections: [] });
  const html = elements["#dsOut"].innerHTML;
  assert.match(html, /candidate/);
  assert.match(html, /Published on GitHub/);
  assert.doesNotMatch(html, /<script>|<img>|href="javascript:/);
});

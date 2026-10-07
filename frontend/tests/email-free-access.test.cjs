const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const outcome = require("../assets/js/email-outcome.js");
const script = (name) => fs.readFileSync(path.join(__dirname, "../assets/js", name), "utf8");

function fixture() {
  const checked = { status: "ok", checked: true, breached: true };
  return {
    status: "ok", query: { email: "fixture@example.com" }, analysis: {},
    breaches: { ...checked, sources: [{ name: "Canva", date: "2019" }, { name: "Adobe", date: "2013" }, { name: "Dropbox", date: "2012" }] },
    darkweb: { ...checked, breaches: [] }, fallback: { status: "skipped" },
    summary: { breached: true, breach_count: 3 },
    evidence_report: {
      counts: { public_profiles: 3, registration_signals: 1, historical_services: 3, named_breaches: 3 },
      identity: {}, timeline: [],
      profiles: ["GitHub", "Gravatar", "Google"].map(platform => ({ platform, display_name: platform + " fixture", url: "https://example.com/" + platform,
        source: "Fixture public source", evidence: "Returned exact email evidence", basis: "public_email", stats: {} })),
      registrations: [{ service: "Spotify", source: "Fixture registration source", reason: "Returned registration signal" }],
    },
    account_checks: { enabled: true, sources: [{ name: "Fixture account source", status: "ok" }] },
    profile_enrichment: { status: "ok", sources: [{ name: "Fixture public source", status: "ok", returned: 3 }] },
  };
}

function app(initialState = { user: null }, options = {}) {
  let state = initialState;
  let authCalls = 0;
  const requests = [];
  const results = { innerHTML: "", querySelectorAll: () => [] };
  const input = { value: "fixture@example.com", focus() {} };
  const runButton = { disabled: false };
  const account = {
    state: () => state,
    authHeaders: () => {
      authCalls++;
      return options.auth ? options.auth() : Promise.resolve({ Authorization: "Bearer fixture-token" });
    },
    refreshAccount: async () => {},
    get ready() {
      if (options.waiting) throw new Error("Email lookup read account readiness");
      return Promise.resolve();
    },
  };
  const context = {
    URL, AbortController, setTimeout, clearTimeout,
    location: { href: "https://myrecon.xyz/" },
    window: { MYRECON: { apiBase: "https://api.example.com", endpoints: { email: "/api/email", username: "/api/username" } },
      MyReconEmailOutcome: outcome, MyReconAccount: account, matchMedia: () => ({ matches: true }) },
    document: {
      addEventListener() {}, querySelectorAll: () => [],
      body: { classList: { contains: () => false, add() {} } },
      querySelector: (s) => ({ "#results": results, "#queryInput": input, "#runBtn": runButton, "#linkedAccountsToggle": { checked: true } })[s] || null,
    },
    fetch: async (url, init) => {
      requests.push({ url, init });
      if (options.onFetch) await options.onFetch();
      return { ok: true, json: async () => fixture() };
    },
  };
  const source = script("app.js").replace(/\}\)\(\);\s*$/,
    `globalThis.adapter = { api, run, renderEmail, renderSafely, rememberGuestReport, accountChanged, lockedResults,
      setTool: tool => { activeTool = tool; },
      result: () => lastResult,
      show: (tool, data) => { activeTool = tool; lastResult = { tool, query: "fixture@example.com", data }; rememberGuestReport(tool, lastResult.query, data); renderSafely(RENDERERS[tool], data); },
      seedAccountReport: () => { activeTool = "username"; lastResult = { tool: "username", data: {} }; resultUid = stateUidForTest(); },
    }; function stateUidForTest() { return window.MyReconAccount.state().user.uid; }})();`);
  vm.runInNewContext(source, context);
  return { api: context.adapter, requests, results, runButton, authCalls: () => authCalls, change: (next) => { state = next; context.adapter.accountChanged(next); } };
}

for (const [name, state] of [
  ["guest", { user: null }],
  ["signed-in free", { user: { uid: "free" }, account: { standard_scans_left: 0, standard_scans_unlimited: false } }],
  ["paid", { user: { uid: "paid" }, account: { standard_scans_unlimited: true } }],
]) {
  test(`${name} email lookup renders every finding and source detail without authorization`, async () => {
    const browser = app(state);
    browser.api.setTool("email");
    await browser.api.run();
    assert.equal(browser.requests.length, 1);
    assert.equal(browser.requests[0].init.headers.Authorization, undefined);
    assert.equal(browser.authCalls(), 0);
    assert.equal((browser.results.innerHTML.match(/card email-profile-card/g) || []).length, 3);
    for (const finding of ["Canva", "Adobe", "Dropbox", "Spotify", "Fixture public source", "Returned exact email evidence"]) assert.ok(browser.results.innerHTML.includes(finding), finding);
    assert.doesNotMatch(browser.results.innerHTML, /guest-results-overlay|Sign in to view|data-gate=/);
    assert.equal(browser.api.lockedResults(), false);
    assert.equal(browser.runButton.disabled, false);
  });
}

test("email lookup bypasses pending account initialization and expired token retrieval", async () => {
  const browser = app({ user: { uid: "expired" } }, { waiting: true, auth: () => new Promise(() => {}) });
  browser.api.setTool("email");
  await browser.api.run();
  assert.equal(browser.requests.length, 1);
  assert.equal(browser.authCalls(), 0);
  assert.match(browser.results.innerHTML, /Email intelligence/);
});

test("every email API subtree is public while account-protected endpoints retain authorization", async () => {
  const browser = app({ user: { uid: "account" } });
  for (const endpoint of ["/api/email", "/api/email/photo", "/api/email?fixture=1"]) {
    await browser.api.api(endpoint, { email: "fixture@example.com" });
    assert.equal(browser.requests.at(-1).init.headers.Authorization, undefined);
  }
  assert.equal(browser.authCalls(), 0);
  await browser.api.api("/api/username", { username: "fixture" });
  assert.equal(browser.authCalls(), 1);
  assert.equal(browser.requests.at(-1).init.headers.Authorization, "Bearer fixture-token");
});

test("sign-out or account switch during an email request does not reject the report", async () => {
  let browser;
  browser = app({ user: { uid: "first" } }, { onFetch: () => browser.change({ user: { uid: "second" } }) });
  const data = await browser.api.api("/api/email", { email: "fixture@example.com" });
  browser.change({ user: null });
  browser.api.show("email", data);
  assert.match(browser.results.innerHTML, /Dropbox/);
  assert.equal(browser.api.result().tool, "email");
});

test("displayed email findings remain visible through sign-out and account switches", () => {
  const browser = app({ user: { uid: "first" } });
  browser.api.show("email", fixture());
  const original = browser.results.innerHTML;
  browser.change({ user: null });
  assert.equal(browser.results.innerHTML, original);
  assert.equal(browser.api.result().tool, "email");
  browser.change({ user: { uid: "second" } });
  assert.equal(browser.results.innerHTML, original);
});

test("account-protected reports still clear when their owner signs out", () => {
  const browser = app({ user: { uid: "first" } });
  browser.api.seedAccountReport();
  browser.results.innerHTML = "Private account report";
  browser.change({ user: null });
  assert.equal(browser.api.result(), null);
  assert.doesNotMatch(browser.results.innerHTML, /Private account report/);
});

test("an account change during a protected request still rejects its response", async () => {
  let browser;
  browser = app({ user: { uid: "first" } }, { onFetch: () => browser.change({ user: { uid: "second" } }) });
  await assert.rejects(browser.api.api("/api/username", { username: "fixture" }), /account changed before the report arrived/);
});

function photoHarness(accountState = null) {
  const handlers = {}, requests = [], revoked = [];
  let authCalls = 0;
  const attrs = { src: "https://lh3.googleusercontent.com/fixture-photo" };
  const img = { isConnected: true, complete: false, naturalWidth: 0,
    parentElement: { classList: { add() {}, remove() {} }, removeAttribute() {} },
    getAttribute: name => attrs[name], removeAttribute: name => { delete attrs[name]; },
    addEventListener: (name, callback) => { handlers[name] = callback; }, remove() { this.isConnected = false; },
  };
  class PhotoURL extends URL {
    static createObjectURL() { return "blob:fixture-photo"; }
    static revokeObjectURL(url) { revoked.push(url); }
  }
  const scope = { location: { href: "https://myrecon.xyz/", origin: "https://myrecon.xyz" } };
  if (accountState) scope.MyReconAccount = { state: () => accountState, authHeaders: () => { authCalls++; throw new Error("Expired token"); }, onChange: () => { throw new Error("Public photo registered account guard"); } };
  const context = { window: scope, URL: PhotoURL, Blob, AbortController, setTimeout, clearTimeout,
    fetch: async (url, init) => { requests.push({ url, init }); return { ok: true, headers: { get: name => name === "Content-Type" ? "image/png" : null }, blob: async () => new Blob(["fixture"], { type: "image/png" }) }; },
  };
  vm.runInNewContext(script("email-photos.js"), context);
  scope.EmailPhotos.wire({ querySelectorAll: () => [img] }, "https://api.example.com");
  return { img, handlers, requests, revoked, authCalls: () => authCalls };
}

for (const [name, state] of [["guest", null], ["expired signed-in", { user: { uid: "expired" } }]]) {
  test(`${name} email photo retries publicly with bounded delivery safeguards`, async () => {
    const photo = photoHarness(state);
    await photo.handlers.error();
    assert.equal(photo.requests.length, 1);
    assert.match(photo.requests[0].url, /\/api\/email\/photo\?url=/);
    assert.equal(photo.requests[0].init.headers, undefined);
    assert.equal(photo.requests[0].init.credentials, "omit");
    assert.equal(photo.requests[0].init.redirect, "error");
    assert.equal(photo.authCalls(), 0);
    assert.equal(photo.img.src, "blob:fixture-photo");
    photo.img.naturalWidth = 1;
    photo.handlers.load();
    assert.deepEqual(photo.revoked, ["blob:fixture-photo"]);
    assert.equal(photo.img.isConnected, true);
    await photo.handlers.error();
    assert.equal(photo.requests.length, 1, "at most one CDN retry");
    assert.equal(photo.img.isConnected, false, "failed retry falls back to initials");
  });
}

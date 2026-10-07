const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const script = (name) => fs.readFileSync(path.join(__dirname, "../assets/js", name), "utf8");

function app(state, scope) {
  const note = { textContent: "" }, results = { innerHTML: "" };
  const context = {
    URL, location: { href: "https://myrecon.xyz/" },
    window: { MYRECON: { endpoints: {} }, matchMedia: () => ({ matches: false }),
      MyReconAccount: { enabled: true, state: () => state } },
    document: { addEventListener() {}, querySelectorAll: () => [],
      querySelector: (s) => s === "#scopeNote" ? note : s === "#results" ? results
        : s === 'input[name="scope"]:checked' ? { value: scope } : null },
  };
  vm.runInNewContext(script("app.js").replace(/\}\)\(\);\s*$/,
    "globalThis.adapter = { refreshScopeNote, setGate, previewUnlock };})();"), context);
  return { note, results, api: context.adapter };
}

test("guest and signed-in standard scope notes state the free result boundary", async () => {
  const guest = app({ user: null }, "full");
  await guest.api.refreshScopeNote(false);
  assert.match(guest.note.textContent, /Standard scans require sign-in/);
  assert.match(guest.note.textContent, /Sign in with Google/);
  assert.match(guest.note.textContent, /5 free scans a day/);
  const signed = app({ user: { uid: "u" }, account: { standard_scans_unlimited: true } }, "full");
  await signed.api.refreshScopeNote(false);
  assert.match(signed.note.textContent, /unlimited with your paid plan/);
  assert.doesNotMatch(signed.note.textContent, /trial|pass|used/);
  assert.match(guest.api.previewUnlock({ checked: 561, visible: 100, hidden: 461 }), /5 free standard scans a day/);
});

test("extended balances show permanent pack credits and legacy expiry separately", async () => {
  const pack = app({ user: { uid: "u" }, account: { extended_scans_left: 10, extended_pack_scans_left: 10 } }, "extended");
  await pack.api.refreshScopeNote(false);
  assert.match(pack.note.textContent, /10 Extended scans left/);
  assert.match(pack.note.textContent, /never expire/);
  assert.doesNotMatch(pack.note.textContent, /1970|Invalid Date/);
  const legacy = app({ user: { uid: "u" }, account: { extended_scans_left: 12,
    extended_legacy_scans_left: 2, extended_legacy_until: Date.now() + 86400000 } }, "extended");
  await legacy.api.refreshScopeNote(false);
  assert.match(legacy.note.textContent, /2 from a previous pass expire/);
  pack.api.setGate({ code: "upgrade_required", scope: "extended", account: {} });
  assert.match(pack.results.innerHTML, /₹99.*10 Extended scans/);
  assert.match(pack.results.innerHTML, /Run a free standard scan/);
});

test("account summary shows free standard scans alongside extended pack balance", () => {
  const elements = Object.fromEntries(["#account", "#acctWho", "#acctPlan", "#acctUsage"].map((s) => [s, {}]));
  const context = { window: { MYRECON: {}, MyReconAccount: { avatarHtml: () => "", wireAvatar() {} } },
    document: { addEventListener() {}, querySelector: (s) => elements[s], querySelectorAll: () => [] } };
  vm.runInNewContext(script("pricing.js").replace(/\}\)\(\);\s*$/,
    "globalThis.renderAccount = renderAccount;})();"), context);
  context.renderAccount({ user: { uid: "u" }, account: { standard_scans_unlimited: true, extended_scans_left: 10, extended_pack_scans_left: 10 } });
  assert.match(elements["#acctUsage"].textContent, /Unlimited standard.*paid plan/);
  assert.match(elements["#acctUsage"].textContent, /10 Extended pack scans left, no expiry/);
  context.renderAccount({ user: { uid: "u" }, account: { standard_scans_unlimited: true, extended_scans_left: 0 } });
  assert.equal(elements["#acctPlan"].textContent, "Extended Scan Pack");
  assert.match(elements["#acctUsage"].textContent, /Unlimited standard/);
  context.renderAccount({ user: { uid: "u" }, account: { standard_scans_unlimited: false,
    standard_scans_left: 3, standard_resets_at: Date.now() + 86400000, extended_scans_left: 0 } });
  assert.equal(elements["#acctPlan"].textContent, "Free standard account");
  assert.match(elements["#acctUsage"].textContent, /3 of 5 free standard scans left today/);
  assert.doesNotMatch(elements["#acctUsage"].textContent, /Unlimited/);
});

test("free daily limit is visible in scope notes and gives a paid upgrade action", async () => {
  const free = app({ user: { uid: "u" }, account: { standard_scans_unlimited: false,
    standard_scans_left: 0 } }, "full");
  await free.api.refreshScopeNote(false);
  assert.match(free.note.textContent, /0 of 5 free scans left today/);
  assert.match(free.note.textContent, /midnight UTC/);
  free.api.setGate({ code: "standard_daily_limit", account: {} });
  assert.match(free.results.innerHTML, /used today&#39;s 5 standard scans/);
  assert.match(free.results.innerHTML, /₹99.*unlimited standard scans/);
  assert.doesNotMatch(free.results.innerHTML, /data-gate="signin"/);
  const quick = app({ user: { uid: "u" }, account: { standard_scans_left: 2 } }, "standard");
  await quick.api.refreshScopeNote(false);
  assert.match(quick.note.textContent, /2 of 5 free scans left today/);
});

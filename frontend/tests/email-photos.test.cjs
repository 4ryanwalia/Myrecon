const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function runtime() {
  const scope = { location: { href: "https://myrecon.xyz/#tool=email", origin: "https://myrecon.xyz" } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../assets/js/email-photos.js"), "utf8"),
    { window: scope, URL, Set, WeakSet });
  return scope.EmailPhotos;
}

function image(url, { complete = false, width = 0 } = {}) {
  const classes = new Set(), attrs = new Map([["src", url]]), listeners = new Map();
  const parent = {
    title: "", classList: { add: x => classes.add(x), remove: x => classes.delete(x) },
    removeAttribute: name => { if (name === "title") parent.title = ""; },
    fallbackText: "GH"
  };
  const img = {
    complete, naturalWidth: width, parentElement: parent, removed: false,
    addEventListener: (name, fn) => { const current = listeners.get(name) || []; current.push(fn); listeners.set(name, current); },
    getAttribute: name => attrs.get(name), setAttribute: (name, value) => attrs.set(name, value),
    remove() { this.removed = true; this.parentElement = null; },
    emit(name) { for (const fn of listeners.get(name) || []) fn(); }
  };
  Object.defineProperty(img, "src", { get: () => attrs.get("src"), set: value => attrs.set("src", value) });
  return { img, parent, classes, attrs, root: { querySelectorAll: () => [img] } };
}

test("known public image gets a same-origin proxy even with empty production apiBase", () => {
  const photo = "https://lh3.googleusercontent.com/a/fixture=s200";
  assert.equal(runtime().source(photo, ""), "https://myrecon.xyz/api/email/photo?url=" + encodeURIComponent(photo));
});

test("unknown, private, credential-bearing and local fixture URLs stay direct", () => {
  const api = runtime();
  for (const url of ["https://unknown.example/photo.jpg", "http://127.0.0.1:8000/fixture.svg",
    "https://user:secret@media.licdn.com/photo", "https://media.licdn.com:444/photo",
    "https://media.licdn.com/photo#fragment", "https://media.licdn.com.attacker.test/photo"]) {
    assert.equal(api.source(url, "http://localhost:5000"), url);
  }
});

test("direct failure retries once; final failure preserves fallback and removes broken image", () => {
  const api = runtime(), fixture = image("https://avatars.githubusercontent.com/u/42");
  api.wire(fixture.root, "http://localhost:5000");
  fixture.img.emit("error");
  assert.match(fixture.img.src, /^http:\/\/localhost:5000\/api\/email\/photo\?url=/);
  assert.equal(fixture.attrs.get("crossorigin"), "anonymous");
  assert.equal(fixture.img.removed, false);
  fixture.img.emit("error");
  assert.equal(fixture.img.removed, true);
  assert.equal(fixture.parent.title, "Photo unavailable");
  assert.equal(fixture.parent.fallbackText, "GH");
});

test("success makes image visible and clears stale unavailable title", () => {
  const api = runtime(), fixture = image("https://media.licdn.com/fixture");
  fixture.parent.title = "Photo unavailable";
  api.wire(fixture.root, "");
  fixture.img.naturalWidth = 48;
  fixture.img.emit("load");
  assert.equal(fixture.classes.has("loaded"), true);
  assert.equal(fixture.parent.title, "");
});

test("cached completed image is shown without waiting for another load event", () => {
  const fixture = image("https://www.gravatar.com/avatar/fixture", { complete: true, width: 48 });
  runtime().wire(fixture.root, "");
  assert.equal(fixture.classes.has("loaded"), true);
});

test("cached broken direct image is retried immediately", () => {
  const fixture = image("https://lh3.googleusercontent.com/a/fixture", { complete: true });
  runtime().wire(fixture.root, "");
  assert.match(fixture.img.src, /\/api\/email\/photo\?url=/);
});

test("duplicate wiring does not add multiple retry handlers", () => {
  const api = runtime(), fixture = image("https://avatars.githubusercontent.com/u/42");
  api.wire(fixture.root, "");
  api.wire(fixture.root, "");
  fixture.img.emit("error");
  assert.equal(fixture.img.removed, false);
});

test("unsupported image failure does not call arbitrary upstream proxy", () => {
  const fixture = image("https://unknown.example/fixture.jpg");
  runtime().wire(fixture.root, "");
  fixture.img.emit("error");
  assert.equal(fixture.img.removed, true);
  assert.equal(fixture.img.src, "https://unknown.example/fixture.jpg");
});

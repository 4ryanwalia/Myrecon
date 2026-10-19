const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function renderer() {
  const context = { window: { MYRECON: { endpoints: {} }, matchMedia: () => ({ matches: true }) },
    URL, location: { href: 'https://myrecon.xyz/' },
    document: { addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] } };
  const source = fs.readFileSync(path.join(__dirname, '../assets/js/app.js'), 'utf8')
    .replace(/\}\)\(\);\s*$/, 'globalThis.adapter = { profileCard, buildTextSummary };})();');
  vm.runInNewContext(source, context);
  return context.adapter;
}

const profile = { platform: 'Inkitt', category: 'profile', url: 'https://www.inkitt.com/alice',
  confidence: 'high', display_name: 'Alice <script>', bio: 'Writer', profile_pic_url: 'https://cdn.example/a.png',
  followers: 0, statistics: { followers: 0, stories: 3 }, public_links: ['https://example.com', 'javascript:alert(1)'],
  metadata_source: { platform: 'Inkitt', url: 'https://www.inkitt.com/alice', basis: 'public account object' } };

test('live and final cards preserve zero statistics, source and safe public links without nested anchors', () => {
  for (const live of [true, false]) {
    const html = renderer().profileCard(profile, live);
    assert.match(html, /0 followers/);
    assert.match(html, /3 stories/);
    assert.match(html, /Source:/);
    assert.match(html, /href="https:\/\/example.com\//);
    assert.match(html, /Alice &lt;script&gt;/);
    assert.doesNotMatch(html, /javascript:|<script>/);
    assert.match(html, /^<div class="card">/);
    assert.match(html, /Open profile/);
  }
});

test('text reports retain account metadata, supported stats and attribution', () => {
  const r = { ...profile, public_links: ['https://example.com'] };
  const text = renderer().buildTextSummary({ tool: 'username', query: 'alice',
    data: { partial: true, results: { profiles: [r], documents: [], mentions: [] } } });
  for (const item of ['Name: Alice', 'Bio: Writer', 'Avatar: https://cdn.example/a.png',
    'Public links: https://example.com', 'followers: 0', 'stories: 3', 'Source: Inkitt;', 'public account object']) {
    assert.ok(text.includes(item), item);
  }
});

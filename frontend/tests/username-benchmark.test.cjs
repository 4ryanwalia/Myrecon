const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {validCase, comparisonSeries} = require('../assets/js/username-benchmark.js');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/username-benchmark.json'), 'utf8'));
test('recorded case study reconciles native hits with reviewed unique leads', () => {
  assert.equal(validCase(data), true);
  for (const tool of ['myrecon','sherlock','maigret']) {
    const stats = data.tools[tool].summary;
    const hits = data.results.filter(r => r.tools[tool]?.reported);
    assert.equal(hits.filter(r => r.reference.verdict === 'not_found').length, stats.source_contradicted);
    assert.equal(hits.filter(r => r.reference.verdict === 'found').length, stats.source_supported);
    assert.equal(data.tools[tool].shared_summary.checked, data.shared_address_count);
  }
});
test('altered counts cannot turn unresolved leads into a perfect score', () => {
  const changed = structuredClone(data);
  changed.tools.maigret.summary.unverified = 0;
  assert.equal(validCase(changed), false);
});
test('hidden preview matches cannot be silently treated as verified profiles', () => {
  assert.equal(data.tools.osintsearch.named_matches + data.tools.osintsearch.hidden_matches, data.tools.osintsearch.grouped_matches);
  assert.equal(data.tools.osintsearch.profile_urls_exposed, false);
  assert.equal(data.tools.osintsearch.shared_summary, null);
});

test('graph counts reflect source review for each catalogue and shared scope', () => {
  for (const scope of ['full', 'shared']) {
    const series = comparisonSeries(data, scope);
    assert.deepEqual(series.map(s => s.tool), ['myrecon', 'sherlock', 'maigret']);
    for (const s of series) {
      const leads = data.results.filter(r => r.tools[s.tool]?.reported && (scope === 'full' || r.shared));
      assert.equal(s.total, leads.length);
      assert.equal(s.supported, leads.filter(r => r.reference.verdict === 'found').length);
      assert.equal(s.falsePositives, leads.filter(r => r.reference.verdict === 'not_found').length);
      assert.equal(s.unverified, leads.filter(r => r.reference.verdict === 'unknown').length);
      assert.equal(s.total, s.supported + s.falsePositives + s.unverified);
    }
  }
});

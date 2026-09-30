const test = require('node:test');
const assert = require('node:assert/strict');
const { graphSeries, validRun } = require('../assets/js/benchmarks.js');

function stats(overrides = {}) {
  return { TP: 2, TN: 3, FP: 1, FN: 0, unknown: 3, unscored: 1, unknown_negative: 2,
    total: 10, scored: 6, negative_denominator: 4, false_positive_rate_percent: 25,
    accuracy_percent: 83.33, coverage_percent: 60, p50_seconds: 1, p95_seconds: 2, ...overrides };
}
function run(s = stats()) {
  return { started_at_utc: '2026-09-30T03:17:00Z', finished_at_utc: '2026-09-30T03:19:00Z',
    tools: { myrecon: s, http200_baseline: stats() } };
}
test('graph records real errors and leaves unavailable negatives as gaps', () => {
  const missing = run(stats({ TN: 0, FP: 0, negative_denominator: 0, false_positive_rate_percent: null }));
  const data = graphSeries([run(), missing, run(stats({ FP: 2 }))], 'fp');
  assert.deepEqual(data[0].values, [1, null, 2]);
  assert.deepEqual(data[1].values, [1, 1, 1]);
});
test('valid measurements require consistent denominators, coverage and percentages', () => {
  assert.equal(validRun(run()), true);
  assert.equal(validRun(run(stats({ false_positive_rate_percent: 0 }))), false);
  assert.equal(validRun(run(stats({ accuracy_percent: 100 }))), false);
  assert.equal(validRun(run(stats({ coverage_percent: 100 }))), false);
  assert.equal(validRun(run(stats({ TN: 9 }))), false);
});
test('unavailable accuracy and real timing measurements remain separate', () => {
  const data = graphSeries([run(stats({ accuracy_percent: null, p50_seconds: 9.4 }))], 'accuracy');
  assert.equal(data[0].values[0], null);
  assert.equal(graphSeries([run(stats({ p50_seconds: 9.4 }))], 'speed')[0].values[0], 9.4);
});

test('coverage shows unknown outcomes even when scored accuracy is perfect', () => {
  const partial = run(stats({ TP: 2, TN: 2, FP: 0, FN: 0, unknown: 6, unscored: 0,
    scored: 4, negative_denominator: 2, unknown_negative: 3, false_positive_rate_percent: 0,
    accuracy_percent: 100, coverage_percent: 40 }));
  assert.equal(validRun(partial), true);
  assert.equal(graphSeries([partial], 'accuracy')[0].values[0], 100);
  assert.equal(graphSeries([partial], 'coverage')[0].values[0], 40);
  const outage = run(stats({ TP: 0, TN: 0, FP: 0, FN: 0, unknown: 10, unscored: 0,
    scored: 0, negative_denominator: 0, unknown_negative: 4, false_positive_rate_percent: null,
    accuracy_percent: null, coverage_percent: 0 }));
  assert.equal(validRun(outage), true);
  assert.equal(graphSeries([outage], 'fp')[0].values[0], null);
  assert.equal(graphSeries([outage], 'coverage')[0].values[0], 0);
});

test('named tools have gaps in older runs and are validated when present', () => {
  const old = run();
  const measured = run();
  measured.tools.sherlock = stats();
  measured.tools.maigret = stats({ p50_seconds: 3 });
  assert.equal(validRun(old), true);
  assert.equal(validRun(measured), true);
  assert.deepEqual(graphSeries([old, measured], 'fp', ['myrecon', 'sherlock'])[1].values, [null, 1]);
  assert.deepEqual(graphSeries([old, measured], 'speed', ['myrecon', 'maigret'])[1].values, [null, 3]);
  measured.tools.sherlock.accuracy_percent = 100;
  assert.equal(validRun(measured), false);
});

test('failed named runner is unavailable, including coverage and speed', () => {
  const measured = run();
  measured.tools.sherlock = stats();
  measured.tool_metadata = { sherlock: { status: 'unavailable' } };
  for (const mode of ['fp', 'accuracy', 'coverage', 'speed']) {
    assert.equal(graphSeries([measured], mode, ['myrecon', 'sherlock'])[1].values[0], null);
  }
});

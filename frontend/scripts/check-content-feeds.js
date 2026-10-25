const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
function checkFeeds(read, now = Date.now()) {
  const breaches = read('assets/data/breaches.json');
  const cases = read('assets/data/case-files.json');
  const apiBreaches = read('data/v1/breaches.json');
  const apiCases = read('data/v1/case-files.json');
  for (const feed of [breaches, cases]) {
    const age = now - Date.parse(feed.generated);
    assert.ok(Number.isFinite(age) && age >= -300000 && age < 36 * 3600000, 'Feed is stale or has an invalid generation date');
  }
  assert.ok(breaches.breaches.length && cases.cases.length, 'Refusing empty feeds');
  assert.deepEqual(apiBreaches.breaches, breaches.breaches, 'Android and public breach API differ');
  assert.equal(apiCases.case_files.length, cases.cases.length, 'Case counts differ');
  for (const published of apiCases.case_files) {
    const source = cases.cases.find(item => item.slug === published.slug);
    assert.ok(source, 'Public case missing from Android feed');
    for (const [field, value] of Object.entries(published)) assert.deepEqual(value, source[field], `Case ${published.slug}: ${field} differs`);
  }
  for (const [items, key] of [[breaches.breaches, 'name'], [cases.cases, 'slug']]) {
    assert.equal(new Set(items.map(item => item[key])).size, items.length, 'Duplicate feed entries');
    for (const item of items) {
      assert.ok(item.story && item.url.startsWith('https://www.myrecon.xyz/'), 'Missing story or canonical source URL');
    }
  }
  return {breaches: breaches.breaches.length, cases: cases.cases.length};
}
async function main() {
  let read;
  const base = process.argv[2];
  if (base) {
    const files = ['assets/data/breaches.json', 'assets/data/case-files.json', 'data/v1/breaches.json', 'data/v1/case-files.json'];
    const data = {};
    for (const file of files) {
      const response = await fetch(new URL(file, base.endsWith('/') ? base : base + '/'), {signal: AbortSignal.timeout(20000)});
      assert.ok(response.ok, `${file}: HTTP ${response.status}`);
      data[file] = await response.json();
    }
    read = file => data[file];
  } else read = file => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
  console.log('[feeds] Fresh Android/public API parity verified:', checkFeeds(read));
}
if (require.main === module) main().catch(error => { console.error(error.message.split('\n')[0]); process.exitCode = 1; });
module.exports = {checkFeeds};

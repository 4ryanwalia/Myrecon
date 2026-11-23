const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {select} = require('../scripts/build-breaches');
const {checkFeeds} = require('../scripts/check-content-feeds');
test('newly disclosed older breaches are included, retired and fabricated are excluded', () => {
 const record = {Name:'RegressionOldDisclosure',Title:'Example',BreachDate:'2010-01-01',AddedDate:'2026-10-25T00:00:00Z',DataClasses:['Email addresses']};
 assert.ok(select([record]).some(x=>x.Name===record.Name));
 assert.equal(select([{...record,IsRetired:true},{...record,IsFabricated:true}]).length,0);
});

test('public API discovery points to the OpenAPI description for every feed', () => {
 const directory = path.join(__dirname, '../data/v1');
 const read = name => JSON.parse(fs.readFileSync(path.join(directory, name), 'utf8'));
 const index = read('index.json');
 const spec = read('openapi.json');
 const base = spec.servers[0].url;
 assert.equal(index.openapi, base + '/openapi.json');
 assert.equal(spec.info.version, String(index.api_version));
 assert.deepEqual(Object.keys(spec.paths).sort(), [
  '/index.json',
  ...Object.values(index.endpoints).map(url => {
   assert.ok(url.startsWith(base + '/'));
   return url.slice(base.length);
  }),
 ].sort());
 for (const operations of Object.values(spec.paths)) {
  assert.deepEqual(Object.keys(operations), ['get']);
  const reference = operations.get.responses['200'].content['application/json'].schema.$ref;
  assert.ok(spec.components.schemas[reference.split('/').at(-1)]);
 }
});
test('feed validation rejects stale and divergent API payloads',()=>{
 const item = {name:'Example',slug:'example',story:{},url:'https://www.myrecon.xyz/breaches/example.html'};
 const data = {'assets/data/breaches.json':{generated:'2026-10-25T00:00:00Z',breaches:[item]},'assets/data/case-files.json':{generated:'2026-10-25T00:00:00Z',cases:[item]},'data/v1/breaches.json':{breaches:[item]},'data/v1/case-files.json':{case_files:[item]}};
 const read = p=>data[p];
 assert.deepEqual(checkFeeds(read,Date.parse('2026-10-25T01:00:00Z')),{breaches:1,cases:1});
 assert.throws(()=>checkFeeds(read,Date.parse('2026-10-28T01:00:00Z')),/stale/);
 data['data/v1/breaches.json'].breaches=[];
 assert.throws(()=>checkFeeds(read,Date.parse('2026-10-25T01:00:00Z')),/differ/);
});

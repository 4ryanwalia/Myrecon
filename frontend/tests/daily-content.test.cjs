const test = require('node:test');
const assert = require('node:assert/strict');
const {select} = require('../scripts/build-breaches');
const {checkFeeds} = require('../scripts/check-content-feeds');
test('newly disclosed older breaches are included, retired and fabricated are excluded', () => {
 const record = {Name:'RegressionOldDisclosure',Title:'Example',BreachDate:'2010-01-01',AddedDate:'2026-10-25T00:00:00Z',DataClasses:['Email addresses']};
 assert.ok(select([record]).some(x=>x.Name===record.Name));
 assert.equal(select([{...record,IsRetired:true},{...record,IsFabricated:true}]).length,0);
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

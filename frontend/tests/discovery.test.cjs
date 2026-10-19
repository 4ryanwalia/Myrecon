const {test} = require('node:test');
const assert = require('node:assert/strict');
const {confirmed,recap} = require('../assets/js/discovery.js');
test('only distinct found profiles explicitly marked Mine count', () => {
 const p = [{url:'a',exists:true},{url:'a',exists:true},{url:'b',exists:true},{url:'c',exists:false},{url:'d',verdict:'found'}];
 const choices = {a:{choice:'mine'},b:{choice:'not_mine'},c:{choice:'mine'},d:{choice:'unsure'}};
 assert.equal(confirmed(p, u => choices[u]),1);
 assert.equal(confirmed([], u => choices[u]),0);
 assert.equal(confirmed(p, () => null),0);
});
test('recap contains only allowed fields and accurate count', () => {
 assert.deepEqual(recap(6), {title:'MyRecon discovery recap',text:'I confirmed 6 public accounts with MyRecon.',url:'https://www.myrecon.xyz/'});
 assert.match(recap(-2).text,/0 public/);
 assert.match(recap('alice@example.com').text,/0 public/);
 assert.doesNotMatch(JSON.stringify(recap(6)),/rediscovered|score|username|profile_url/);
});

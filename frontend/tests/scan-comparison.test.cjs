const {test}=require('node:test');
const assert=require('node:assert/strict');
const {normalize,compare}=require('../assets/js/scan-comparison');
const report=(checks,extra={})=>({tool:'username',query:'sam',data:{query:{username:'sam',scope:'standard'},platform_checks:checks,...extra}});
test('snapshots reject locked reports and do not retain arbitrary report fields',()=>{
  assert.equal(normalize(report([],{guest_access:{}})),null);
  assert.equal(normalize(report([],{guest_preview:{requires_sign_in:true}})),null);
  const row=normalize(report([{platform:'Test',verdict:'found',url:'javascript:alert(1)',reason:'source evidence'}],{secret:'not stored'}));
  assert.equal(row.rows[0].url,'');assert(!JSON.stringify(row).includes('not stored'));
});
test('comparisons distinguish missing checks, unavailable sources, no match and evidence changes',()=>{
  const a=normalize(report(['New','Offline','Gone','Missing','Changed'].map(platform=>({platform,verdict:platform==='New'?'not_found':'found',reason:'old'}))),1);
  const b=normalize(report([{platform:'New',verdict:'found'},{platform:'Offline',verdict:'unknown',unreachable:true},{platform:'Gone',verdict:'not_found'},{platform:'Changed',verdict:'found',reason:'new'}]),2);
  const changes=Object.fromEntries(compare(b,a).changes.map(c=>[c.platform,c.label]));
  assert.equal(changes.New,'Newly found');assert.equal(changes.Offline,'Source unavailable');assert.match(changes.Gone,/removal unconfirmed/);assert.match(changes.Missing,/Not checked/);assert.equal(changes.Changed,'Evidence changed');
  assert.throws(()=>compare(a,{...b,query:'someone-else'}),/same username/);
  assert.throws(()=>compare(a,{...b,scope:'extended'}),/scan size/);
  assert.throws(()=>compare(a,a),/different/);
});

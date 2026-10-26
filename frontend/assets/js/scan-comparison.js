/* Only explicit saves of unlocked username reports become local snapshots. */
(function () {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function safeUrl(raw) {try{const u=new URL(raw);if(!['https:','http:'].includes(u.protocol)||u.username||u.password)return '';u.hash='';return u.href;}catch{return '';}}
  function normalize(report, savedAt=Date.now()) {
    if(report.tool!=='username'||report.data?.guest_access||report.data?.guest_preview?.requires_sign_in||report.data?.guest_preview?.hidden_cards>0) return null;
    const d=report.data||{}, rows=new Map();
    for(const c of d.platform_checks||[]) {
      const key=String(c.platform||'').trim().toLowerCase();if(!key)continue;
      rows.set(key,{key,platform:String(c.platform),url:safeUrl(c.url),status:['found','possible','not_found','unknown'].includes(c.verdict)?c.verdict:'unknown',unavailable:!!c.unreachable,evidence:String(c.reason||'').slice(0,1000)});
    }
    for(const p of d.results?.profiles||[]) {
      const key=String(p.platform||'').trim().toLowerCase();if(!key)continue;
      const existing=rows.get(key);
      rows.set(key,{...existing,key,platform:String(p.platform),url:safeUrl(p.url),status:existing?.status||(p.confidence==='high'?'found':'possible'),unavailable:existing?.unavailable||false,evidence:String(p.evidence||existing?.evidence||'').slice(0,1000)});
    }
    if(!rows.size)return null;
    return {id:String(savedAt)+'-'+Math.random().toString(36).slice(2,9),query:String(report.query||d.query?.username||'').replace(/^@/,''),scope:String(d.query?.scope||'not recorded'),savedAt,checkedAt:d.checked_at||d.scanned_at||null,partial:!!d.partial,rows:[...rows.values()]};
  }
  function compare(a,b) {
    if(a.query!==b.query||a.scope!==b.scope)throw new Error('Choose snapshots of the same username and scan size.');
    if(a.id===b.id)throw new Error('Choose two different snapshots.');
    const [before,after]=a.savedAt<=b.savedAt?[a,b]:[b,a];
    const old=new Map(before.rows.map(r=>[r.key,r])), next=new Map(after.rows.map(r=>[r.key,r])),changes=[];
    for(const key of new Set([...old.keys(),...next.keys()])) {
      const x=old.get(key),y=next.get(key);let label='';
      if(!y)label='Not checked in the newer snapshot';
      else if(y.status==='unknown'&&(x?.status!=='unknown'||x?.unavailable!==y.unavailable))label=y.unavailable?'Source unavailable':'Could not verify';
      else if(y.status==='found'&&x?.status!=='found')label=x?.status==='not_found'?'Newly found':'Newly observed · earlier evidence incomplete';
      else if(y.status==='not_found'&&x?.status==='found')label='No match returned now · removal unconfirmed';
      else if(!x)label='New source checked';
      else if(y.status!==x.status)label='Result status changed';
      else if(y.evidence!==x.evidence||y.url!==x.url)label='Evidence changed';
      if(label)changes.push({platform:(y||x).platform,label,before:x||null,after:y||null});
    }
    return {before,after,changes};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={normalize,compare};
  if(typeof document==='undefined')return;
  const owner=()=>window.MyReconAccount?.state()?.user?.uid||'';
  const key=()=>`myrecon.scan-snapshots.v1:${owner()}`;
  function read(){if(!owner())return [];try{const v=JSON.parse(localStorage.getItem(key())||'[]');return Array.isArray(v)?v.filter(r=>r&&Array.isArray(r.rows)&&typeof r.query==='string'&&Number.isFinite(r.savedAt)):[];}catch{return [];}}
  const time=n=>new Date(n).toLocaleString();
  function host(){let el=document.getElementById('scan-comparison');if(!el){const anchor=document.getElementById('saved-section');if(!anchor)return null;el=document.createElement('section');el.id='scan-comparison';el.className='container';el.setAttribute('aria-label','Compare saved scan snapshots');anchor.after(el);}return el;}
  function render(){
    const el=host();if(!el)return;const rows=read();el.hidden=!rows.length;
    if(!rows.length){el.replaceChildren();return;}
    const options=rows.map(r=>`<option value="${esc(r.id)}">${esc(r.query)} · ${esc(r.scope)} · saved ${esc(time(r.savedAt))}</option>`).join('');
    el.innerHTML=`<div class="snapshot-panel"><h3>What changed between scans?</h3><p>Compare snapshots you explicitly saved. These records stay in this browser for your signed-in account; they do not sync between devices. Up to 20 snapshots are kept.</p>${rows.length>1?`<div class="snapshot-selects"><label>First snapshot<select data-snapshot-a>${options}</select></label><label>Second snapshot<select data-snapshot-b>${options}</select></label></div><button class="btn btn-sm" data-snapshot-compare>Compare snapshots</button>`:'<p>Save a later scan of the same username and scan size to make a comparison.</p>'}<div class="snapshot-diff" data-snapshot-diff role="status" aria-live="polite"></div><div class="snapshot-tools"><button type="button" class="btn btn-ghost btn-sm" data-snapshot-clear>Clear local snapshots</button></div></div>`;
    if(rows.length>1)el.querySelector('[data-snapshot-b]').selectedIndex=1;
  }
  function capture(report){if(!owner())return {message:'Comparison snapshots require a signed-in, unlocked username report.'};const row=normalize(report);if(!row)return {message:'This report has no unlocked platform evidence to compare.'};try{localStorage.setItem(key(),JSON.stringify([row,...read()].slice(0,20)));render();return {saved:true,message:'Saved a comparison snapshot in this browser.'};}catch{return {message:'Snapshot not saved: browser storage is unavailable or full.'};}}
  document.addEventListener('click',e=>{
    if(e.target.closest('[data-snapshot-clear]')){try{localStorage.removeItem(key());render();}catch{host().querySelector('[data-snapshot-diff]').textContent='Could not clear browser storage.';}}
    if(!e.target.closest('[data-snapshot-compare]'))return;
    const el=host(),out=el.querySelector('[data-snapshot-diff]'),rows=read();
    try{const a=rows.find(r=>r.id===el.querySelector('[data-snapshot-a]').value),b=rows.find(r=>r.id===el.querySelector('[data-snapshot-b]').value);if(!a||!b)throw new Error('These snapshots are no longer available.');const result=compare(a,b);
      const status=r=>!r?'Not checked':r.unavailable?'Unavailable':({found:'Found',possible:'Possible match',not_found:'No match',unknown:'Could not verify'}[r.status]||'Unknown');
      out.innerHTML=`<p>Saved ${esc(time(result.before.savedAt))} → ${esc(time(result.after.savedAt))}</p><p>Source check times: ${esc(result.before.checkedAt || "not recorded")} → ${esc(result.after.checkedAt || "not recorded")}</p><p>${result.before.partial||result.after.partial?'At least one scan had incomplete coverage. ':''}A newly observed profile may be old. Missing or unavailable results do not prove deletion.</p>${result.changes.length?`<ul>${result.changes.map(c=>`<li><strong>${esc(c.platform)}: ${esc(c.label)}</strong><small>${esc(status(c.before))} → ${esc(status(c.after))}</small><details><summary>Compare source evidence</summary><p>Earlier: ${esc(c.before?.evidence||'No evidence recorded')}</p><p>Later: ${esc(c.after?.evidence||'No evidence recorded')}</p>${safeUrl(c.after?.url)?`<a href="${esc(safeUrl(c.after.url))}" target="_blank" rel="noopener noreferrer">Open current source ↗</a>`:''}</details></li>`).join('')}</ul>`:'<p>No changes in the recorded evidence. This does not establish that every account is unchanged.</p>'}`;
    }catch(error){out.textContent=error.message;}
  });
  window.MyReconSnapshots={capture,render};
  const start=async()=>{await window.MyReconAccount?.ready;window.MyReconAccount?.onChange(render);render();};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();

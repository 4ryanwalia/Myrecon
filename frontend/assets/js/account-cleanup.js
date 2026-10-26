/* Action records are local, account-scoped user notes, never evidence of deletion. */
(() => {
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const sources = {
    'github.com': {name:'GitHub', secure:'https://github.com/settings/security', privacy:'https://github.com/settings/profile', remove:'https://docs.github.com/en/account-and-profile/how-tos/account-management/deleting-your-personal-account'},
    'reddit.com': {name:'Reddit', secure:'https://www.reddit.com/settings/account', privacy:'https://support.reddithelp.com/hc/en-us/articles/360043047952-How-can-I-control-how-Reddit-uses-my-information', remove:'https://support.reddithelp.com/hc/en-us/articles/204579509-How-do-I-delete-my-account'},
    'discord.com': {name:'Discord', secure:'https://support.discord.com/hc/en-us/articles/219576828-Setting-up-Multi-Factor-Authentication', privacy:'https://discord.com/privacy', remove:'https://support.discord.com/hc/en-us/articles/212500837-How-to-Delete-your-Discord-Account'}
  };
  const storageKey = () => 'myrecon.cleanup-actions.v1:' + (window.MyReconAccount?.state()?.user?.uid || 'guest');
  function read() { try { const v=JSON.parse(localStorage.getItem(storageKey()) || '{}'); return v && typeof v==='object' && !Array.isArray(v) ? v : {}; } catch { return {}; } }
  function controls(url) {
    let source;
    try { source=sources[new URL(url).hostname.replace(/^www\./,'')]; } catch { return ''; }
    const actions=[['secure','Secure this account','Review your password, recovery methods and active sessions. Turn on a passkey or two-factor authentication when offered.','Security reviewed'],['privacy','Change what is public','Review your bio, contact details, posts and profile visibility. Keep only the details you intend to share.','Visibility reviewed'],['remove','Remove an account you no longer use','Read the service’s instructions first. Save anything you need and check subscriptions or dependencies. Deletion may not remove past posts or copies.','Removal requested']];
    return `<div class="cleanup-actions" data-cleanup-actions="${esc(url)}"><p>Choose the actions that fit this account. Progress saves in this browser for the current user.</p>${actions.map(([key,title,text,label])=>`<details><summary>${title}</summary><p>${text}</p><a href="${source ? esc(source[key]) : '/blog/after-finding-an-old-account.html'}" ${source ? 'target="_blank" rel="noopener noreferrer"' : ''}>${source ? `${source.name}: official ${key==='remove'?'deletion instructions':key==='secure'?'security settings / help':'profile and privacy guidance'}` : 'Read the account cleanup guide'} ↗</a><label><input type="checkbox" data-cleanup-task="${key}"><span>${label} (recorded by me)</span></label></details>`).join('')}<output aria-live="polite"></output><p class="hint">This checklist does not change the external account. A failed lookup does not confirm removal.</p><button type="button" class="btn btn-ghost btn-sm" data-cleanup-reset>Clear action record</button></div>`;
  }
  function paint() {
    const rows=read();
    document.querySelectorAll('[data-cleanup-actions]').forEach(el=>{
      const mine=window.MyReconMatchChoices?.choice(el.dataset.cleanupActions)?.choice==='mine';
      el.hidden=!mine;
      const row=rows[el.dataset.cleanupActions] || {};
      el.querySelectorAll('[data-cleanup-task]').forEach(box=>{box.checked=!!row[box.dataset.cleanupTask];box.disabled=!mine;});
      el.querySelector('output').textContent=`${Object.values(row).filter(v=>v===true).length} of 3 optional actions recorded`;
    });
  }
  function save(el, edit) {
    if(window.MyReconMatchChoices?.choice(el.dataset.cleanupActions)?.choice!=='mine') return;
    const rows=read(); edit(rows,el.dataset.cleanupActions);
    try { localStorage.setItem(storageKey(),JSON.stringify(rows)); paint(); }
    catch { paint();el.querySelector('output').textContent='Browser storage is unavailable. Your change was not saved.'; }
  }
  document.addEventListener('change',e=>{const box=e.target.closest?.('[data-cleanup-task]');if(!box)return;const el=box.closest('[data-cleanup-actions]');save(el,(rows,key)=>{rows[key]={...rows[key],[box.dataset.cleanupTask]:box.checked};});});
  document.addEventListener('click',e=>{const b=e.target.closest?.('[data-cleanup-reset]');if(b)save(b.closest('[data-cleanup-actions]'),(rows,key)=>{delete rows[key];});});
  document.addEventListener('myrecon-choices-changed',paint);
  window.MyReconCleanup={controls,paint};
})();

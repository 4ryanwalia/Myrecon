(() => {
  const form=document.querySelector('[data-archive-filters]');if(!form)return;
  const cards=[...document.querySelectorAll('[data-archive-card]')];
  function filter(){const data=new FormData(form),search=String(data.get('search')||'').trim().toLowerCase();let count=0;
    for(const card of cards){const show=(!search||card.dataset.search.toLowerCase().includes(search))&&['year','industry','incident'].every(k=>!data.get(k)||data.get(k)===card.dataset[k])&&(!data.get('data')||JSON.parse(card.dataset.exposed).includes(data.get('data')));card.hidden=!show;if(show)count++;}
    form.querySelector('[data-archive-count]').textContent=count?`${count} of ${cards.length} records`:'No records match. Try fewer filters or reset.';
  }
  form.addEventListener('submit',e=>e.preventDefault());form.addEventListener('input',filter);form.addEventListener('change',filter);form.addEventListener('reset',()=>setTimeout(filter,0));filter();
})();

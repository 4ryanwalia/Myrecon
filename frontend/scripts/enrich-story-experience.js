const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const photos=require('../content/editorial-photography.json').photos;
const breaches=JSON.parse(fs.readFileSync(path.join(root,'assets/data/breaches.json'),'utf8')).breaches;
const cases=JSON.parse(fs.readFileSync(path.join(root,'assets/data/case-files.json'),'utf8')).cases;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const plain=s=>String(s||'').replace(/<[^>]*>/g,'').trim();
const groups={
  Healthcare:['sharecare','mckesson','medela','star-health','medibank','anthem','aiims','irhythm','singhealth','change-healthcare','23andme'],
  'Social & communities':['doublecounter','twitter','facebook','linkedin','gravatar','myspace','wattpad','mangatoon','soundcloud','dropbox'],
  Retail:['carhartt','underarmour','hottopic','advanceautoparts','canadiantire','tokopedia','home-depot','target','tjx','morrisons','ebay','luxottica'],
  'Finance & insurance':['angelone','prosper','addi','capital-one','jpmorgan','equifax','latitude'],
  Technology:['cyrusone','crunchbase','okta','twilio','solarwinds','kaseya','accellion','moveit','snowflake','adobe','lastpass','nitro'],
  'Travel & hospitality':['railyatri','gitesdefrance','air-india','marriott','british-airways','mgm','cargurus'],
  Gaming:['1win','chess','playcybergames','sony-psn']
};
function industry(slug){return Object.entries(groups).find(([,terms])=>terms.some(t=>slug.includes(t)))?.[0]||'Other / unclassified';}
function type(b){const t=(b.story?.how||[]).join(' ');if(b.stealer_log)return 'Stealer logs';if(/ransomware/i.test(t))return 'Ransomware';if(/credential stuffing/i.test(t))return 'Credential stuffing';if(/scrap(?:e|ed|ing)/i.test(t))return 'Scraping';if(/vulnerab|unpatched|SQL injection/i.test(t))return 'Software vulnerability';return 'Not classified';}
function figure(route){const category=industry(route);const p=category==='Healthcare'?photos.health:['Finance & insurance','Retail'].includes(category)?photos.finance:category==='Technology'||/domain|dns|whois|server|infrastructure/.test(route)?photos.infrastructure:/social|instagram|discord|facebook|twitter|username|doublecounter|linkedin/.test(route)?photos.social:photos.research;return `<figure class="story-photo"><img src="${esc(p.image)}" alt="${esc(p.alt)}" width="1200" height="800" loading="lazy" decoding="async"><figcaption><a href="${esc(p.source)}" target="_blank" rel="noopener">${esc(p.credit)} / Unsplash</a> · ${esc(p.caption)}</figcaption></figure>`;}
function timeline(html,route){
  if(html.includes('data-story-timeline'))return html;
  const slug=path.basename(route,'.html'),b=breaches.find(b=>b.slug===slug),c=cases.find(c=>c.slug===slug);
  if(!b&&!c)return html;
  let steps=[],source='';
  if(c){
    const old=html.match(/<ol class="cf-timeline">([\s\S]*?)<\/ol>/);
    if(old){steps=[...old[1].matchAll(/<li>([\s\S]*?)<\/li>/g)].map(m=>{const title=m[1].match(/<(?:b|strong)>([\s\S]*?)<\/(?:b|strong)>/)?.[1];return [plain(title||'In the public record'),plain(m[1].replace(/<(?:b|strong)>[\s\S]*?<\/(?:b|strong)>\s*:?/,''))];});}
    if(!steps.length)steps=[['Reported incident',c.occurred||'The incident date is not established in this account.'],['Public disclosure',c.disclosed||'A separate disclosure date is not recorded.'],['Entry point',c.vector||'The entry point is not established publicly.'],['Response and consequences',c.cost||'The final outcome is not established in this record.']];
    source='<a href="#story-sources">Review the case-file sources</a>';
    html=html.replace('<h2>Sources</h2>','<h2 id="story-sources">Sources</h2>');
  }else{
    steps=[[b.name==='LinkedInScrape'?'Reported incident date':'Reported breach date',b.breach_date||'Not recorded'],['Entry point',(b.story?.how||[]).join(' ')||'The available record does not establish the entry point.'],['Discovery and disclosure','A separate discovery or company-disclosure date is not established by this feed record.'],['Added to the breach catalogue',`${b.added_date?.slice(0,10)||'Date not recorded'}. This is the catalogue date, not necessarily the disclosure date.`],['Reported outcome',(b.story?.outcome||[]).join(' ')||'A final outcome is not recorded.']];
    source=`<a href="https://haveibeenpwned.com/PwnedWebsites#${encodeURIComponent(b.name)}" target="_blank" rel="noopener">Read the HIBP source record</a>`;
  }
  const block=`<section class="story-timeline" data-story-timeline aria-labelledby="timelineHeading"><div class="story-section-heading"><span class="story-eyebrow">FOLLOW THE RECORD</span><h2 id="timelineHeading">How the story unfolded</h2><p>Open a step to read the detail. Missing dates stay unknown.</p></div><ol>${steps.map(([title,text],i)=>`<li><details${i===0?' open':''}><summary><span class="timeline-number">${String(i+1).padStart(2,'0')}</span>${esc(title)}</summary><p>${esc(text)}</p><p class="timeline-source">${source}</p></details></li>`).join('')}</ol></section>`;
  return html.replace(/(<nav class="bx-story-nav"[\s\S]*?<\/nav>)/,`$1${block}`);
}
function archive(html){
  if(html.includes('data-archive-filters'))return html;
  const rows=breaches.map(b=>({...b,industry:industry(b.slug),incident:type(b)}));
  const options=(values)=>[...new Set(values)].sort().map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  html=html.replace('<div class="bx-grid">',`<form class="archive-filters" data-archive-filters aria-label="Filter breach archive"><label>Find a service<input type="search" name="search" placeholder="Name or domain" autocomplete="off"></label><label>Year<select name="year"><option value="">All years</option>${options(rows.map(b=>b.breach_date.slice(0,4)))}</select></label><label>Industry<select name="industry"><option value="">All industries</option>${options(rows.map(b=>b.industry))}</select></label><label>Exposed data<select name="data"><option value="">All data types</option>${options(rows.flatMap(b=>b.data_classes))}</select></label><label>Incident type<select name="incident"><option value="">All incident types</option>${options(rows.map(b=>b.incident))}</select></label><button type="reset" class="btn btn-ghost btn-sm">Reset filters</button><p data-archive-count role="status" aria-live="polite">${rows.length} records</p><small>Filters cover the current feed below. Industry and incident categories are editorial groupings; unclassified records remain available.</small></form><div class="bx-grid" data-filtered-archive>`);
  html=html.replace(/<a class="bx-card" href="\/breaches\/([^"/]+)\.html">/g,(all,slug)=>{const b=rows.find(b=>b.slug===slug);return b?`<a class="bx-card" href="/breaches/${slug}.html" data-archive-card data-search="${esc(b.title+' '+b.domain)}" data-year="${b.breach_date.slice(0,4)}" data-industry="${esc(b.industry)}" data-incident="${esc(b.incident)}" data-exposed="${esc(JSON.stringify(b.data_classes))}">`:all;});
  html=html.replace('</body>','<script src="/assets/js/archive-filters.js" defer></script></body>');return html;
}
function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){if(entry.name.startsWith('.')||['assets','content','data','scripts','tests','node_modules','worker-console'].includes(entry.name))continue;const file=path.join(dir,entry.name);if(entry.isDirectory()){walk(file);continue;}if(!file.endsWith('.html'))continue;let html=fs.readFileSync(file,'utf8');const route=path.relative(root,file).replace(/\\/g,'/');const before=html;
  html=html.replace(/<figure class="story-photo">[\s\S]*?<\/figure>/g,()=>figure(route));
  if(route.startsWith('breaches/'))html=timeline(html,route);
  if(html.includes('cf-article')) {
    const c=cases.find(c=>route.endsWith('/'+c.slug+'.html'));
    if(c) html=html.replace(/<div class="story-opening">[\s\S]*?<\/div>/, `<div class="story-opening"><span class="story-eyebrow">CASE FILE</span><h2>${esc(c.subject)}</h2><p>${esc(c.description)}</p><a class="story-jump" href="#timelineHeading">Follow the timeline ↓</a></div>`);
  }
  if(route==='breaches/index.html')html=archive(html);
  // The first implementation only recognized news articles; give case files a proper opening too.
  if(html.includes('cf-article')&&!html.includes('class="story-feature"')){
    const c=cases.find(c=>route.endsWith('/'+c.slug+'.html'));if(c)html=html.replace(/(<header class="bx-head">[\s\S]*?<\/header>)/,`$1<section class="story-feature"><div class="story-opening"><span class="story-eyebrow">CASE FILE</span><h2>${esc(c.subject)}</h2><p>${esc(c.description)}</p><a class="story-jump" href="#timelineHeading">Follow the timeline ↓</a></div>${figure(route)}</section>`);
  }
  if((html.includes('story-timeline')||route==='breaches/index.html')&&!/\/assets\/(?:optimized\/)?css\/story-experience[.]/.test(html))html=html.replace('</head>','<link rel="stylesheet" href="/assets/css/story-experience.css"></head>');
  if(html!==before)fs.writeFileSync(file,html);
}}
walk(root);
console.log('[stories] Applied credited photography, source timelines and archive filters');

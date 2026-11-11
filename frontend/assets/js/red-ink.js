/* Red ink is decorative: never captures clicks, focuses fields, or starts a search. */
(() => {
  'use strict';
  if(document.querySelector('#red-ink')) return;
  const media=matchMedia('(prefers-reduced-motion: reduce)'),host=document.createElement('div');
  host.id='red-ink';host.setAttribute('aria-hidden','true');
  host.innerHTML=`<style>
  #red-ink{position:fixed;inset:0;z-index:45;pointer-events:none!important;overflow:hidden;contain:strict}#red-ink *{pointer-events:none!important}
  #red-ink canvas{position:absolute;inset:0}#red-ink svg{position:absolute;width:40px;height:40px;transform-origin:0 40px;opacity:.85}
  #red-ink .ink-hook{position:absolute;width:220px;color:#e14959;font:italic 16px/1.4 'Segoe Print','Comic Sans MS',cursive;transform:rotate(-3deg);opacity:0}#red-ink strong{display:block;font-size:17px}
  @media(prefers-reduced-motion:reduce){#red-ink{display:none}}
  </style><canvas></canvas><div class="ink-hook">Go beyond the username.<strong>Try our Deep Search</strong></div><svg class="ink-pen" viewBox="0 0 58 58" fill="none" stroke="#e14959" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"><path d="M0 58 5 43 37 10 Q40 7 43 10 L48 15 Q50 18 46 22 L14 53 0 58Z"/><path d="m5 43 9 10M8 44 39 13M12 49 44 17M35 12 45 23M0 58 4 51 7 54M42 10q4-3 7 1l3 4-12 13"/></svg>`;
  document.body.append(host);
  // Reserve a small annotation margin: the hook cannot collide with hero copy on narrow screens.
  const tool=document.querySelector('#tool'),margin=document.createElement('div');
  margin.className='ink-annotation-margin';margin.setAttribute('aria-hidden','true');
  margin.style.cssText='position:absolute;width:0;height:0;pointer-events:none';
  const originalToolMargin=tool?.style.marginTop||'';
  if(tool){tool.prepend(margin);tool.style.marginTop='92px';}

  const canvas=host.querySelector('canvas'),ctx=canvas.getContext('2d'),pen=host.querySelector('svg'),hook=host.querySelector('.ink-hook');
  const controls='#tool,#results,a,button,input,textarea,select,label,summary,header,nav,[role="dialog"],[role="button"],[contenteditable],.orbit,.promo-art,.hero-trace-tags,figure,picture,video,iframe,[role="img"],[data-ink-exclude]';
  const random=(a,b)=>a+Math.random()*(b-a),pt=(x,y)=>({x,y});
  let nib=pt(innerWidth-45,150),marks=[],job=null,roam=null,blocks=[],textBoxes=[],raf=0,lastScroll=-9999,next=performance.now()+1400,roamNext=0,lastZone=-1,lastShape=-1,refresh=0,engaged=false,hinted=false,park=null,hintRead=0,lastFrame=performance.now(),shapeBag=[];
  const used=new WeakMap();
  let handwriting=null,lastDoodle=-1;
  const overlap=(a,b,p=0)=>a.left<b.right+p&&a.right>b.left-p&&a.top<b.bottom+p&&a.bottom>b.top-p;
  const blocked=r=>blocks.some(b=>overlap(r,b,14));
  const penBounds=p=>({left:p.x-7,right:p.x+44,top:p.y-48,bottom:p.y+8});
  const safe=p=>p.x>=8&&p.x<=innerWidth-46&&p.y>=85&&p.y<=innerHeight-12&&!blocked(penBounds(p))&&(job?.m.word||!textBoxes.some(r=>overlap(penBounds(p),r,5)));
  function nearestSafe(p){
    if(safe(p))return p;
    let best=null,distance=Infinity;
    for(let y=90;y<innerHeight-12;y+=24)for(let x=8;x<innerWidth-46;x+=24){const q=pt(x,y),d=Math.hypot(x-p.x,y-p.y);if(d<distance&&safe(q)){best=q;distance=d;}}
    return best;
  }
  function travel(from,to,allowed=safe,bends=[25,-25,65,-65,120,-120,0]){
    if(!allowed(to))return null;
    // Try flowing arcs first, then route through clear spaces between controls.
    for(const bend of bends){
      const dx=to.x-from.x,dy=to.y-from.y,length=Math.hypot(dx,dy)||1;
      const path=Array.from({length:65},(_,i)=>{const t=i/64,b=Math.sin(Math.PI*t)*bend;return pt(from.x+dx*t-dy/length*b,from.y+dy*t+dx/length*b);});
      if(path.every(allowed))return path;
    }
    const nodes=[from,to];
    for(let y=90;y<innerHeight-12;y+=32)for(let x=8;x<innerWidth-46;x+=32){const p=pt(x,y);if(allowed(p))nodes.push(p);}
    for(let y=90;y<innerHeight-12;y+=32)for(const x of [12,innerWidth-12]){const p=pt(x,y);if(allowed(p))nodes.push(p);}
    const clear=(a,b)=>{const n=Math.ceil(Math.hypot(b.x-a.x,b.y-a.y)/8);for(let i=0;i<=n;i++)if(!allowed(pt(a.x+(b.x-a.x)*i/(n||1),a.y+(b.y-a.y)*i/(n||1))))return false;return true;};
    const queue=[0],previous=new Map([[0,-1]]);
    for(let k=0;k<queue.length;k++){
      const index=queue[k],a=nodes[index];
      if(clear(a,to)){previous.set(1,index);let path=[],at=1;while(at!==-1){path.unshift(nodes[at]);at=previous.get(at);}return path;}
      for(let i=2;i<nodes.length;i++)if(!previous.has(i)&&Math.hypot(nodes[i].x-a.x,nodes[i].y-a.y)<(index===0?64:46)&&clear(a,nodes[i])){previous.set(i,index);queue.push(i);}
    }
    return null;
  }
  function along(path,t){
    const lengths=path.slice(1).map((p,i)=>Math.hypot(p.x-path[i].x,p.y-path[i].y));let distance=lengths.reduce((a,b)=>a+b,0)*t;
    for(let i=0;i<lengths.length;i++){if(distance<=lengths[i]){const f=distance/(lengths[i]||1);return pt(path[i].x+(path[i+1].x-path[i].x)*f,path[i].y+(path[i+1].y-path[i].y)*f);}distance-=lengths[i];}
    return path.at(-1);
  }
  function noteBounds(m,o){return {left:o.x+m.note.x-5,right:o.x+m.note.x+215,top:o.y+m.note.y-5,bottom:o.y+m.note.y+30};}
  function occupied(r,except){return marks.some(m=>{
    if(m===except)return false;const o=origin(m);if(!o)return false;
    const cue=m.cue&&{left:o.x+m.cue.x,right:o.x+m.cue.x+220,top:o.y+m.cue.y,bottom:o.y+m.cue.y+49};
    return overlap(r,bounds(m.lines,o),12)||(m.note&&overlap(r,noteBounds(m,o),10))||(cue&&overlap(r,cue,8));
  });}
  function bounds(lines,o,p=6){const points=lines.flat(),xs=points.map(v=>v.x+o.x),ys=points.map(v=>v.y+o.y);return {left:Math.min(...xs)-p,right:Math.max(...xs)+p,top:Math.min(...ys)-p,bottom:Math.max(...ys)+p};}
  function origin(m){if(!m.anchor.isConnected)return null;const r=m.anchor.getBoundingClientRect();return r.width&&r.height?pt(r.left,r.top):null;}
  function resize(){const d=Math.min(devicePixelRatio||1,2);canvas.width=innerWidth*d;canvas.height=innerHeight*d;canvas.style.width=innerWidth+'px';canvas.style.height=innerHeight+'px';ctx.setTransform(d,0,0,d,0,0);marks=[];job=null;roam=null;refresh=0;}
  function measure(){const rect=el=>Object.assign(el.getBoundingClientRect(),{inkElement:el});blocks=[...document.querySelectorAll(controls)].map(rect).filter(r=>r.width&&r.height&&r.bottom>0&&r.top<innerHeight);textBoxes=[...document.querySelectorAll('h1,h2,h3,p,li,img,video,.lookup-intent-note')].map(rect).filter(r=>r.width&&r.height&&r.bottom>0&&r.top<innerHeight);}
  function paintWriting(){
    if(!handwriting)return;
    const angle=(handwriting.vertical?-45:45)+(handwriting.lifted?1:Math.sin(performance.now()/170)*1.5);
    pen.style.opacity='.95';pen.style.transform=`translate(${nib.x}px,${nib.y-40}px) rotate(${angle}deg) scale(.78)`;
    host.dataset.mode=(handwriting.excursion?'doodle':'headline')+(handwriting.lifted?'-lift':'-writing');
    pen.dataset.tipX=String(nib.x);pen.dataset.tipY=String(nib.y);
  }
  // One pen coordinates headline writing, lifted travel, and short doodle trips.
  window.MyReconPen={claim(owner){
    if(media.matches||document.hidden)return null;
    if(handwriting)return handwriting.owner===owner?handwriting.api:null;
    measure();
    const departure=new Set(textBoxes.filter(r=>overlap(penBounds(nib),r)).map(r=>r.inkElement));
    nib.x=Math.max(8,Math.min(innerWidth-49,nib.x));
    const state={owner,lifted:true,active:true,api:null};handwriting=state;
    job=null;roam=null;
    const allowed=p=>{
      const b=state.vertical?{left:p.x-6,right:p.x+6,top:p.y-42,bottom:p.y+4}:{left:p.x-3,right:p.x+45,top:p.y-8,bottom:p.y+4};
      const outside=r=>r.inkElement!==owner&&!owner.contains(r.inkElement);
      return b.left>=2&&b.right<=innerWidth-2&&b.top>=0&&b.bottom<=innerHeight-2&&!blocks.some(r=>outside(r)&&overlap(b,r,3))&&!textBoxes.some(r=>outside(r)&&!departure.has(r.inkElement)&&overlap(b,r,2))&&(!state.excursion||!occupied(b,state.mark));
    };
    const api={
      get active(){return state.active;},
      move(p,lifted=false){if(!state.active||!allowed(p))return false;nib={...p};state.lifted=lifted;paintWriting();return true;},
      async travelTo(target,{signal,duration}={}){
        if(!state.active||signal?.aborted)return Promise.resolve(false);
        const distance=Math.hypot(target.x-nib.x,target.y-nib.y),bend=Math.min(22,distance*.12);
        state.vertical=distance>80||(state.excursion&&innerWidth<600);
        const header=document.querySelector('header')?.getBoundingClientRect();
        const landing=state.vertical?pt(target.x,Math.max(target.y,(header?.bottom||0)+48)):target;
        const route=travel(nib,landing,allowed,[bend,-bend,0,65,-65]);
        if(!route)return Promise.resolve(false);
        const ms=duration??Math.max(45,Math.min(750,distance*1.7));
        const arrived=await new Promise(resolve=>{
          let frame=0,start=null,done=false;
          const finish=value=>{if(done)return;done=true;cancelAnimationFrame(frame);signal?.removeEventListener('abort',abort);resolve(value);};
          const abort=()=>finish(false);signal?.addEventListener('abort',abort,{once:true});
          const step=now=>{if(!state.active||signal?.aborted){finish(false);return;}start??=now;const t=Math.min(1,(now-start)/ms),e=t*t*(3-2*t);if(!api.move(along(route,e),true)){finish(false);return;}if(t===1)finish(true);else frame=requestAnimationFrame(step);};
          frame=requestAnimationFrame(step);
        });
        if(!arrived)return false;
        state.vertical=state.excursion&&innerWidth<600;
        if(Math.hypot(landing.x-target.x,landing.y-target.y)>1)return api.travelTo(target,{signal,duration:110});
        return api.move(target,true);
      },
      async excursion({signal}={}){
        if(!state.active||signal?.aborted||engaged)return false;
        state.excursion=true;state.lifted=true;state.vertical=false;measure();
        marks=marks.filter(mark=>performance.now()-mark.born<(mark.life||24000));
        let m=null;
        try{
          m=doodle(true);
          if(!m){
            state.vertical=true;const heading=owner.getBoundingClientRect(),destinations=[];
            for(let y=122;y<innerHeight-30;y+=32)for(const x of [8,innerWidth-8,innerWidth*.28,innerWidth*.72]){
              const p=pt(x,y),distance=Math.hypot(p.x-nib.x,p.y-nib.y);
              if(distance>100&&allowed(p)&&!(p.x>=heading.left&&p.x<=heading.right&&p.y>=heading.top&&p.y<=heading.bottom))destinations.push(p);
            }
            destinations.sort(()=>Math.random()-.5);
            for(const p of destinations.slice(0,6))if(await api.travelTo(p,{signal,duration:1100}))return true;
            return false;
          }
          m.compact=true;m.life=6500;m.fade=3000;m.born=performance.now();m.drawn=[];state.mark=m;marks.push(m);
          for(const raw of m.lines){
            const o=origin(m);if(!o)return false;
            const line=raw.flatMap((p,i)=>{if(!i)return [p];const a=raw[i-1],n=Math.max(1,Math.ceil(Math.hypot(p.x-a.x,p.y-a.y)));return Array.from({length:n},(_,k)=>pt(a.x+(p.x-a.x)*(k+1)/n,a.y+(p.y-a.y)*(k+1)/n));});
            if(!await api.travelTo(pt(o.x+line[0].x,o.y+line[0].y),{signal}))return false;
            const drawn=[];m.drawn.push(drawn);
            const duration=Math.max(120,Math.min(520,line.length/0.22));
            const complete=await new Promise(resolve=>{
              let frame=0,start=null,index=0,done=false;
              const finish=value=>{if(done)return;done=true;cancelAnimationFrame(frame);signal?.removeEventListener('abort',abort);resolve(value);};
              const abort=()=>finish(false);signal?.addEventListener('abort',abort,{once:true});
              const step=now=>{
                if(!state.active||signal?.aborted){finish(false);return;}start??=now;
                const t=Math.min(1,(now-start)/duration),progress=t+Math.sin(t*Math.PI*2)*.018,end=Math.min(line.length-1,Math.floor(progress*(line.length-1))),at=origin(m);
                if(!at){finish(false);return;}
                const previous=drawn.at(-1)||line[0];ctx.beginPath();ctx.moveTo(at.x+previous.x,at.y+previous.y);
                for(;index<=end;index++){const p=line[index];drawn.push(p);ctx.lineTo(at.x+p.x,at.y+p.y);}
                const p=drawn.at(-1)||line[0];
                if(!api.move(pt(at.x+p.x,at.y+p.y))){finish(false);return;}
                ctx.globalAlpha=m.alpha;ctx.strokeStyle='#e14959';ctx.lineWidth=m.width;ctx.lineCap=ctx.lineJoin='round';ctx.stroke();
                host.dataset.inkX=String(at.x+p.x);host.dataset.inkY=String(at.y+p.y);
                if(t===1)finish(true);else frame=requestAnimationFrame(step);
              };
              frame=requestAnimationFrame(step);
            });
            if(!complete)return false;
          }
          host.dataset.doodleCount=String((Number(host.dataset.doodleCount)||0)+1);
          state.lifted=true;
          const rest=pt(Math.min(innerWidth-49,nib.x+random(12,28)),nib.y+random(-12,12));
          await api.travelTo(rest,{signal,duration:280});return !signal?.aborted;
        }finally{
          if(m&&!m.drawn.some(line=>line.length))marks=marks.filter(mark=>mark!==m);
          state.mark=null;state.excursion=false;state.lifted=true;paintWriting();
        }
      },
      release(){if(!state.active)return;state.active=false;if(handwriting===state)handwriting=null;next=performance.now()+1600;refresh=0;}
    };
    state.api=api;return api;
  }};
  function hint(){
    if(hintRead>=14000||marks.some(m=>m.cue))return null;
    const anchor=document.querySelector('#tab-deepsearch');
    if(!anchor||!margin.isConnected)return null;
    const r=anchor.getBoundingClientRect(),space=margin.getBoundingClientRect();
    if(!r.width||r.top<165||r.top>innerHeight-45||r.left<0||r.right>innerWidth)return null;
    const x=r.width/2,left=Math.max(16,Math.min(innerWidth-236,r.left+x-70));
    const labelY=r.top-100,label={left,right:left+220,top:labelY,bottom:labelY+49};
    if(label.top<85||blocked(label))return null;
    const sx=left+155-r.left,sy=labelY+55-r.top;
    return {anchor,alpha:.9,width:1.8,cue:{x:left-r.left,y:labelY-r.top},lines:[Array.from({length:65},(_,i)=>{const t=i/64;return pt(sx+(x-sx)*t,sy+(-33-sy)*t-Math.sin(t*Math.PI)*5);}),[pt(x-7,-42),pt(x,-33),pt(x+8,-41)]]};
  }
  function wordMark(){
    const choices=[];
    for(const el of document.querySelectorAll('main h1,main h2,main h3,main p')){
      const rect=el.getBoundingClientRect();if(rect.top>innerHeight-60||rect.bottom<110||el.closest('#tool,'+controls))continue;
      const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node;
      while((node=walker.nextNode())){
        if(node.parentElement.closest(controls))continue;
        for(const match of node.textContent.matchAll(/[A-Za-z]{5,}/g)){
          if(used.get(node)?.has(match.index)||! /^(search|username|footprint|profiles?|public|accounts?|sources?|discover|investigate|connections?|mentions)$/i.test(match[0]))continue;
          const range=document.createRange();range.setStart(node,match.index);range.setEnd(node,match.index+match[0].length);const r=range.getBoundingClientRect();
          if(r.top<110||r.bottom>innerHeight-55||r.left<16||r.right>innerWidth-45||blocked(r))continue;
          if(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)?.closest('h1,h2,h3,p')!==el)continue;
          choices.push({anchor:el,node,key:match.index,x:r.left-rect.left,y:r.top-rect.top,w:r.width,h:r.height});
        }
      }
    }
    if(!choices.length)return null;
    // Prefer a different area, instead of continually revisiting the hero paragraph.
    choices.sort((a,b)=>{const ra=a.anchor.getBoundingClientRect(),rb=b.anchor.getBoundingClientRect();return Math.hypot(rb.left+b.x-nib.x,rb.top+b.y-nib.y)-Math.hypot(ra.left+a.x-nib.x,ra.top+a.y-nib.y);});
    const w=choices[Math.floor(random(0,Math.min(5,choices.length)))],{x,y,h}=w;
    const shape=(lastShape+1+Math.floor(random(0,3)))%4;lastShape=shape;let lines,alpha=.6,width=1.5;
    if(shape===0)lines=[Array.from({length:90},(_,i)=>{const t=i/89*Math.PI*2.1;return pt(x+w.w/2+Math.cos(t)*(w.w/2+6)+Math.sin(t*5),y+h/2+Math.sin(t)*(h/2+5));})];
    else if(shape===1){alpha=.15;width=3;lines=[Array.from({length:Math.max(14,Math.ceil(w.w/3))},(_,i)=>pt(x+i*3,y+h*(i%2?.8:.25)+random(-1,1)))];}
    else{const line=d=>Array.from({length:40},(_,i)=>pt(x-2+i*(w.w+4)/39,y+h+d+Math.sin(i*.34)*1.3));lines=[line(3)];if(shape===3)lines.push(line(7));}
    return {anchor:w.anchor,word:w,lines,alpha,width};
  }
  function doodle(compact=false){
    const candidates=[];
    if(compact){for(let y=115;y<innerHeight-55;y+=12)for(let x=22;x<innerWidth-65;x+=12)candidates.push(pt(x,y));for(let i=candidates.length-1;i>0;i--){const j=Math.floor(random(0,i+1));[candidates[i],candidates[j]]=[candidates[j],candidates[i]];}}
    for(let attempt=0;attempt<(compact?60+candidates.length:60);attempt++){
      const candidate=compact&&attempt>=60?candidates[attempt-60]:pt(random(22,Math.max(23,innerWidth-110)),random(115,Math.max(116,innerHeight-80)));
      const {x,y}=candidate;
      const anchor=document.elementFromPoint(x,y);if(!anchor||anchor.closest(controls+',#tool'))continue;
      const r=anchor.getBoundingClientRect(),ox=x-r.left,oy=y-r.top;
      if(!shapeBag.length){shapeBag=[0,1,2,3,4].sort(()=>Math.random()-.5);if(shapeBag[0]===lastDoodle)[shapeBag[0],shapeBag[1]]=[shapeBag[1],shapeBag[0]];}
      const shape=shapeBag[compact?Math.floor(attempt/60)%shapeBag.length:0];
      const circle=(cx,cy,r)=>Array.from({length:65},(_,i)=>{const t=i/64*Math.PI*2.04;return pt(cx+Math.cos(t)*(r+Math.sin(t*3)*.5),cy+Math.sin(t)*r);});
      let lines,caption;
      if(shape===0){lines=[circle(18,18,16),[pt(30,30),pt(48,49)],[pt(8,14),pt(10,10),pt(15,7)]];caption='What will you find?';}
      if(shape===1){lines=[Array.from({length:45},(_,i)=>{const t=i/44*Math.PI*1.45;return pt(19+Math.cos(t+Math.PI)*13,15+Math.sin(t+Math.PI)*12);}),[pt(27,26),pt(20,32),pt(20,38)],circle(20,47,1.5)];caption='Where does your handle lead?';}
      if(shape===2){lines=[circle(7,12,7),[pt(14,15),pt(33,26)],circle(40,30,8),[pt(46,24),pt(62,7)],circle(67,2,6)];caption='Connect the public clues.';}
      if(shape===3){lines=[circle(24,11,9),Array.from({length:35},(_,i)=>{const t=Math.PI+i/34*Math.PI;return pt(24+Math.cos(t)*21,44+Math.sin(t)*16);}),[pt(3,44),pt(45,44)]];caption='Find your public footprint.';}
      if(shape===4){lines=[[pt(0,8),pt(0,44),pt(52,44),pt(52,8),pt(27,8),pt(22,1),pt(0,1),pt(0,8)],[pt(12,21),pt(38,21)],[pt(12,29),pt(30,29)]];caption='Follow a lead. Check the source.';}
      const angle=random(-.16,.16),scale=compact?(innerWidth<360?random(.42,.58):random(.52,.72)):random(.8,1.05);
      lines=lines.map(l=>l.map(p=>pt(ox+(p.x*Math.cos(angle)-p.y*Math.sin(angle))*scale,oy+(p.x*Math.sin(angle)+p.y*Math.cos(angle))*scale)));
      const b=bounds(lines,pt(r.left,r.top));if(blocked(b)||occupied(b)||textBoxes.some(t=>overlap(b,t,8))||b.left<10||b.right>innerWidth-20||b.top<90||b.bottom>innerHeight-20)continue;
      if(compact){const space=innerWidth<600?{left:b.left-6,right:b.right+6,top:b.top-42,bottom:b.bottom+4}:{left:b.left-3,right:b.right+45,top:b.top-8,bottom:b.bottom+4};if(blocked(space)||occupied(space)||textBoxes.some(t=>overlap(space,t,5)))continue;}
      const note={left:x-9,right:x+215,top:y+53,bottom:y+88};
      const showCaption=!blocked(note)&&!occupied(note)&&!textBoxes.some(t=>overlap(note,t,8))&&note.right<innerWidth-15&&note.bottom<innerHeight-15;
      shapeBag.splice(shapeBag.indexOf(shape),1);lastDoodle=shape;host.dataset.drawing=['magnifier','question','connections','profile','case-file'][shape];
      return {anchor,lines,alpha:compact?.5:.65,width:compact?1.35:1.6,note:!compact&&showCaption?{x:ox-4,y:oy+58,text:caption}:null};
    }
    return null;
  }
  function plan(now,scrolling){
    const m=(!scrolling&&hint())||(!scrolling&&Math.random()<.3&&wordMark())||doodle();
    if(!m){next=now+1300;return;}
    const o=origin(m),b=bounds(m.lines,o);if(blocked(b)){next=now+1000;return;}
    if(m.cue){host.dataset.mode='deep-search';}
    if(m.word){if(!used.has(m.word.node))used.set(m.word.node,new Set());used.get(m.word.node).add(m.word.key);}
    m.lines=m.lines.map(line=>line.flatMap((p,i)=>{if(!i)return [p];const a=line[i-1],n=Math.max(1,Math.ceil(Math.hypot(p.x-a.x,p.y-a.y)));return Array.from({length:n},(_,k)=>pt(a.x+(p.x-a.x)*(k+1)/n,a.y+(p.y-a.y)*(k+1)/n));}));
    m.born=now;m.drawn=[];marks.push(m);if(marks.length>12)marks.shift();roam=null;
    job={m,line:0,index:0,lift:true,from:{...nib},start:now,duration:random(700,1400)};
  }
  function wander(now){
    if(!roam&&now>roamNext){
      const zone=(lastZone+1+Math.floor(random(0,3)))%4;lastZone=zone;
      for(let i=0;i<40;i++){
        const x=random(20,Math.max(21,innerWidth-50)),y=random(110,Math.max(111,innerHeight-40));
        if((x>innerWidth/2?1:0)+(y>innerHeight/2?2:0)!==zone||!safe(pt(x,y)))continue;
        const route=travel(nib,pt(x,y));if(!route)continue;
        roam={route,start:now,duration:random(2000,3600)};break;
      }
      if(!roam)roamNext=now+600;
    }
    if(roam){const t=Math.min(1,(now-roam.start)/roam.duration),e=t*t*(3-2*t);nib=along(roam.route,e);if(t===1){roam=null;roamNext=now+random(200,900);}}
  }
  function tick(now){
    if(media.matches||document.hidden){raf=0;return;}
    const dt=Math.min(60,now-lastFrame);lastFrame=now;
    const scrolling=now-lastScroll<240;
    if(now>refresh){measure();refresh=now+180;}
    ctx.clearRect(0,0,innerWidth,innerHeight);hook.style.opacity='0';
    if(handwriting&&!scrolling&&hintRead<14000&&!marks.some(m=>m.cue)){const cue=hint();if(cue)marks.push({...cue,born:now,drawn:cue.lines});}
    if(!handwriting&&!job&&!engaged&&!scrolling&&hintRead<14000&&!marks.some(m=>m.cue)&&hint())next=Math.min(next,now);
    marks=marks.filter(m=>now-m.born<(m.life||24000)&&origin(m));let lifted=true;
    if(!handwriting&&job){
      const j=job,o=origin(j.m),line=j.m.lines[j.line];
      if(!o||((j.m.word||j.m.cue)&&scrolling)||o.y+line[0].y<80||o.y+line[0].y>innerHeight-15){if(j.m.cue)marks=marks.filter(m=>m!==j.m);job=null;next=now+800;}
      else{
        const t=Math.min(1,(now-j.start)/j.duration);
        if(j.lift){
          const target=pt(o.x+line[0].x,o.y+line[0].y);
          if(!j.route||Math.hypot(target.x-j.route.at(-1).x,target.y-j.route.at(-1).y)>8){j.route=travel(nib,target);j.start=now;}
          if(!j.route){marks=marks.filter(m=>m!==j.m);job=null;next=now+1800;}
          else{const progress=Math.min(1,(now-j.start)/j.duration),e=progress*progress*(3-2*progress);nib=along(j.route,e);if(progress===1){j.lift=false;j.route=null;j.start=now;j.duration=random(600,1300);j.m.drawn.push([]);}}
        }
        else{lifted=false;const end=Math.min(line.length-1,Math.floor((t+Math.sin(t*Math.PI*4)*.018)*(line.length-1))),drawn=j.m.drawn.at(-1);for(;j.index<=end;j.index++)drawn.push(line[j.index]);const p=drawn.at(-1)||line[0];nib=pt(o.x+p.x,o.y+p.y);if(t===1){j.line++;if(j.line===j.m.lines.length){job=null;next=now+random(4500,9500);}else{j.lift=true;j.from={...nib};j.start=now;j.duration=random(200,400);j.index=0;}}}
      }
    }else if(!handwriting&&!engaged){if(now>next)plan(now,scrolling);if(!job)wander(now);}
    for(const m of marks){const o=origin(m);if(!m.word&&!m.cue&&(blocked(bounds(m.lines,o))||textBoxes.some(t=>overlap(bounds(m.lines,o),t,8))||(m.compact&&occupied(bounds(m.lines,o),m))))continue;const fade=Math.min(1,Math.max(0,((m.life||24000)-(now-m.born))/(m.fade||11000)));ctx.globalAlpha=m.alpha*fade;ctx.strokeStyle='#e14959';ctx.lineWidth=m.width;ctx.lineCap='round';ctx.lineJoin='round';for(const line of m.drawn){ctx.beginPath();line.forEach((p,i)=>ctx[i?'lineTo':'moveTo'](o.x+p.x,o.y+p.y));ctx.stroke();}
      if(m.note&&m.drawn.length===m.lines.length&&!blocked(noteBounds(m,o))&&!occupied(noteBounds(m,o),m)&&!textBoxes.some(t=>overlap(noteBounds(m,o),t,8))){ctx.font="italic 14px 'Segoe Print', cursive";ctx.fillStyle='#e14959';ctx.globalAlpha=.7*fade;ctx.fillText(m.note.text,o.x+m.note.x,o.y+m.note.y+14,210);}
      if(m.cue&&!scrolling){const x=o.x+m.cue.x,y=o.y+m.cue.y,b={left:x,right:x+220,top:y,bottom:y+49};if(y>85&&y+49<innerHeight&&!blocked(b)){
        hook.style.left=x+'px';hook.style.top=y+'px';hook.style.opacity=String(Math.min(1,(now-m.born)/450,Math.max(0,(16000-hintRead)/2000)));
        hintRead+=dt;host.dataset.hintVisible='true';
      }}
    }
    for(const b of blocks)ctx.clearRect(b.left-14,b.top-14,b.width+28,b.height+28);
    if(handwriting){paintWriting();raf=requestAnimationFrame(tick);return;}
    if(engaged&&park){if(park.route){const t=Math.min(1,(now-park.start)/1200),e=t*t*(3-2*t);nib=along(park.route,e);}}
    nib.x=Math.max(8,Math.min(innerWidth-33,nib.x));nib.y=Math.max(80,Math.min(innerHeight-12,nib.y));
    if(!safe(nib)){const clear=nearestSafe(nib);if(clear)nib=clear;job=null;roam=null;next=now+1500;}
    pen.style.opacity='.9';pen.style.transform=`translate(${nib.x}px,${nib.y-40}px) rotate(${(engaged?0:Math.sin(now/800)*4)+(lifted?8:0)}deg) scale(${lifted?1.06:1})`;
    raf=requestAnimationFrame(tick);
  }
  function yieldToVisitor(e){if(!e.target.closest?.('#tool,#results,[role="dialog"]')||engaged)return;engaged=true;marks=[];job=null;roam=null;const target=nearestSafe(pt(innerWidth-54,125));park={route:target&&travel(nib,target),start:performance.now()};host.dataset.mode='resting';}
  for(const event of ['focusin','input','pointerdown'])document.addEventListener(event,yieldToVisitor);
  function resume(){host.hidden=media.matches;margin.hidden=media.matches;if(tool)tool.style.marginTop=media.matches?originalToolMargin:'92px';lastFrame=performance.now();if(!media.matches&&!document.hidden&&!raf)raf=requestAnimationFrame(tick);}
  addEventListener('scroll',()=>{lastScroll=performance.now();refresh=0;if(!job)next=Math.min(next,lastScroll+300);},{passive:true});
  addEventListener('resize',resize,{passive:true});
  const layoutObserver=new ResizeObserver(()=>{refresh=0;});layoutObserver.observe(document.body);
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;job=null;roam=null;}else resume();});
  media.addEventListener('change',()=>{marks=[];job=null;roam=null;resume();});
  resize();resume();
})();

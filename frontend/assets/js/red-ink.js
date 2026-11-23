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
  const tool=document.querySelector('#tool');

  const canvas=host.querySelector('canvas'),ctx=canvas.getContext('2d'),pen=host.querySelector('svg'),hook=host.querySelector('.ink-hook');
  const controls='#tool,#results,a,button,input,textarea,select,label,summary,header,nav,[role="dialog"],[role="button"],[contenteditable],.orbit,.promo-art,.hero-trace-tags,figure,picture,video,iframe,[role="img"],[data-ink-exclude]';
  const random=(a,b)=>a+Math.random()*(b-a),pt=(x,y)=>({x,y});
  let nib=pt(innerWidth-45,150),marks=[],blocks=[],textBoxes=[],raf=0,lastScroll=-9999,refresh=0,engaged=false,park=null,hintRead=0,lastFrame=performance.now();
  let handwriting=null,cueDrawn=false;
  const ease=t=>t*t*t*(10+t*(-15+6*t));
  function curve(a,b,c,d){return Array.from({length:65},(_,i)=>{const t=i/64,u=1-t;return pt(u*u*u*a.x+3*u*u*t*b.x+3*u*t*t*c.x+t*t*t*d.x,u*u*u*a.y+3*u*u*t*b.y+3*u*t*t*c.y+t*t*t*d.y);});}
  function arrow(a,b,c,tip,size=9){
    const shaft=curve(a,b,c,tip),dx=tip.x-c.x,dy=tip.y-c.y,length=Math.hypot(dx,dy)||1,ux=dx/length,uy=dy/length,wing=size*.52;
    const left=pt(tip.x-ux*size-uy*wing,tip.y-uy*size+ux*wing),right=pt(tip.x-ux*size+uy*wing,tip.y-uy*size-ux*wing);
    return [shaft,[left,{...tip},right]];
  }
  function pause(ms,signal){return new Promise(resolve=>{if(signal?.aborted){resolve(false);return;}const finish=ok=>{clearTimeout(timer);signal?.removeEventListener('abort',abort);resolve(ok);},abort=()=>finish(false),timer=setTimeout(()=>finish(true),ms);signal?.addEventListener('abort',abort,{once:true});});}
  const overlap=(a,b,p=0)=>a.left<b.right+p&&a.right>b.left-p&&a.top<b.bottom+p&&a.bottom>b.top-p;
  const blocked=r=>blocks.some(b=>overlap(r,b,14));
  const penBounds=p=>({left:p.x-7,right:p.x+44,top:p.y-48,bottom:p.y+8});
  const safe=p=>p.x>=8&&p.x<=innerWidth-46&&p.y>=85&&p.y<=innerHeight-12&&!blocked(penBounds(p))&&!textBoxes.some(r=>overlap(penBounds(p),r,5));
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
    const nodes=[from,to],ys=[];
    for(let y=90;y<innerHeight-12;y+=32)ys.push(y);
    if(to.y>=90&&to.y<innerHeight-12&&!ys.includes(to.y))ys.push(to.y);
    for(const y of ys)for(let x=8;x<innerWidth-46;x+=32){const p=pt(x,y);if(allowed(p))nodes.push(p);}
    for(const y of ys)for(const x of [8,innerWidth-8]){const p=pt(x,y);if(allowed(p))nodes.push(p);}
    const clear=(a,b)=>{const n=Math.ceil(Math.hypot(b.x-a.x,b.y-a.y)/8);for(let i=0;i<=n;i++)if(!allowed(pt(a.x+(b.x-a.x)*i/(n||1),a.y+(b.y-a.y)*i/(n||1))))return false;return true;};
    const queue=[0],previous=new Map([[0,-1]]);
    for(let k=0;k<queue.length;k++){
      const index=queue[k],a=nodes[index];
      if(clear(a,to)){
        previous.set(1,index);let path=[],at=1;while(at!==-1){path.unshift(nodes[at]);at=previous.get(at);}
        const short=[path[0]];at=0;
        while(at<path.length-1){let end=path.length-1;while(end>at+1&&!clear(path[at],path[end]))end--;short.push(path[end]);at=end;}
        const rounded=[short[0]];
        for(let i=1;i<short.length-1;i++){
          const a=short[i-1],b=short[i],c=short[i+1],before=Math.hypot(b.x-a.x,b.y-a.y),after=Math.hypot(c.x-b.x,c.y-b.y);let arc=null;
          if(before<.01||after<.01){rounded.push(b);continue;}
          for(const radius of [18,10,5]){const r=Math.min(radius,before/3,after/3),p=pt(b.x+(a.x-b.x)*r/before,b.y+(a.y-b.y)*r/before),q=pt(b.x+(c.x-b.x)*r/after,b.y+(c.y-b.y)*r/after);const points=Array.from({length:13},(_,j)=>{const t=j/12,u=1-t;return pt(u*u*p.x+2*u*t*b.x+t*t*q.x,u*u*p.y+2*u*t*b.y+t*t*q.y);});if(points.every(allowed)){arc=points;break;}}
          rounded.push(...(arc||[b]));
        }
        rounded.push(short.at(-1));return rounded;
      }
      for(let i=2;i<nodes.length;i++)if(!previous.has(i)&&Math.hypot(nodes[i].x-a.x,nodes[i].y-a.y)<(index===0?64:46)&&clear(a,nodes[i])){previous.set(i,index);queue.push(i);}
    }
    return null;
  }
  function along(path,t){
    const lengths=path.slice(1).map((p,i)=>Math.hypot(p.x-path[i].x,p.y-path[i].y));let distance=lengths.reduce((a,b)=>a+b,0)*t;
    for(let i=0;i<lengths.length;i++){if(distance<=lengths[i]){const f=distance/(lengths[i]||1);return pt(path[i].x+(path[i+1].x-path[i].x)*f,path[i].y+(path[i+1].y-path[i].y)*f);}distance-=lengths[i];}
    return path.at(-1);
  }
  function occupied(r,except){return marks.some(m=>{
    if(m===except)return false;const o=origin(m);if(!o)return false;
    const cue=m.cue&&hintRead<16000&&{left:o.x+m.cue.x,right:o.x+m.cue.x+220,top:o.y+m.cue.y,bottom:o.y+m.cue.y+49};
    return overlap(r,bounds(m.lines,o),12)||(cue&&overlap(r,cue,8));
  });}
  function bounds(lines,o,p=6){const points=lines.flat(),xs=points.map(v=>v.x+o.x),ys=points.map(v=>v.y+o.y);return {left:Math.min(...xs)-p,right:Math.max(...xs)+p,top:Math.min(...ys)-p,bottom:Math.max(...ys)+p};}
  function origin(m){if(!m.anchor.isConnected)return null;const r=m.anchor.getBoundingClientRect();return r.width&&r.height?pt(r.left,r.top):null;}
  function resize(){const d=Math.min(devicePixelRatio||1,2);canvas.width=innerWidth*d;canvas.height=innerHeight*d;canvas.style.width=innerWidth+'px';canvas.style.height=innerHeight+'px';ctx.setTransform(d,0,0,d,0,0);marks=[];refresh=0;}
  function measure(){const rect=el=>Object.assign(el.getBoundingClientRect(),{inkElement:el});blocks=[...document.querySelectorAll(controls)].map(rect).filter(r=>r.width&&r.height&&r.bottom>0&&r.top<innerHeight);textBoxes=[...document.querySelectorAll('h1,h2,h3,p,li,img,video,.lookup-intent-note')].map(rect).filter(r=>r.width&&r.height&&r.bottom>0&&r.top<innerHeight);}
  function paintWriting(){
    if(!handwriting)return;
    const tilt=handwriting.sidePen?.7:handwriting.lifted?1.8:1.2;
    const angle=(handwriting.sidePen?135:handwriting.vertical?-45:handwriting.guide?50:45)+Math.sin(performance.now()/(handwriting.lifted?650:280))*tilt;
    pen.style.opacity='.95';pen.style.transform=`translate(${nib.x}px,${nib.y-40}px) rotate(${angle}deg) scale(${handwriting.sidePen?.58:.78})`;
    host.dataset.mode=(handwriting.guide?'deep-search':'headline')+(handwriting.lifted?'-lift':'-writing');
    pen.dataset.tipX=String(nib.x);pen.dataset.tipY=String(nib.y);
  }
  // One pen coordinates headline writing, lifted travel, and the Deep Search callout arrow.
  window.MyReconPen={claim(owner){
    if(media.matches||document.hidden)return null;
    if(handwriting)return handwriting.owner===owner?handwriting.api:null;
    measure();
    const departure=new Set(textBoxes.filter(r=>overlap(penBounds(nib),r)).map(r=>r.inkElement));
    nib.x=Math.max(8,Math.min(innerWidth-49,nib.x));
    const state={owner,lifted:true,active:true,api:null};handwriting=state;
    const allowed=p=>{
      const b=state.sidePen?{left:p.x-4,right:p.x+4,top:p.y-3,bottom:p.y+28}:state.vertical?{left:p.x-6,right:p.x+6,top:p.y-42,bottom:p.y+4}:state.guide?{left:p.x-3,right:p.x+45,top:p.y-4,bottom:p.y+5}:{left:p.x-3,right:p.x+45,top:p.y-8,bottom:p.y+4};
      const outside=r=>r.inkElement!==owner&&!owner.contains(r.inkElement);
      return b.left>=2&&b.right<=innerWidth-2&&b.top>=0&&b.bottom<=innerHeight-2&&!blocks.some(r=>outside(r)&&overlap(b,r,3))&&!textBoxes.some(r=>outside(r)&&!departure.has(r.inkElement)&&overlap(b,r,2))&&(!state.excursion||!occupied(b,state.mark))&&(!state.guide||!state.mark?.cue||!overlap({left:p.x-2,right:p.x+2,top:p.y-2,bottom:p.y+2},hook.getBoundingClientRect(),0));
    };
    const api={
      get active(){return state.active;},
      move(p,lifted=false){if(!state.active||!allowed(p))return false;nib={...p};state.lifted=lifted;paintWriting();return true;},
      async travelTo(target,{signal,duration,horizontal=false}={}){
        if(!state.active||signal?.aborted)return Promise.resolve(false);
        const distance=Math.hypot(target.x-nib.x,target.y-nib.y),bend=Math.min(22,distance*.12);
        state.vertical=!horizontal&&distance>80;
        const header=document.querySelector('header')?.getBoundingClientRect();
        const landing=state.vertical?pt(target.x,Math.max(target.y,(header?.bottom||0)+48)):target;
        const route=travel(nib,landing,allowed,[bend,-bend,0,65,-65]);
        if(!route)return Promise.resolve(false);
        const routeLength=route.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p.x-route[i].x,p.y-route[i].y),0);
        const ms=duration===undefined?Math.max(75,Math.min(1250,routeLength*2.15)):duration*1.25;
        const arrived=await new Promise(resolve=>{
          let frame=0,start=null,done=false;
          const finish=value=>{if(done)return;done=true;cancelAnimationFrame(frame);signal?.removeEventListener('abort',abort);resolve(value);};
          const abort=()=>finish(false);signal?.addEventListener('abort',abort,{once:true});
          const step=now=>{if(!state.active||signal?.aborted){finish(false);return;}start??=now;const t=Math.min(1,(now-start)/ms);if(!api.move(along(route,ease(t)),true)){finish(false);return;}if(t===1)finish(true);else frame=requestAnimationFrame(step);};
          frame=requestAnimationFrame(step);
        });
        if(!arrived)return false;
        state.vertical=false;
        if(Math.hypot(landing.x-target.x,landing.y-target.y)>1)return api.travelTo(target,{signal,duration:110});
        return api.move(target,true);
      },
      async guide({signal}={}){return api.excursion({signal,guide:true});},
      async excursion({signal,guide=false}={}){
        if(!guide||!state.active||signal?.aborted||engaged)return false;
        const operation=state.operation=(state.operation||0)+1;
        state.excursion=true;state.guide=true;state.lifted=true;measure();
        marks=marks.filter(mark=>performance.now()-mark.born<(mark.life||24000));
        let m=null,completeGuide=false,staging=null;
        const abortGuide=()=>{if(m&&!completeGuide)marks=marks.filter(mark=>mark!==m);};
        signal?.addEventListener('abort',abortGuide,{once:true});
        try{
          m=hint();
          if(!m)return false;
          m.life=24000;m.fade=11000;m.born=performance.now();m.drawn=[];state.mark=m;marks.push(m);
          {
            const o=origin(m);if(!o)return false;
            hook.style.left=(o.x+m.cue.x)+'px';hook.style.top=(o.y+m.cue.y)+'px';
            host.dataset.arrowPoints='0';host.dataset.arrowComplete='false';
            // Approach beside the label upright, then rotate below its text.
            staging=pt(Math.max(8,o.x+m.cue.x-14),o.y+m.lines[0][0].y);
            const upright={left:nib.x-6,right:nib.x+6,top:nib.y-42,bottom:nib.y+4};
            if(!await api.travelTo(staging,{signal,horizontal:!m.side||overlap(upright,hook.getBoundingClientRect(),1)}))return false;
            state.sidePen=!!m.side;
          }
          for(const raw of m.lines){
            const o=origin(m);if(!o)return false;
            const line=raw.flatMap((p,i)=>{if(!i)return [p];const a=raw[i-1],n=Math.max(1,Math.ceil(Math.hypot(p.x-a.x,p.y-a.y)));return Array.from({length:n},(_,k)=>pt(a.x+(p.x-a.x)*(k+1)/n,a.y+(p.y-a.y)*(k+1)/n));});
            if(!await api.travelTo(pt(o.x+line[0].x,o.y+line[0].y),{signal}))return false;
            if(!await pause(random(45,95),signal))return false;
            const drawn=[];m.drawn.push(drawn);
            const duration=Math.max(165,Math.min(780,line.length/0.17))*random(.94,1.08);
            const complete=await new Promise(resolve=>{
              let frame=0,start=null,index=0,done=false;
              const finish=value=>{if(done)return;done=true;cancelAnimationFrame(frame);signal?.removeEventListener('abort',abort);resolve(value);};
              const abort=()=>finish(false);signal?.addEventListener('abort',abort,{once:true});
              const step=now=>{
                if(!state.active||signal?.aborted){finish(false);return;}start??=now;
                const t=Math.min(1,(now-start)/duration),end=Math.min(line.length-1,Math.floor(ease(t)*(line.length-1))),at=origin(m);
                if(!at){finish(false);return;}
                const previous=drawn.at(-1)||line[0];ctx.beginPath();ctx.moveTo(at.x+previous.x,at.y+previous.y);
                for(;index<=end;index++){const p=line[index];drawn.push(p);ctx.lineTo(at.x+p.x,at.y+p.y);}
                const p=drawn.at(-1)||line[0];
                if(!api.move(pt(at.x+p.x,at.y+p.y))){finish(false);return;}
                ctx.globalAlpha=m.alpha;ctx.strokeStyle='#e14959';ctx.lineWidth=m.width;ctx.lineCap=ctx.lineJoin='round';ctx.stroke();
                host.dataset.inkX=String(at.x+p.x);host.dataset.inkY=String(at.y+p.y);
                if(guide)host.dataset.arrowPoints=String(m.drawn.reduce((sum,line)=>sum+line.length,0));
                if(t===1)finish(true);else frame=requestAnimationFrame(step);
              };
              frame=requestAnimationFrame(step);
            });
            if(!complete)return false;
          }
          cueDrawn=true;completeGuide=true;host.dataset.arrowComplete='true';state.lifted=true;
          await api.travelTo(staging,{signal,duration:420,horizontal:true});return !signal?.aborted;
        }finally{
          signal?.removeEventListener('abort',abortGuide);
          if(m&&((guide&&!completeGuide)||!m.drawn.some(line=>line.length)))marks=marks.filter(mark=>mark!==m);
          if(state.operation===operation){state.mark=null;state.guide=false;state.sidePen=false;state.excursion=false;state.lifted=true;paintWriting();}
        }
      },
      release(){if(!state.active)return;state.active=false;if(handwriting===state)handwriting=null;invalidateLayout();}
    };
    state.api=api;wake();return api;
  }};
  function hint(){
    if(cueDrawn||hintRead>=14000||marks.some(m=>m.cue))return null;
    const anchor=document.querySelector('#tab-deepsearch');
    if(!anchor||!tool?.isConnected)return null;
    const r=anchor.getBoundingClientRect(),panel=tool.getBoundingClientRect();
    if(!r.width||r.top<165||r.top>innerHeight-45||r.left<0||r.right>innerWidth)return null;
    const x=r.width/2,left=Math.max(16,Math.min(innerWidth-236,r.left+x-70));
    const labelY=panel.top-70,label={left,right:left+220,top:labelY,bottom:labelY+49};
    if(label.top<85||blocked(label))return null;
    const sx=left+20-r.left,sy=labelY+55-r.top,side=r.top>panel.top+20;
    if(side){
      const lane=8-r.left,tip=pt(panel.left-8-r.left,r.height/2),turn=pt(lane,tip.y-8);
      const [bend,head]=arrow(turn,pt(lane,tip.y-2),pt(lane,tip.y),tip,5);
      const start=curve(pt(sx,sy),pt(lane+8,sy),pt(lane,sy),pt(lane,panel.top-22-r.top));
      return {anchor,side:true,alpha:.85,width:1.65,cue:{x:left-r.left,y:labelY-r.top},lines:[[...start,turn,...bend.slice(1)],head]};
    }
    return {anchor,alpha:.85,width:1.65,cue:{x:left-r.left,y:labelY-r.top},lines:arrow(pt(sx,sy),pt(sx+(x-sx)*.5,sy-1),pt(x-6,-20),pt(x,-17),5)};
  }
  function tick(now){
    raf=0;
    if(media.matches||document.hidden)return;
    const dt=Math.min(60,now-lastFrame);lastFrame=now;
    const scrolling=now-lastScroll<240;
    if(now>refresh){measure();refresh=now+180;}
    ctx.clearRect(0,0,innerWidth,innerHeight);hook.style.opacity='0';
    marks=marks.filter(m=>now-m.born<(m.life||24000)&&origin(m));let lifted=true;
    for(const m of marks){const o=origin(m);if(!m.cue)continue;const fade=Math.min(1,Math.max(0,((m.life||24000)-(now-m.born))/(m.fade||11000)));ctx.globalAlpha=m.alpha*fade;ctx.strokeStyle='#e14959';ctx.lineWidth=m.width;ctx.lineCap='round';ctx.lineJoin='round';if(!m.side)for(const line of m.drawn){ctx.beginPath();line.forEach((p,i)=>ctx[i?'lineTo':'moveTo'](o.x+p.x,o.y+p.y));ctx.stroke();}
      if(m.cue&&!scrolling){const x=o.x+m.cue.x,y=o.y+m.cue.y,b={left:x,right:x+220,top:y,bottom:y+49};if(y>85&&y+49<innerHeight&&!blocked(b)){
        hook.style.left=x+'px';hook.style.top=y+'px';hook.style.opacity=String(Math.min(1,(now-m.born)/450,Math.max(0,(16000-hintRead)/2000)));
        hintRead+=dt;host.dataset.hintVisible='true';
      }}
    }
    for(const b of blocks)ctx.clearRect(b.left-14,b.top-14,b.width+28,b.height+28);
    // Wrapped tabs get a side arrow in the gutter, clipped outside the panel.
    if(marks.some(m=>m.side&&m.cue)){
      const panel=tool.getBoundingClientRect(),top=Math.max(0,panel.top-3);
      ctx.save();ctx.beginPath();ctx.rect(0,0,innerWidth,top);ctx.rect(0,top,Math.max(0,panel.left-3),innerHeight-top);ctx.clip();
      for(const m of marks.filter(m=>m.side&&m.cue)){
        const o=origin(m);if(!o)continue;ctx.globalAlpha=m.alpha*Math.min(1,Math.max(0,(24000-(now-m.born))/11000));ctx.strokeStyle='#e14959';ctx.lineWidth=m.width;ctx.lineCap=ctx.lineJoin='round';
        for(const line of m.drawn){ctx.beginPath();line.forEach((p,i)=>ctx[i?'lineTo':'moveTo'](o.x+p.x,o.y+p.y));ctx.stroke();}
      }
      ctx.restore();
      for(const b of blocks){if(b.inkElement===tool)continue;const pad=tool.contains(b.inkElement)?3:14;ctx.clearRect(b.left-pad,b.top-pad,b.width+pad*2,b.height+pad*2);}
    }
    if(handwriting){paintWriting();raf=requestAnimationFrame(tick);return;}
    if(park){
      const t=park.route?Math.min(1,(now-park.start)/1200):1;
      if(park.route)nib=along(park.route,t*t*(3-2*t));
      if(t===1)park=null;
    }
    nib.x=Math.max(8,Math.min(innerWidth-33,nib.x));nib.y=Math.max(80,Math.min(innerHeight-12,nib.y));
    if(!safe(nib)){const clear=nearestSafe(nib);if(clear)nib=clear;}
    pen.style.opacity='.9';pen.style.transform=`translate(${nib.x}px,${nib.y-40}px) rotate(${(engaged?0:Math.sin(now/800)*4)+(lifted?8:0)}deg) scale(${lifted?1.06:1})`;
    // Keep the parked pen visible without clearing a blank canvas every frame.
    if(!engaged||park||marks.length)raf=requestAnimationFrame(tick);
  }
  function yieldToVisitor(e){if(!e.target.closest?.('#tool,#results,[role="dialog"]')||engaged)return;engaged=true;marks=[];const target=nearestSafe(pt(innerWidth-54,125));park={route:target&&travel(nib,target),start:performance.now()};host.dataset.mode='resting';wake();}
  for(const event of ['focusin','input','pointerdown'])document.addEventListener(event,yieldToVisitor);
  function wake(){
    if(media.matches||document.hidden||raf)return;
    lastFrame=performance.now();
    raf=requestAnimationFrame(tick);
  }
  function invalidateLayout(){refresh=0;wake();}
  function resume(){host.hidden=media.matches;invalidateLayout();}
  addEventListener('scroll',()=>{lastScroll=performance.now();invalidateLayout();},{passive:true});
  addEventListener('resize',()=>{resize();wake();},{passive:true});
  const layoutObserver=new ResizeObserver(invalidateLayout);layoutObserver.observe(document.body);
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;}else resume();});
  media.addEventListener('change',()=>{marks=[];resume();});
  resize();resume();
})();

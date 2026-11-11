/* The shared pen traces the rendered font. Reserved heading slots never reflow. */
(() => {
  'use strict';
  const title=document.querySelector('.hero-rotating-title');
  if(!title)return;
  const slots=[...title.querySelectorAll('[data-hero-slot]')],toggle=document.querySelector('.hero-rotate-toggle');
  const motion=matchMedia('(prefers-reduced-motion: reduce)'),cache=new Map();
  let index=0,paused=false,visible=true,busy=false,timer=0,run=null,lease=null,parking=null;
  const point=(x,y)=>({x,y});
  function animate(duration,paint,signal){
    return new Promise(resolve=>{
      let start=null,frame=0,done=false;
      const finish=value=>{if(done)return;done=true;cancelAnimationFrame(frame);signal.removeEventListener('abort',abort);resolve(value);};
      const abort=()=>finish(false);signal.addEventListener('abort',abort,{once:true});
      const tick=now=>{if(signal.aborted){finish(false);return;}start??=now;const t=Math.min(1,(now-start)/duration);if(paint(t)===false){finish(false);return;}if(t===1)finish(true);else frame=requestAnimationFrame(tick);};
      if(signal.aborted)finish(false);else frame=requestAnimationFrame(tick);
    });
  }
  function settle(){
    for(const slot of slots)[...slot.children].forEach((word,i)=>{
      word.classList.remove('is-leaving','is-writing');word.classList.toggle('is-current',i===index);
      for(const property of ['mask-image','-webkit-mask-image','clip-path'])word.style.removeProperty(property);
    });
    title.removeAttribute('data-writing');
  }
  // Turn this exact font's glyph raster into connected centerline strokes.
  function glyph(character,font){
    const key=font+'|'+character;if(cache.has(key))return cache.get(key);
    const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.font=font;
    const metric=ctx.measureText(character),ascent=metric.fontBoundingBoxAscent||24,descent=metric.fontBoundingBoxDescent||7,pad=4;
    const w=canvas.width=Math.ceil(metric.width)+pad*2,h=canvas.height=Math.ceil(ascent+descent)+pad*2;
    ctx.font=font;ctx.fillStyle='#fff';ctx.fillText(character,pad,pad+ascent);
    const rgba=ctx.getImageData(0,0,w,h).data,pixels=new Uint8Array(w*h);
    for(let i=0;i<pixels.length;i++)pixels[i]=rgba[i*4+3]>95?1:0;
    for(let pass=0;pass<24;pass++){
      let changed=false;
      for(let step=0;step<2;step++){
        const remove=[];
        for(let y=1;y<h-1;y++)for(let x=1;x<w-1;x++){
          const at=y*w+x;if(!pixels[at])continue;
          const n=[pixels[at-w],pixels[at-w+1],pixels[at+1],pixels[at+w+1],pixels[at+w],pixels[at+w-1],pixels[at-1],pixels[at-w-1]];
          const count=n.reduce((a,b)=>a+b,0),turns=n.reduce((a,b,i)=>a+(!b&&n[(i+1)%8]?1:0),0);
          if(count<2||count>6||turns!==1)continue;
          if(step===0?(n[0]*n[2]*n[4]||n[2]*n[4]*n[6]):(n[0]*n[2]*n[6]||n[0]*n[4]*n[6]))continue;
          remove.push(at);
        }
        if(remove.length)changed=true;for(const at of remove)pixels[at]=0;
      }
      if(!changed)break;
    }
    const graph=new Map();
    for(let y=1;y<h-1;y++)for(let x=1;x<w-1;x++){
      const at=y*w+x;if(!pixels[at])continue;const neighbors=[];
      for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){
        if((!dx&&!dy)||!pixels[at+dy*w+dx])continue;
        if(dx&&dy&&(pixels[at+dx]||pixels[at+dy*w]))continue;
        neighbors.push(at+dy*w+dx);
      }
      graph.set(at,neighbors);
    }
    const visited=new Set(),paths=[],edge=(a,b)=>a<b?a+':'+b:b+':'+a;
    const xy=at=>point(at%w-pad,Math.floor(at/w)-pad-ascent);
    const starts=[...graph.keys()].sort((a,b)=>(graph.get(a).length===2)-(graph.get(b).length===2)||a%w-b%w||a-b);
    for(const start of starts){
      const neighbors=graph.get(start);
      if(!neighbors.length){const p=xy(start);paths.push([p,point(p.x+.1,p.y)]);continue;}
      for(const first of neighbors){
        if(visited.has(edge(start,first)))continue;
        const path=[xy(start)];let previous=start,at=first;
        for(let guard=0;guard<500;guard++){
          visited.add(edge(previous,at));path.push(xy(at));
          const next=graph.get(at);if(next.length!==2)break;
          const candidate=next.find(n=>n!==previous&&!visited.has(edge(at,n)));if(candidate===undefined)break;
          previous=at;at=candidate;
        }
        paths.push(path);
      }
    }
    const result={paths,ascent,descent};cache.set(key,result);return result;
  }
  function letters(element){
    const style=getComputedStyle(element),font=`${style.fontWeight} ${style.fontSize} ${style.fontFamily}`,box=element.getBoundingClientRect();
    const size=parseFloat(style.fontSize),lineHeight=parseFloat(style.lineHeight),walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT),items=[];let node;
    while((node=walker.nextNode()))for(let i=0;i<node.length;i++){
      const character=node.textContent[i],range=document.createRange();range.setStart(node,i);range.setEnd(node,i+1);const r=range.getBoundingClientRect(),g=glyph(character,font);
      const baseline=(lineHeight-g.ascent-g.descent)/2+g.ascent;
      items.push({character,x:r.left-box.left,width:r.width,paths:g.paths.map(path=>path.map(p=>point(r.left-box.left+p.x,baseline+p.y)))});
    }
    return {items,box,size};
  }
  function metrics(path){let total=0;const lengths=[0];for(let i=1;i<path.length;i++){total+=Math.hypot(path[i].x-path[i-1].x,path[i].y-path[i-1].y);lengths.push(total);}return {total,lengths};}
  async function writeRow(slot,previousIndex,signal){
    const previous=slot.children[previousIndex],incoming=slot.children[index],old=previous.textContent,text=incoming.textContent;
    let common=0;while(common<old.length&&common<text.length&&old[common]===text[common])common++;
    common=text.lastIndexOf(' ',common-1)+1;
    const {items,box,size}=letters(incoming),prefix=items[common]?.x||0;
    const mask=document.createElement('canvas');mask.width=Math.ceil(box.width);mask.height=Math.ceil(box.height);
    const ctx=mask.getContext('2d');ctx.fillStyle=ctx.strokeStyle='#fff';ctx.lineCap='round';ctx.lineJoin='round';ctx.lineWidth=Math.max(3,size*.18);
    ctx.fillRect(0,0,prefix,mask.height);
    const publish=()=>{const image=`url("${mask.toDataURL()}")`;incoming.style.maskImage=image;incoming.style.webkitMaskImage=image;};
    const work=items.slice(common).filter(item=>item.paths.length);
    if(!work.length){previous.classList.remove('is-current');incoming.classList.add('is-current');return true;}
    const first=work[0].paths[0][0];
    if(!await lease.travelTo(point(box.left+first.x,box.top+first.y),{signal}))return false;
    publish();previous.style.clipPath=`inset(0 0 0 ${prefix}px)`;
    previous.classList.remove('is-current');previous.classList.add('is-leaving');incoming.classList.add('is-current','is-writing');
    title.dataset.writing=slot.dataset.heroSlot;
    if(!await animate(240,()=>true,signal))return false;
    for(const item of work){
      const paths=[...item.paths];let last=point(item.x,mask.height*.45);
      while(paths.length){
        paths.sort((a,b)=>Math.hypot(a[0].x-last.x,a[0].y-last.y)-Math.hypot(b[0].x-last.x,b[0].y-last.y));
        const path=paths.shift(),start=path[0];
        if(!await lease.travelTo(point(box.left+start.x,box.top+start.y),{signal,duration:Math.min(140,Math.max(32,Math.hypot(start.x-last.x,start.y-last.y)*2))}))return false;
        const measure=metrics(path);let cursor=1,painted=start;
        const duration=Math.max(32,Math.min(140,90/item.paths.length+measure.total*.3));
        if(!await animate(duration,t=>{
          const distance=measure.total*t;ctx.beginPath();ctx.moveTo(painted.x,painted.y);
          while(cursor<path.length&&measure.lengths[cursor]<=distance){ctx.lineTo(path[cursor].x,path[cursor].y);painted=path[cursor++];}
          const end=Math.min(cursor,path.length-1),begin=Math.max(0,end-1),f=(distance-measure.lengths[begin])/(measure.lengths[end]-measure.lengths[begin]||1);
          const tip=point(path[begin].x+(path[end].x-path[begin].x)*f,path[begin].y+(path[end].y-path[begin].y)*f);
          ctx.lineTo(tip.x,tip.y);ctx.stroke();painted=tip;
          if(!lease.move(point(box.left+tip.x,box.top+tip.y)))return false;
          publish();incoming.dataset.inkX=String(tip.x);incoming.dataset.inkY=String(tip.y);
        },signal))return false;
        last=path.at(-1);
      }
      // Finish antialiased corners after this glyph has been traced.
      ctx.fillRect(item.x-1,0,item.width+1,mask.height);publish();
    }
    previous.classList.remove('is-leaving');previous.style.removeProperty('clip-path');
    incoming.classList.remove('is-writing');incoming.style.removeProperty('mask-image');incoming.style.removeProperty('-webkit-mask-image');
    const lastItem=items.at(-1),rest=point(Math.min(innerWidth-49,box.left+lastItem.x+lastItem.width+8),box.top+box.height*.72);
    await lease.travelTo(rest,{signal,duration:160});return !signal.aborted;
  }
  function parkInitial(){
    parking?.abort();parking=new AbortController();
    const word=slots.at(-1).children[index],range=document.createRange();range.selectNodeContents(word);const r=range.getBoundingClientRect();
    lease.travelTo(point(Math.min(innerWidth-49,r.right+8),r.top+r.height*.74),{signal:parking.signal,duration:400});
  }
  async function rotate(){
    parking?.abort();parking=null;
    lease??=window.MyReconPen?.claim(title);if(!lease){timer=setTimeout(rotate,2000);return;}
    const previousIndex=index;index=(index+1)%slots[0].children.length;
    const controller=run=new AbortController();
    try{for(const slot of slots)if(!await writeRow(slot,previousIndex,controller.signal))break;}
    finally{if(run===controller){run=null;settle();if(!paused&&visible&&!busy&&!document.hidden&&!motion.matches)timer=setTimeout(rotate,3800);}}
  }
  function sync(){
    clearTimeout(timer);parking?.abort();run?.abort();run=null;settle();if(toggle)toggle.hidden=motion.matches;
    if(motion.matches){index=0;settle();}
    if(motion.matches||!visible||busy||document.hidden){lease?.release();lease=null;return;}
    lease??=window.MyReconPen?.claim(title);if(lease)parkInitial();
    if(!paused)timer=setTimeout(rotate,4200);
  }
  toggle?.addEventListener('click',()=>{
    paused=!paused;toggle.setAttribute('aria-pressed',String(paused));const label=`${paused?'Resume':'Pause'} headline animation`;
    toggle.setAttribute('aria-label',label);toggle.title=label;toggle.querySelector('path').setAttribute('d',paused?'m5 3 8 5-8 5z':'M4 3h3v10H4zm5 0h3v10H9z');sync();
  });
  document.addEventListener('focusin',e=>{busy=!!e.target.closest?.('#tool,#results');sync();});
  document.addEventListener('focusout',()=>queueMicrotask(()=>{const next=!!document.activeElement?.closest('#tool,#results');if(next!==busy){busy=next;sync();}}));
  new IntersectionObserver(entries=>{const next=entries[0].isIntersecting;if(next!==visible){visible=next;sync();}}).observe(title);
  let scrollTimer=0;
  addEventListener('scroll',()=>{clearTimeout(scrollTimer);clearTimeout(timer);parking?.abort();run?.abort();run=null;settle();lease?.release();lease=null;scrollTimer=setTimeout(sync,500);},{passive:true});
  addEventListener('resize',()=>{cache.clear();lease?.release();lease=null;sync();},{passive:true});
  document.addEventListener('visibilitychange',sync);motion.addEventListener('change',sync);
  sync();document.fonts.ready.then(()=>{cache.clear();sync();});
})();

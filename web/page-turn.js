/* A genuinely curved sheet: 56 articulated strips; a 56 x 12 Three.js mesh
 * when WebGL2 and the pinned CDN module are available. Accessible text remains
 * real DOM. All rendering paths consume snapshots of that same DOM.
 */
(() => {
  'use strict';
  const THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.min.js';
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const smooth = t => t * t * (3 - 2 * t);

  function capturePaper(element) {
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(rect.width * ratio); canvas.height = Math.ceil(rect.height * ratio);
    const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
    ctx.fillStyle = getComputedStyle(element).backgroundColor; ctx.fillRect(0, 0, rect.width, rect.height);
    let seed = 712;
    const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    ctx.fillStyle = '#59421b09';
    for (let n = 0; n < 3700; n++) ctx.fillRect(random() * rect.width, random() * rect.height, .7, .7);
    const shade = ctx.createLinearGradient(0, 0, rect.width, 0);
    shade.addColorStop(0, '#59411c12'); shade.addColorStop(.09, '#59411c00');
    shade.addColorStop(.92, '#59411c00'); shade.addColorStop(1, '#59411c0b');
    ctx.fillStyle = shade; ctx.fillRect(0, 0, rect.width, rect.height);
    ctx.textBaseline = 'middle';
    const range = document.createRange();

    function paint(node, parentStyle) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.textContent.trim()) return;
        const style = parentStyle;
        if (style.visibility === 'hidden' || style.color === 'transparent') return;
        const p = node.parentElement;
        const isDrop = p.matches('.story-text p:first-child') && node === p.firstChild;
        // Word ranges reflect real line breaks, scroll position and loaded typeface.
        const cjk = /[\u3000-\u9fff]/.test(node.textContent);
        let offset = 0;
        const matches = cjk ? Array.from(node.textContent, ch => {
          const part = {0: ch, index: offset}; offset += ch.length; return part;
        }).filter(part => part[0].trim()) : [...node.textContent.matchAll(/\S+/g)];
        for (const match of matches) {
          const start = match.index, end = start + match[0].length;
          const pieces = isDrop && start === 0 ? [[0, 1], [1, end]] : [[start, end]];
          for (const [a, b] of pieces) {
            if (a >= b) continue;
            range.setStart(node, a); range.setEnd(node, b);
            const bounds = range.getBoundingClientRect();
            if (bounds.bottom < rect.top || bounds.top > rect.bottom) continue;
            const drop = isDrop && a === 0;
            const textStyle = drop ? getComputedStyle(p, '::first-letter') : style;
            ctx.font = `${textStyle.fontStyle} ${textStyle.fontWeight} ${textStyle.fontSize} ${textStyle.fontFamily}`;
            ctx.fillStyle = textStyle.color;
            if ('letterSpacing' in ctx) ctx.letterSpacing = textStyle.letterSpacing === 'normal' ? '0px' : textStyle.letterSpacing;
            let txt = node.textContent.slice(a, b);
            if (style.textTransform === 'uppercase') txt = txt.toUpperCase();
            // Canvas middle is half the x-height; compensate using actual font metrics.
            ctx.textBaseline = 'alphabetic';
            const metrics = ctx.measureText(txt);
            const asc = metrics.fontBoundingBoxAscent ?? parseFloat(textStyle.fontSize) * .8;
            const desc = metrics.fontBoundingBoxDescent ?? parseFloat(textStyle.fontSize) * .2;
            const baseline = bounds.top - rect.top + (bounds.height - asc - desc) / 2 + asc;
            ctx.fillText(txt, bounds.left - rect.left, baseline);
          }
        }
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden') return;
      const r = node.getBoundingClientRect(), x = r.left - rect.left, y = r.top - rect.top;
      ctx.save();
      if (node !== element && style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent') {
        ctx.fillStyle = style.backgroundColor; ctx.fillRect(x, y, r.width, r.height);
      }
      for (const edge of ['Top', 'Bottom']) {
        const width = parseFloat(style[`border${edge}Width`]);
        if (width > 0) {
          ctx.fillStyle = style[`border${edge}Color`];
          ctx.fillRect(x, edge === 'Top' ? y : y + r.height - width, r.width, width);
        }
      }
      if (node.tagName.toLowerCase() === 'svg') {
        // Preserve pen annotations on the outgoing sheet, including their tilt.
        for (const stroke of node.querySelectorAll('path')) {
          const matrix = stroke.getScreenCTM();
          if (!matrix) continue;
          const inkStyle = getComputedStyle(stroke);
          ctx.save(); ctx.translate(-rect.left, -rect.top);
          ctx.transform(matrix.a, matrix.b, matrix.c, matrix.d, matrix.e, matrix.f);
          ctx.strokeStyle = inkStyle.stroke; ctx.lineWidth = parseFloat(inkStyle.strokeWidth) || 2;
          ctx.lineCap = 'round'; ctx.lineJoin = 'round';
          const outline = new Path2D(stroke.getAttribute('d'));
          // Non-scaling circle strokes are transformed back to CSS-pixel width.
          if (inkStyle.vectorEffect === 'non-scaling-stroke') ctx.lineWidth /= Math.max(.1, Math.hypot(matrix.a, matrix.b));
          ctx.stroke(outline); ctx.restore();
        }
      } else if (node.tagName === 'IMG') {
        if (node.complete && node.naturalWidth) {
          const scale = Math.min(r.width / node.naturalWidth, r.height / node.naturalHeight);
          const w = node.naturalWidth * scale, h = node.naturalHeight * scale;
          ctx.globalAlpha = parseFloat(style.opacity) || 1;
          try { ctx.drawImage(node, x + (r.width - w) / 2, y + (r.height - h) / 2, w, h); } catch (_) {}
        }
      } else {
        if (node === element || /auto|scroll|hidden|clip/.test(style.overflowY)) {
          ctx.beginPath(); ctx.rect(x, y, r.width, r.height); ctx.clip();
        }
        for (const child of node.childNodes) paint(child, style);
      }
      ctx.restore();
    }
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, rect.width, rect.height); ctx.clip();
    paint(element, getComputedStyle(element)); ctx.restore(); range.detach();
    return canvas;
  }

  // Inextensible centreline integrated from local tangent angles. No flat-card flip.
  function curve(width, t, count = 56) {
    const p = smooth(clamp(t, 0, 1));
    const points = [{x: 0, z: 0, angle: -Math.PI * p}];
    let x = 0, z = 0;
    for (let i = 0; i < count; i++) {
      const u = (i + .5) / count;
      const angle = -Math.PI * p + Math.sin(Math.PI * p) * .72 * Math.sin(Math.PI * u - .48);
      points[i].angle = angle;
      x += Math.cos(angle) * width / count;
      z -= Math.sin(angle) * width / count;
      points.push({x, z, angle});
    }
    return points;
  }


  function travelPlan(from, to) {
    const delta=from&&to?to.spread-from.spread:1, distance=Math.abs(delta);
    const sheets=Math.min(9,distance), leafDuration=distance>1?440:660, stagger=distance>1?110:0;
    return {direction:delta<0?-1:1,distance,sheets,leafDuration,stagger,
      duration:distance?leafDuration+stagger*(sheets-1):0,from:from?.right??1,to:to?.right??3};
  }
  function neutralPaper(reference, folio) {
    const c=document.createElement('canvas');c.width=reference.width;c.height=reference.height;
    const ctx=c.getContext('2d'),w=c.width,h=c.height;
    const gradient=ctx.createLinearGradient(0,0,w,0);gradient.addColorStop(0,'#d9c8a6');gradient.addColorStop(.12,'#ede0c3');gradient.addColorStop(.9,'#eee1c5');gradient.addColorStop(1,'#dacaac');
    ctx.fillStyle=gradient;ctx.fillRect(0,0,w,h);ctx.strokeStyle='#846b4330';ctx.lineWidth=.8;
    for(let i=0;i<18;i++){const y=h*(.19+i*.032);ctx.beginPath();ctx.moveTo(w*.13,y);ctx.lineTo(w*(.8+(i%3)*.03),y);ctx.stroke();}
    ctx.fillStyle='#745839';ctx.font=`${Math.round(w*.025)}px Georgia,serif`;ctx.textAlign='center';
    ctx.fillText('THE DECISION LIBRARY',w/2,h*.085);ctx.fillText(`— ${folio} —`,w/2,h*.955);
    // Neutral unexamined leaves; no future story text is requested or exposed.
    return c;
  }

  class PageTurn {
    constructor({book, spread, stage, onRenderer, audio}) {
      this.book = book; this.spread = spread; this.stage = stage;
      this.onRenderer = onRenderer; this.audio = audio; this.duration = 1250;
      this.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
      this.busy = false; this.THREE = null; this.renderer = null;
      this.engine = 'css3d'; this.lastProgress = null;
      this.onRenderer('CSS 3D · curved paper');
      this.prepareThree();
    }
    async prepareThree() {
      let probe;
      try {
        const c = document.createElement('canvas'); probe = c.getContext('webgl2');
        if (!probe) return;
        probe.getExtension('WEBGL_lose_context')?.loseContext();
        const T = await Promise.race([
          import(THREE_URL),
          new Promise((_, reject) => setTimeout(() => reject(new Error('CDN timeout')), 6000))
        ]);
        const renderer = new T.WebGLRenderer({alpha: true, antialias: true});
        renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);
        renderer.domElement.className = 'three-sheet';
        this.renderer = renderer; this.THREE = T; this.engine = 'three';
        if (!this.busy) this.onRenderer('Three.js r180 · curved mesh');
      } catch (_) { /* Offline / no GPU: keep the fully functional CSS renderer. */ }
    }
    async turn(renderNext, {from, to} = {}) {
      if (this.busy) return;
      const plan = travelPlan(from, to);
      if (!plan.distance) { renderNext(); return; }
      this.lastPlan = plan; this.busy = true; this.book.classList.add('turning');
      const right = document.getElementById('rightPage'), left = document.getElementById('leftPage');
      const mobile = getComputedStyle(left).display === 'none';
      const rect = this.spread.getBoundingClientRect(), w = mobile ? rect.width : rect.width / 2, h = rect.height;
      const cleanups = [];
      try {
        const oldRight = capturePaper(right), oldLeft = mobile ? null : capturePaper(left);
        if (!oldRight) { renderNext(); return; }
        const still = document.createElement('div'); still.className = 'sheet-old-left';
        still.style.left = plan.direction > 0 ? '0' : '50%';
        const stationary = plan.direction > 0 ? oldLeft : oldRight;
        if (stationary && !mobile) still.style.backgroundImage = `url(${stationary.toDataURL()})`;
        else still.hidden = true;
        this.stage.append(still);
        const cover = document.createElement('div'); cover.className = 'sheet-old-left';
        cover.style.left = mobile || plan.direction < 0 ? '0' : '50%';
        cover.style.width = mobile ? '100%' : '50%';
        cover.style.backgroundImage = `url(${(plan.direction > 0 || mobile ? oldRight : oldLeft).toDataURL()})`;
        cover.style.zIndex = '50';this.stage.append(cover);
        renderNext();
        const nextRight = capturePaper(right), nextLeft = mobile ? null : capturePaper(left);
        if (this.reduced || mobile) {
          this.audio.play('paper', .25, plan.direction);
          await cover.animate([{opacity:1,transform:'translateX(0)'},
            {opacity:0,transform:`translateX(${-12*plan.direction}px)`}],{duration:this.reduced?150:260,easing:'ease-out'}).finished;
          return;
        }
        const counter=document.createElement('div');counter.className='riffle-counter';this.book.append(counter);cleanups.push(()=>counter.remove());
        const sheets=[];
        for(let i=0;i<plan.sheets;i++) {
          const fraction=(i+1)/plan.sheets;
          const page=Math.round(plan.from+(plan.to-plan.from)*fraction);
          const neutral=neutralPaper(oldRight,page);
          sheets.push({front:plan.direction>0 ? (i===0?oldRight:neutral) : (i===plan.sheets-1?nextRight:neutral),
            back:plan.direction>0 ? (i===plan.sheets-1?nextLeft:neutral) : (i===0?oldLeft:neutral)});
        }
        let render;
        if(this.engine==='three') {
          try { const batch=this.makeThreeStack(sheets,w,h);render=batch.frame;cleanups.push(batch.cleanup); }
          catch(_) { this.engine='css3d'; this.onRenderer('CSS 3D · curved paper'); }
        }
        if(!render) {
          const leaves=sheets.map(({front,back})=>this.makeStrips(front,back,w,h));
          cleanups.push(()=>leaves.forEach(leaf=>leaf.cleanup()));
          render=(positions)=>leaves.forEach((leaf,i)=>{
            const t=positions[i]; leaf.element.style.zIndex=String(t<.5 ? sheets.length-i+3 : sheets.length+i+3);
            leaf.frame(t);
          });
        }
        const shadow=document.createElement('div');shadow.className='sheet-shadow';this.stage.append(shadow);
        shadow.style.left=plan.direction>0?'50%':'0';
        const sounded=new Set();
        render(sheets.map(()=>plan.direction>0?0:1));
        // Prime the layered textures before starting the clock. Setup latency must
        // not compress the first paper sounds into a single frame.
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        cover.remove(); const started=performance.now();
        await new Promise(resolve=>{
          const draw=now=>{
            const elapsed=Math.min(now-started,plan.duration);
            const positions=sheets.map((_,i)=>{
              const raw=clamp((elapsed-i*plan.stagger)/plan.leafDuration,0,1);
              if(raw>0&&!sounded.has(i)){sounded.add(i);this.audio.play(plan.sheets===1?'paper':'flutter',plan.sheets===1?.55:.1,plan.direction);}
              return plan.direction>0?raw:1-raw;
            });
            this.lastProgress=elapsed/plan.duration;render(positions);
            const movement=smooth(this.lastProgress);
            counter.textContent=`${plan.direction>0?'→':'←'}  p.${Math.round(plan.from+(plan.to-plan.from)*movement)} / ${to?.total||'—'}  ·  ${plan.distance}見開き`;
            shadow.style.opacity=String(Math.sin(Math.PI*movement)*.13);
            if(elapsed<plan.duration)requestAnimationFrame(draw);else resolve();
          };requestAnimationFrame(draw);
        });
      } finally {
        cleanups.reverse().forEach(cleanup=>cleanup());
        this.stage.replaceChildren();this.book.classList.remove('turning');this.busy=false;this.lastProgress=null;
      }
    }
    makeStrips(front, back, w, h) {
      const count = 56, container = document.createElement('div'); container.className = 'sheet-strips';
      const frontURL = front.toDataURL(), backURL = back.toDataURL();
      const strips = [];
      for (let i = 0; i < count; i++) {
        const strip = document.createElement('div'); strip.className = 'sheet-strip';
        const sw = w / count + .55; strip.style.width = `${sw}px`;
        for (let side = 0; side < 2; side++) {
          const face = document.createElement('div'); face.className = `sheet-face ${side ? 'back' : 'front'}`;
          face.style.backgroundImage = `url(${side ? backURL : frontURL})`;
          face.style.backgroundSize = `${w}px ${h}px`;
          face.style.backgroundPosition = `${side ? -(w - (i + 1) * w / count) : -i * w / count}px 0`;
          strip.append(face);
        }
        container.append(strip); strips.push(strip);
      }
      this.stage.append(container);
      return {
        element: container,
        frame(t) {
          const pts = curve(w, t, count);
          strips.forEach((s, i) => {
            const p = pts[i];
            s.style.transform = `translate3d(${p.x}px,0,${p.z + 1}px) rotateY(${p.angle}rad)`;
            s.style.setProperty('--shade', String(Math.sin(Math.PI * t) * (.05 + .07 * Math.abs(Math.sin(p.angle)))));
          });
        },
        cleanup: () => container.remove()
      };
    }
    makeThreeStack(sheets, w, h) {
      const T=this.THREE, renderer=this.renderer, cols=56, rows=12;
      const pad=Math.ceil(h*.45), totalW=w*2+pad*2, totalH=h+pad*2;
      renderer.setSize(totalW,totalH);
      Object.assign(renderer.domElement.style,{left:`${-pad}px`,top:`${-pad}px`,width:`${totalW}px`,height:`${totalH}px`});
      this.stage.append(renderer.domElement);
      const scene=new T.Scene(), camera=new T.PerspectiveCamera(2*Math.atan(totalH/3000)*180/Math.PI,totalW/totalH,1,3000);
      camera.position.z=1500;
      const resources=sheets.map(({front,back})=>{
        const geo=new T.PlaneGeometry(w,h,cols,rows), positions=geo.attributes.position;
        positions.setUsage(T.DynamicDrawUsage);
        const colors=new Float32Array(positions.count*3).fill(1);
        geo.setAttribute('color',new T.BufferAttribute(colors,3).setUsage(T.DynamicDrawUsage));
        const ft=new T.CanvasTexture(front),bt=new T.CanvasTexture(back);
        [ft,bt].forEach(tex=>{tex.colorSpace=T.SRGBColorSpace;tex.anisotropy=Math.min(renderer.capabilities.getMaxAnisotropy(),4);});
        bt.repeat.x=-1;bt.offset.x=1;
        const fm=new T.MeshBasicMaterial({map:ft,side:T.FrontSide,vertexColors:true,toneMapped:false});
        const bm=new T.MeshBasicMaterial({map:bt,side:T.BackSide,vertexColors:true,toneMapped:false});
        const f=new T.Mesh(geo,fm),b=new T.Mesh(geo,bm);f.frustumCulled=b.frustumCulled=false;scene.add(f,b);
        return {geo,positions,colors,ft,bt,fm,bm};
      });
      return {
        frame(progresses){
          resources.forEach((r,i)=>{
            const t=progresses[i], pts=curve(w,t,cols), bend=Math.sin(Math.PI*t);
            for(let y=0;y<=rows;y++)for(let x=0;x<=cols;x++) {
              const j=y*(cols+1)+x,p=pts[x];
              r.positions.setXYZ(j,p.x,h/2-y*h/rows,p.z+1+(t<.5?sheets.length-i:i)*.25+bend*8*(y/rows-.5)*(x/cols)**2);
              const shade=1-bend*(.04+.08*Math.abs(Math.sin(p.angle)));
              r.colors[j*3]=r.colors[j*3+1]=r.colors[j*3+2]=shade;
            }
            r.positions.needsUpdate=true;r.geo.attributes.color.needsUpdate=true;
          });renderer.render(scene,camera);
        },
        cleanup(){renderer.clear();renderer.domElement.remove();resources.forEach(r=>{r.geo.dispose();r.ft.dispose();r.bt.dispose();r.fm.dispose();r.bm.dispose();});}
      };
    }

  }
  window.PageTurn = PageTurn;
  window.GamebookPaper = {capturePaper, curve, travelPlan};
})();

/* Presentation-only layer. Load after reader-ui/page-turn/sound and before app.
 * It does not change action IDs, probabilities, rules, RNG or folios.
 * The item tray partitions visual actions; provider choices remain intact.
 * Public base classes stay usable by older captures; the normal UI uses these
 * bounded, pooled renderers. No remote assets or fonts are needed here.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const MOTION = Object.freeze({score:260, contemplation:340, down:110, up:145, hold:1000});
  const runningAnimations = new Set();

  // Web Animation .finished can remain pending in a background/automated tab.
  // Decorative work may finish early, but must never own the gameplay lock.
  function motion(node, frames, options) {
    if (document.hidden) return Promise.resolve();
    const animation = node.animate(frames, options);
    runningAnimations.add(animation);
    return new Promise(resolve => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true; clearTimeout(timer); runningAnimations.delete(animation);
        try { animation.finish(); } catch (_) { animation.cancel(); }
        resolve();
      };
      const timer = setTimeout(finish, (options.duration || 0) + (options.delay || 0) + 300);
      animation.finished.then(finish, finish);
    });
  }
  const svgNode = (tag, attrs = {}) => {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };

  // Original broad-nib numeral outlines, rather than the old monoline doodles.
  // Angled feet, pointed bowls and heavy/light strokes echo blackletter print.
  // These are drawing commands, not embedded or distributed font binaries.
  const NUMERALS = {
    '0':'M13 1 L22 7 L21 29 L10 35 L2 28 L3 8 Z M10 7 L8 27 L14 30 L16 10 Z',
    '1':'M3 10 L13 1 L16 3 L14 29 L20 30 L18 34 L2 34 L4 30 L8 29 L10 9 L6 12 Z',
    '2':'M2 9 Q7 0 15 2 L22 7 L21 14 L7 27 L17 27 L22 23 L20 34 L1 34 L2 27 L15 13 L15 8 L9 6 L5 12 Z',
    '3':'M3 7 L12 1 L21 6 L21 13 L16 17 L21 22 L20 30 L10 35 L2 30 L3 24 L8 28 L13 29 L15 23 L10 19 L6 20 L6 15 L13 14 L15 8 L9 7 L4 11 Z',
    '4':'M14 1 L19 2 L17 22 L23 21 L22 26 L17 26 L16 31 L20 32 L19 35 L6 35 L7 31 L11 30 L12 26 L1 26 L2 21 Z M12 10 L6 21 L12 21 Z',
    '5':'M6 2 L22 2 L20 8 L10 7 L8 15 L15 13 L22 19 L20 29 L10 35 L2 30 L3 24 L9 28 L14 28 L16 21 L11 19 L3 21 Z',
    '6':'M18 1 L22 5 L14 7 L8 15 L15 12 L22 19 L20 29 L10 35 L2 28 L3 14 L10 5 Z M9 19 L8 27 L14 30 L16 21 L12 18 Z',
    '7':'M2 2 L23 2 L22 7 L15 20 L13 31 L16 33 L15 35 L5 35 L9 20 L16 8 L7 8 L2 12 Z M5 17 L19 15 L19 19 L4 21 Z',
    '8':'M12 1 L22 6 L21 13 L16 18 L22 23 L20 30 L10 35 L1 29 L2 22 L7 17 L2 12 L3 6 Z M10 7 L8 12 L14 15 L16 9 Z M9 21 L7 27 L14 30 L16 24 Z',
    '9':'M13 1 L22 8 L21 22 L14 31 L6 35 L2 31 L10 28 L15 20 L8 23 L1 17 L3 7 Z M10 7 L8 16 L13 18 L16 13 L16 9 Z',
    '.':'M7 28 L11 31 L7 35 L3 32 Z',
    '%':'M27 1 L30 2 L5 35 L2 33 Z M7 2 L13 6 L12 13 L6 17 L1 13 L2 6 Z M6 7 L5 12 L8 13 L9 8 Z M24 20 L30 24 L29 31 L23 35 L18 31 L19 24 Z M23 25 L22 30 L25 31 L26 26 Z',
  };
  function inkPercentage(value) {
    const scaled = value * 100;
    const label = `${scaled.toFixed(Math.abs(scaled - Math.round(scaled)) < .05 ? 0 : 1)}%`;
    const width = [...label].reduce((n, c) => n + (c === '.' ? 12 : c === '%' ? 33 : 24), 0);
    const svg = svgNode('svg', {viewBox:`0 -3 ${width + 2} 43`, class:'ink-percent gothic-numerals', 'aria-hidden':'true'});
    let x = 0;
    for (const ch of label) {
      svg.append(svgNode('path', {d:NUMERALS[ch], 'fill-rule':'evenodd', transform:`translate(${x},0)`}));
      x += ch === '.' ? 12 : ch === '%' ? 33 : 24;
    }
    const accessible = document.createElement('span');
    accessible.className = 'sr-only ink-numeric'; accessible.textContent = label;
    return [svg, accessible];
  }
  let inkSerial = 0;
  function checkmark(button) {
    const id = `quill-check-${++inkSerial}`;
    const svg = svgNode('svg', {viewBox:'0 0 100 76', class:'ink-check', 'aria-hidden':'true'});
    const defs = svgNode('defs');
    const mask = svgNode('mask', {id, maskUnits:'userSpaceOnUse', x:0, y:0, width:100, height:76});
    const down = svgNode('path', {d:'M10 32 Q22 43 34 61', pathLength:1, class:'check-reveal'});
    const up = svgNode('path', {d:'M31 59 Q48 35 92 7', pathLength:1, class:'check-reveal'});
    mask.append(down, up); defs.append(mask); svg.append(defs);
    // Narrow nib touch, a heavy elbow, and a long, tapered ascending slash.
    const ink = svgNode('g', {mask:`url(#${id})`, class:'check-ink'});
    ink.append(svgNode('path', {d:'M6 27 Q19 33 29 44 L34 54 Q57 24 96 3 Q68 35 40 68 L28 72 Q22 53 6 27 Z'}));
    ink.append(svgNode('path', {d:'M12 30 Q24 44 30 60 L33 62 L29 56 Q22 39 12 30 Z M43 50 L76 17 L51 45 Z', class:'ink-grain'}));
    svg.append(ink);
    const fleck = svgNode('path', {class:'ink-flecks', d:'M11 23 l2 2 -1 2 -2 -1 Z M92 1 l3 0 -2 2 Z M23 64 l1 4 -2 -1 Z'});
    svg.append(fleck); button.append(svg);
    return {svg, down, up, fleck};
  }
  const baseClear = window.ReaderUI.clearInk;
  window.ReaderUI.clearInk = () => {
    for (const animation of runningAnimations) animation.cancel();
    runningAnimations.clear();
    document.querySelectorAll('.ink-check').forEach(node => node.remove());
    baseClear();
  };
  window.ReaderUI.annotate = async function(decision, {audio, reduced = false} = {}) {
    this.phase('annotating');
    timing.decision = {source:decision.source, provider_ms:decision.latency_ms, revision:window.gamebook?.app.run?.revision};
    const scores = decision.probabilities || {}, hasScores = Object.keys(scores).length > 0;
    const source = decision.probability_source || (decision.source === 'random' ? 'uniform' : decision.source === 'browser' ? 'browser_self_report' : 'provider');
    $('inkLegend').textContent = hasScores ? ({uniform:'Random の抽選確率', browser_self_report:'ブラウザAIの自己申告'}[source] || 'モデルが返した選択確率') : decision.source === 'forced' ? '分岐なし · エンジン処理' : '手動選択 · 確率情報なし';
    $('inkLegend').hidden = false;
    const available = [...document.querySelectorAll('#choices [data-choice], #itemChoices [data-choice]')];
    const selected = available.find(button => button.dataset.choice === decision.choice);
    const marks = [];
    for (const button of available) {
      const value = scores[button.dataset.choice];
      if (typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1) {
        const [svg, text] = inkPercentage(value); button.append(svg, text); marks.push(svg);
      }
    }
    if (!selected) return;
    const parent = selected.parentElement, rect = selected.getBoundingClientRect(), shelf = parent.getBoundingClientRect();
    if (rect.bottom > shelf.bottom) parent.scrollTop += rect.bottom - shelf.bottom + 7;
    if (rect.top < shelf.top) parent.scrollTop += rect.top - shelf.top - 7;
    selected.classList.add('ink-picked');
    if (hasScores && !reduced && !document.hidden) {
      await Promise.all(marks.map((mark, i) => motion(mark, [{opacity:0, clipPath:'inset(0 100% 0 0)'}, {opacity:1, clipPath:'inset(0 0 0 0)'}], {duration:MOTION.score, delay:Math.min(i*30,120), fill:'both', easing:'ease-out'})));
    }
    if (!reduced && !document.hidden) await sleep(MOTION.contemplation);
    const check = checkmark(selected);
    if (reduced || document.hidden) {
      check.down.style.strokeDashoffset = check.up.style.strokeDashoffset = '0';
      if (!document.hidden) await sleep(90);
      return;
    }
    await motion(check.down, [{strokeDashoffset:'1'}, {strokeDashoffset:'0'}], {duration:MOTION.down, fill:'forwards', easing:'cubic-bezier(.45,0,.75,1)'});
    audio?.play('slash', .16);
    await motion(check.up, [{strokeDashoffset:'1'}, {strokeDashoffset:'0'}], {duration:MOTION.up, fill:'forwards', easing:'cubic-bezier(.08,.6,.15,1)'});
    await motion(check.fleck, [{opacity:0}, {opacity:.6}], {duration:70, fill:'both'});
    if (!document.hidden) await sleep(MOTION.hold);
  };


  // Main choices and consumables are separate visual groups. Move the actual
  // button nodes, retaining their click listeners and authoritative action IDs.
  const isItemAction = key => /^(use:|equip:|kai:equip:)/.test(key || '') || key === 'kai:potion';
  const baseDecorate = window.ReaderUI.decorate;
  const combatItemSlots = [
    ['use:tonic', '回復薬'], ['use:bandage', '清め布'],
    ['use:saltbomb', '鳴塩を投げる'], ['use:smoke', '煙玉'],
  ];
  const mainOrder = ['combat:attack', 'combat:precision', 'combat:guard', 'combat:flee'];
  function itemTray() {
    let area = $('itemArea');
    if (!area) {
      area = document.createElement('section'); area.id = 'itemArea'; area.className = 'item-area';
      area.setAttribute('aria-labelledby', 'itemAreaLabel');
      const header = document.createElement('div'); header.id = 'itemAreaLabel'; header.className = 'item-area-label';
      header.textContent = '道具を使う / 装備';
      const list = document.createElement('div'); list.id = 'itemChoices'; list.className = 'item-choices';
      area.append(header, list); $('actionShelf').insertBefore(area, $('actionExplanation'));
    }
    return area;
  }
  function unavailableItem(key, label) {
    const button = document.createElement('button'); button.className = 'choice-button unavailable';
    button.disabled = true; button.dataset.slot = key; button.setAttribute('aria-disabled', 'true');
    for (const name of ['choice-roman', 'choice-label', 'choice-target']) {
      const span = document.createElement('span'); span.className = name; button.append(span);
    }
    button.querySelector('.choice-label').textContent = label;
    return button;
  }
  function itemDetail(run, key, legal) {
    if (run.mode === 'lonewolf_kai') {
      const count = run.character?.backpack?.find(item => item.name === 'Healing Potion')?.count || 0;
      if (key === 'kai:potion') return `残り ${count} · ${legal ? 'ENDURANCE +4' : run.combat_state ? '戦闘中は使えない' : count ? '体力は最大' : '所持していない'}`;
      return legal ? '使用する武器を変更' : '現在は装備できない';
    }
    const item = run.character?.inventory?.find(entry => entry.id === key.split(':')[1]);
    if (key.startsWith('equip:')) return '装備を変更';
    const count = item?.count || 0;
    const hint = !count ? '所持していない' : !legal ? (key === 'use:smoke' ? 'この戦闘では撤退不可' : '体力は最大') :
      key === 'use:saltbomb' ? '固定ダメージ' : key === 'use:smoke' ? '確実に撤退' : '体力を回復';
    return `残り ${count} · ${hint}`;
  }
  window.ReaderUI.decorate = function(run) {
    const area = itemTray(), items = $('itemChoices'), main = $('choices');
    // app.render has just rebuilt #choices. Remove the old tray before base
    // decoration assigns DOM IDs, preventing stale/duplicate item buttons.
    const renderKey = `${run.run_id || run.book || run.mode}:${run.current}:${run.revision}`;
    if (area.dataset.renderKey === renderKey) {
      const fresh = new Set([...main.children].map(button => button.dataset.choice || button.dataset.slot));
      for (const button of [...items.querySelectorAll('.choice-button')]) {
        const key = button.dataset.choice || button.dataset.slot;
        if (!fresh.has(key) && run.section.choices.some(action => action.key === key)) main.append(button);
      }
    }
    items.replaceChildren(); area.dataset.renderKey = renderKey;
    baseDecorate(run);
    const supportsItems = !!run.character;
    const legal = new Map(run.section.choices.map(action => [action.key, action]));
    for (const button of [...main.children]) {
      if (isItemAction(button.dataset.choice || button.dataset.slot)) items.append(button);
    }
    if (run.combat_state && run.mode === 'story_rpg') {
      const byId = new Map([...main.children].map(button => [button.dataset.choice || button.dataset.slot, button]));
      main.replaceChildren(...mainOrder.map(key => byId.get(key)).filter(Boolean),
        ...[...byId].filter(([key]) => !mainOrder.includes(key)).map(([,button]) => button));
    }
    // Keep the four consumable slots in the same positions even as they run out.
    if (run.mode === 'story_rpg' && run.combat_state) {
      const byId = new Map([...items.children].map(button => [button.dataset.choice || button.dataset.slot, button]));
      items.replaceChildren(...combatItemSlots.map(([key, label]) => byId.get(key) || unavailableItem(key, label)),
        ...[...byId].filter(([key]) => !combatItemSlots.some(([slot]) => slot === key)).map(([,button]) => button));
    }
    area.hidden = !supportsItems || run.status !== 'live';
    $('actionShelf').dataset.itemTray = String(!area.hidden);
    const mainChoices = run.section.choices.filter(action => !isItemAction(action.key));
    const itemChoices = run.section.choices.filter(action => isItemAction(action.key));
    $('actionCount').textContent = `${mainChoices.length} ACTIONS · ${itemChoices.length} ITEMS`;
    $('itemAreaLabel').textContent = run.mode === 'lonewolf_kai' ? '道具 / 使用武器' : '道具を使う / 装備';
    for (const [i, button] of [...main.children].entries()) {
      button.querySelector('.choice-roman').textContent = `${i + 1}.`;
      button.dataset.slotIndex = String(i); button.dataset.actionGroup = 'main';
      button.setAttribute('aria-keyshortcuts', String(i + 1));
      const action = legal.get(button.dataset.choice);
      const label = action?.text || button.querySelector('.choice-label').textContent;
      button.setAttribute('aria-label', `${i + 1}. ${label}${button.classList.contains('unavailable') ? '（使用不可）' : ''}`);
    }
    for (const button of [...items.children]) {
      const key = button.dataset.choice || button.dataset.slot, action = legal.get(key);
      button.dataset.actionGroup = 'item'; button.querySelector('.choice-roman').textContent = '道';
      button.removeAttribute('aria-keyshortcuts'); delete button.dataset.slotIndex;
      const detail = itemDetail(run, key, !!action);
      button.querySelector('.choice-target').textContent = detail;
      const label = action?.text || button.querySelector('.choice-label').textContent;
      button.setAttribute('aria-label', `道具: ${label}（${detail}）`);
      button.title = `${label}（${detail}）`;
      button.disabled = !action || run.status !== 'live' || !!window.gamebook?.app.busy;
      button.addEventListener('mouseenter', () => $('actionExplanation').textContent = button.title);
      button.addEventListener('focus', () => $('actionExplanation').textContent = button.title);
    }
    let empty = $('itemEmpty');
    if (!empty) { empty = document.createElement('p'); empty.id = 'itemEmpty'; empty.textContent = '今使える道具・変更できる装備はありません。'; items.append(empty); }
    empty.hidden = items.querySelectorAll('.choice-button').length > 0;
    items.scrollTop = 0;
    $('actionExplanation').textContent = run.combat_state && run.mode === 'story_rpg' ?
      '1–4：攻撃・精密攻撃・防御・撤退。道具は下の別枠。' :
      '物語の選択と、道具の使用・装備変更を分けて表示しています。';
  };

  // .resume() is intentionally fire-and-observe: permission/hardware readiness
  // must not block a manual action, browser-agent evaluation, reset or auto-run.
  const BaseAudio = window.PaperAudio;
  window.PaperAudio = class NonBlockingPaperAudio extends BaseAudio {
    async unlock() {
      if (!this.enabled) return false;
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) { this.enabled = false; return false; }
      try {
        if (!this.ctx) {
          this.ctx = new Context(); this.master = this.ctx.createGain();
          this.master.gain.value = this.volume * .7; this.master.connect(this.ctx.destination);
        }
        if ((this.ctx.state === 'suspended' || this.ctx.state === 'interrupted') && (!this._resuming || navigator.userActivation?.isActive)) {
          const request = this.ctx.resume(); this._resuming = request;
          const clear = () => { if (this._resuming === request) this._resuming = null; };
          Promise.resolve(request).then(clear, clear); // No unhandled rejection; no delayed sound replay.
        }
        return this.ctx.state === 'running';
      } catch (_) { return false; }
    }
  };

  function travelPlan(from, to) {
    const delta = from && to ? to.spread - from.spread : 1;
    const distance = Math.abs(delta), sheets = Math.min(28, distance);
    const leafDuration = distance > 1 ? 680 : 880;
    // At most six pooled CSS renderers. More distance gives a longer riffle,
    // not hundreds of composited strips or a fabricated page destination.
    const duration = distance <= 1 ? distance * leafDuration : Math.min(4800, 1050 + 145 * sheets);
    const stagger = sheets > 1 ? (duration - leafDuration) / (sheets - 1) : 0;
    return {direction:delta < 0 ? -1 : 1, distance, sheets, leafDuration, stagger, duration,
      from:from?.right ?? 1, to:to?.right ?? 3, compressed:distance > sheets};
  }
  function neutralPaper(reference) {
    const paper = document.createElement('canvas');
    paper.width = reference.width; paper.height = reference.height;
    const ctx = paper.getContext('2d'), w = paper.width, h = paper.height;
    const gradient = ctx.createLinearGradient(0,0,w,0);
    gradient.addColorStop(0,'#ccb78f'); gradient.addColorStop(.1,'#e7d9b9'); gradient.addColorStop(.86,'#eee1c5'); gradient.addColorStop(1,'#ccba94');
    ctx.fillStyle = gradient; ctx.fillRect(0,0,w,h);
    ctx.strokeStyle = '#6f4e2822'; ctx.lineWidth = Math.max(1,w/650);
    ctx.strokeRect(w*.09,h*.08,w*.82,h*.84);
    ctx.fillStyle = '#806647'; ctx.textAlign = 'center'; ctx.font = `${Math.round(w*.026)}px Georgia,serif`;
    ctx.fillText('THE DECISION LIBRARY',w*.5,h*.06);
    // No unread narrative, fake paragraphs or misleading intermediate folio.
    return paper;
  }
  // The base DOM capture predates filled lettering. Composite only our ink
  // after its normal text/image pass; never rasterise SVG masks as white marks.
  const baseCapture=window.GamebookPaper.capturePaper;
  window.GamebookPaper.capturePaper=function(element){
    const annotations=[...element.querySelectorAll('.gothic-numerals,.ink-check')];
    if(!annotations.length)return baseCapture(element);
    const rect=element.getBoundingClientRect();
    const shapes=annotations.flatMap(svg=>[...svg.querySelectorAll('.gothic-numerals > path,.check-ink > path,.ink-flecks')].map(path=>({
      path:path.getAttribute('d'), matrix:path.getScreenCTM(), fill:getComputedStyle(path).fill,
      opacity:Number(getComputedStyle(path).opacity), rule:path.getAttribute('fill-rule')||'nonzero'
    })));
    const visibility=annotations.map(svg=>svg.style.visibility);
    let canvas;
    try{annotations.forEach(svg=>svg.style.visibility='hidden');canvas=baseCapture(element);}
    finally{annotations.forEach((svg,i)=>svg.style.visibility=visibility[i]);}
    if(!canvas)return canvas;
    const ctx=canvas.getContext('2d'),ratio=canvas.width/rect.width;
    for(const shape of shapes){
      if(!shape.matrix||shape.fill==='none')continue;
      const m=shape.matrix;ctx.save();ctx.setTransform(ratio,0,0,ratio,0,0);
      ctx.translate(-rect.left,-rect.top);ctx.transform(m.a,m.b,m.c,m.d,m.e,m.f);
      ctx.fillStyle=shape.fill;ctx.globalAlpha=Number.isFinite(shape.opacity)?shape.opacity:1;
      ctx.fill(new Path2D(shape.path),shape.rule);ctx.restore();
    }
    return canvas;
  };
  const BaseTurn = window.PageTurn;
  class RiffleTurn extends BaseTurn {
    makeStrips(front, back, w, h) {
      const count = 28, element = document.createElement('div'); element.className = 'sheet-strips pooled-leaf';
      const urls = this._textureURLs || (this._textureURLs = new WeakMap());
      const urlFor = canvas => { if (!urls.has(canvas)) urls.set(canvas, canvas.toDataURL()); return urls.get(canvas); };
      const fronts = [], backs = [], strips = [];
      for (let i=0; i<count; i++) {
        const strip = document.createElement('div'); strip.className='sheet-strip'; strip.style.width=`${w/count+.6}px`;
        for (let side=0; side<2; side++) {
          const face=document.createElement('div'); face.className=`sheet-face ${side?'back':'front'}`;
          face.style.backgroundSize=`${w}px ${h}px`; face.style.backgroundPosition=`${side?-(w-(i+1)*w/count):-i*w/count}px 0`;
          (side?backs:fronts).push(face); strip.append(face);
        }
        element.append(strip);strips.push(strip);
      }
      this.stage.append(element);
      const item = {
        element, lastT:null, index:-1,
        texture(a,b) { const x=`url(${urlFor(a)})`, y=`url(${urlFor(b)})`; fronts.forEach(n=>n.style.backgroundImage=x); backs.forEach(n=>n.style.backgroundImage=y); },
        frame(t) {
          if(t===item.lastT) return; item.lastT=t;
          const points=window.GamebookPaper.curve(w,t,count);
          strips.forEach((strip,i)=>{const p=points[i];strip.style.transform=`translate3d(${p.x}px,0,${p.z+1}px) rotateY(${p.angle}rad)`;});
          // One shading update per leaf instead of one custom property per strip.
          element.style.setProperty('--shade',String(Math.sin(Math.PI*t)*.105));
        },
        cleanup(){element.remove();}
      };
      item.texture(front,back);return item;
    }
    async turn(renderNext, {from,to}={}) {
      if(this.busy) return;
      const plan=travelPlan(from,to); this.lastPlan=plan; this.lastRenderStats=null;
      if(!plan.distance){renderNext();return;}
      const start=performance.now(); this.busy=true; this.book.classList.add('turning');
      this._textureURLs = new WeakMap();
      const cleanup=[], right=$('rightPage'), left=$('leftPage');
      const mobile=getComputedStyle(left).display==='none', rect=this.spread.getBoundingClientRect();
      const w=mobile?rect.width:rect.width/2, h=rect.height;
      let committed=false, setupMs=0, renderFailure=null;
      const commit=()=>{if(!committed){try{renderNext();committed=true;}catch(error){renderFailure=error;throw error;}}};
      try {
        // Reduced motion never pays the expensive per-character canvas capture.
        if(this.reduced || mobile || document.hidden){
          commit();
          if(!document.hidden){this.audio.play('paper',.25,plan.direction);await motion(right,[{opacity:.6},{opacity:1}],{duration:this.reduced?150:280});}
          return;
        }
        const capture=window.GamebookPaper.capturePaper;
        const oldRight=capture(right), oldLeft=capture(left);
        if(!oldRight||!oldLeft){commit();return;}
        const still=document.createElement('div');still.className='sheet-old-left';still.style.left=plan.direction>0?'0':'50%';
        still.style.backgroundImage=`url(${(plan.direction>0?oldLeft:oldRight).toDataURL()})`;this.stage.append(still);
        // Paint the result once. Reading input stays locked until the final sheet settles.
        commit();
        const nextRight=capture(right), nextLeft=capture(left), neutral=neutralPaper(oldRight);
        const counter=document.createElement('div');counter.className='riffle-counter';counter.setAttribute('aria-hidden','true');this.book.append(counter);cleanup.push(()=>counter.remove());
        const sheets=Array.from({length:plan.sheets},(_,i)=>({
          front:plan.direction>0?(i===0?oldRight:neutral):(i===plan.sheets-1?nextRight:neutral),
          back:plan.direction>0?(i===plan.sheets-1?nextLeft:neutral):(i===0?oldLeft:neutral)
        }));
        let render;
        if(this.engine==='three'){
          try{const stack=this.makeThreeStack(sheets,w,h); render=stack.frame;cleanup.push(stack.cleanup);}
          catch(_){this.engine='css3d';this.onRenderer('CSS 3D · pooled curved paper');}
        }
        let pool=[];
        if(!render){
          // Virtualise the moving sheets: 28 leaves need no more than 6 renderers.
          const poolSize=Math.min(sheets.length,plan.stagger?Math.ceil(plan.leafDuration/plan.stagger)+1:1);
          pool=Array.from({length:poolSize},()=>this.makeStrips(neutral,neutral,w,h));
          cleanup.push(()=>pool.forEach(leaf=>leaf.cleanup()));
          render=positions=>{
            const active=[];positions.forEach((p,i)=>{if(p>0 && p<1)active.push(i);});
            const used=new Set();
            for(const i of active){
              let leaf=pool.find(p=>p.index===i);
              if(!leaf){leaf=pool.find(p=>!used.has(p)&&!active.includes(p.index));if(!leaf)continue;leaf.index=i;leaf.lastT=null;leaf.texture(sheets[i].front,sheets[i].back);}
              used.add(leaf);leaf.element.hidden=false;
              leaf.element.style.zIndex=String(positions[i]<.5?sheets.length-i+3:sheets.length+i+3);leaf.frame(positions[i]);
            }
            for(const leaf of pool)if(!used.has(leaf)){leaf.element.hidden=true;leaf.index=-1;}
          };
        }
        setupMs=performance.now()-start;
        this.lastRenderStats={setup_ms:setupMs,virtual_leaves:sheets.length,active_renderers:pool.length||sheets.length,engine:this.engine};
        const sounded=new Set(), duration=plan.duration;
        await new Promise(resolve=>{
          let done=false, raf, timer;
          const finish=()=>{if(done)return;done=true;cancelAnimationFrame(raf);clearTimeout(timer);document.removeEventListener('visibilitychange',onVisibility);resolve();};
          const onVisibility=()=>{if(document.hidden)finish();};
          document.addEventListener('visibilitychange',onVisibility);
          const started=performance.now();
          const frame=now=>{
            if(done)return;
            const elapsed=Math.min(now-started,duration);
            const positions=sheets.map((_,i)=>{
              const raw=clamp((elapsed-i*plan.stagger)/plan.leafDuration,0,1);
              if(raw>0&&!sounded.has(i)){sounded.add(i);if(raw<.8)this.audio.play(plan.sheets===1?'paper':'flutter',plan.sheets===1?.7:.1,plan.direction);}
              return plan.direction>0?raw:1-raw;
            });
            this.lastProgress=elapsed/duration;
            try{render(positions);}catch(_){this.lastRenderStats.degraded=true;finish();return;}
            const t=this.lastProgress;
            counter.textContent=`${plan.direction>0?'→':'←'}  p.${Math.round(plan.from+(plan.to-plan.from)*t)} / ${to?.total||'—'} · ${plan.distance}見開き${plan.compressed?'（圧縮表示）':''}`;
            if(elapsed>=duration)finish();else raf=requestAnimationFrame(frame);
          };
          timer=setTimeout(finish,duration+700);raf=requestAnimationFrame(frame);
        });
      } catch(error) {
        if(renderFailure)throw error;
        // The server has already accepted the action. Do not leave a stale page
        // on screen merely because a decorative texture failed.
        this.lastRenderStats={...this.lastRenderStats,degraded:true};commit();
      } finally {
        // Even a renderer exception/hidden tab must release the busy flag.
        for(const fn of cleanup.reverse())try{fn();}catch(_){}
        this.stage.replaceChildren();this.book.classList.remove('turning');this.busy=false;this.lastProgress=null;
        this._textureURLs=null;
        this.lastRenderStats={...this.lastRenderStats,setup_ms:setupMs,total_ms:performance.now()-start};
      }
    }
  }
  window.PageTurn=RiffleTurn;
  window.GamebookPaper.travelPlan=travelPlan;

  // A compact timing ledger distinguishes the app from an external agent's
  // next-click interval. That interval is NOT labelled model inference time.
  const timing={phase:'ready',since:performance.now(),readySince:null,current:null,history:[],decision:null};
  function diagnostics(){
    const app=window.gamebook?.app, now=performance.now();
    return {phase:timing.phase,phase_ms:Math.round(now-timing.since),ready:!!app?.ready&&!app?.busy&&!window.gamebook?.turner?.busy,
      revision:app?.run?.revision,section:app?.run?.current,status:app?.run?.status,
      waiting_for:timing.phase==='ready'?(app?.auto?'auto_interval':'next_input'):'app',
      audio_state:window.gamebook?.audio?.ctx?.state||'not_started',
      last:timing.history.at(-1)||null,history:timing.history.slice(),renderer:window.gamebook?.turner?.lastRenderStats||null};
  }
  function updateTiming(){
    const node=$('readingPhase');if(!node)return;
    const d=diagnostics(), seconds=(d.phase_ms/1000).toFixed(1);
    const label={thinking:'要求処理中',annotating:'選択を刻んでいます',turning:'頁を探しています',ready:'次の操作待ち'};
    node.textContent=`${label[d.phase]||d.phase} · ${seconds}s`;
    node.dataset.waitingFor=d.waiting_for;
    const last=d.last;
    if($('phaseTiming'))$('phaseTiming').textContent=last?`要求 ${(last.request_ms/1000).toFixed(2)}s · 演出 ${(last.presentation_ms/1000).toFixed(2)}s`:'音の許可待ちでは操作を止めません';
  }
  const originalPhase=window.ReaderUI.phase;
  window.ReaderUI.phase=function(name){
    const now=performance.now();
    if(name==='thinking'){
      timing.current={started:now,request_ms:0,annotation_ms:0,turn_ms:0,previous_ready_ms:timing.readySince===null?null:now-timing.readySince};timing.decision=null;
    }
    const c=timing.current;
    if(c){
      if(timing.phase==='thinking')c.request_ms+=now-timing.since;
      if(timing.phase==='annotating')c.annotation_ms+=now-timing.since;
      if(timing.phase==='turning')c.turn_ms+=now-timing.since;
      if(name==='ready'){
        const run=window.gamebook?.app.run;
        timing.history.push({...c,started:undefined,finished_at:new Date().toISOString(),total_ms:now-c.started,
          presentation_ms:c.annotation_ms+c.turn_ms,source:timing.decision?.source||'setup',provider_ms:timing.decision?.provider_ms??null,
          revision:run?.revision,section:run?.current,error:window.gamebook?.app.error||null});
        if(timing.history.length>50)timing.history.shift();timing.current=null;
      }
    }
    timing.phase=name;timing.since=now;if(name==='ready')timing.readySince=now;
    originalPhase(name);updateTiming();
  };
  const originalInit=window.ReaderUI.init;
  window.ReaderUI.init=function(){
    originalInit();
    const phase=$('readingPhase');
    if(phase){
      const detail=document.createElement('span');detail.id='phaseTiming';detail.className='phase-timing';
      const panel=document.createElement('section');panel.className='timing-panel';panel.setAttribute('aria-label','処理時間の内訳');
      phase.classList.remove('sr-only');phase.setAttribute('aria-live','off');
      panel.append(phase,detail);document.querySelector('.right-rail').prepend(panel);
      const button=document.createElement('button');button.className='timing-export';button.type='button';button.textContent='待機ログ';button.title='時間の切り分けをJSON保存（本文・キーを含みません）';
      button.addEventListener('click',()=>{
        const url=URL.createObjectURL(new Blob([JSON.stringify(diagnostics(),null,2)],{type:'application/json'}));
        const a=document.createElement('a');a.href=url;a.download='reader-timing.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      });panel.append(button);
    }
    // Low-frequency text only, outside the book; never a persistent render loop.
    const tick=setInterval(()=>{if(!document.hidden)updateTiming();},500);
    window.addEventListener('pagehide',()=>clearInterval(tick),{once:true});
  };
  window.ReaderAtmosphere={version:'1.1-items',timing:diagnostics,travelPlan,inkPercentage,motion:MOTION};
})();

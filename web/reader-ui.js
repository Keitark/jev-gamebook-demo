/* Stable action desk, virtual folios and handwritten decision annotations. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const roman = n => ['I','II','III','IV','V','VI','VII','VIII','IX'][n-1] || String(n);
  const slots = [
    ['combat:attack','攻撃','通常攻撃'], ['combat:precision','精密攻撃','集中2 · 必中'],
    ['combat:guard','防御','集中を回復'], ['use:tonic','回復薬','体力を回復'],
    ['use:bandage','清め布','体力を回復'], ['use:saltbomb','鳴塩を投げる','固定ダメージ'],
    ['use:smoke','煙玉','確実に撤退'], ['combat:flee','撤退','成功判定あり'],
  ];
  const kaiSlots = [['kai:combat','1ラウンド戦う','Combat Results Table'], ['kai:evade','Evasion','敵へのダメージを放棄']];
  // Original single-stroke numeral lettering. No bundled/downloaded font binary.
  const glyph = {
    '0':'M16 3 C4 -1 1 15 3 24 C5 36 18 29 19 15 C20 6 19 3 14 3',
    '1':'M5 10 L14 2 Q12 18 11 30 M5 30 L18 29',
    '2':'M3 8 C8 -2 23 1 18 12 C15 17 7 21 2 29 Q12 27 20 29',
    '3':'M3 5 Q14 -1 19 5 Q21 12 10 16 Q23 15 18 25 Q13 34 2 28',
    '4':'M15 1 Q8 12 2 19 L21 19 M16 12 L14 32',
    '5':'M21 2 L7 3 L4 16 C20 7 22 22 15 28 Q8 34 2 28',
    '6':'M18 3 C7 -1 0 25 7 30 C19 37 26 14 9 15 L4 21',
    '7':'M2 4 Q12 2 22 3 Q12 17 9 31 M7 16 L18 15',
    '8':'M10 16 C-2 11 6 -2 16 3 C28 10 8 17 4 23 C-3 34 21 36 21 24 C21 19 5 15 10 16',
    '9':'M16 18 C0 28 0 4 13 3 C27 0 18 28 7 32',
    '.':'M9 29 L10 29.5',
    '%':'M23 2 L2 31 M6 3 C-3 2 -2 14 5 13 C12 11 11 3 6 3 M21 20 C12 20 13 33 21 31 C28 30 29 20 21 20',
  };
  const keyHash = str => [...str].reduce((n,c) => ((n*31)+c.charCodeAt(0))>>>0, 17);
  function svg(attrs) { const node=document.createElementNS(NS,'svg'); for(const [k,v] of Object.entries(attrs))node.setAttribute(k,v);return node; }
  function path(d, attrs={}) { const node=document.createElementNS(NS,'path');node.setAttribute('d',d);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,v);return node; }
  function percent(value, key) {
    const label = `${(value*100).toFixed(value===0 || value===1 || Math.abs(value*100-Math.round(value*100))<.05 ? 0 : 1)}%`;
    const width = [...label].reduce((w,c)=>w+(c==='.'?10:25),0);
    const pen=svg({viewBox:`-3 -4 ${width+6} 43`,class:'ink-percent', 'aria-hidden':'true'});
    pen.style.setProperty('--tilt',`${(keyHash(key)%15)-7}deg`);
    let x=0;
    for(const c of label) { pen.append(path(glyph[c],{transform:`translate(${x},0)`}));x+=c==='.'?10:25; }
    const readable=document.createElement('span');readable.className='sr-only ink-numeric';readable.textContent=label;
    return [pen,readable];
  }
  function circle(button) {
    const s=svg({viewBox:'0 0 600 120',preserveAspectRatio:'none',class:'ink-circle','aria-hidden':'true'});
    const variation=keyHash(button.dataset.choice||'')%8;
    const stroke=path(`M 565 ${23+variation} C 516 -2, 78 -1, 24 32 C -22 80, 64 115, 292 106 C 505 121, 604 82, 584 47 C 576 31, 558 26, 537 23`);
    stroke.setAttribute('pathLength','1');s.append(stroke);button.append(s);return stroke;
  }
  function disabledReason(run, key) {
    if(key==='combat:precision')return '集中2が必要';
    if(key==='combat:flee'||key==='kai:evade')return 'この戦闘では撤退不可';
    const item=run.character?.inventory?.find(i=>i.id===key.slice(4));
    if(!item)return '所持していない';
    if(key==='use:smoke' && !run.combat_state?.can_flee)return '退路がない';
    return '体力は最大';
  }
  function actionTitle(action) {
    return action.text.split(/\s*[—―]\s*/)[0];
  }
  function decorate(run) {
    const combat=!!run.combat_state, box=$('choices');
    document.body.classList.toggle('in-combat',combat);
    const buttons=new Map([...box.children].map(b=>[b.dataset.choice,b]));
    if(combat) {
      const fixed=run.mode==='lonewolf_kai'?kaiSlots:slots, ordered=[];
      for(const [key,title,hint] of fixed) {
        let b=buttons.get(key);
        if(b) buttons.delete(key);
        else {
          b=document.createElement('button'); b.className='choice-button unavailable';b.disabled=true;
          b.dataset.slot=key;b.setAttribute('aria-disabled','true');
          for(const cls of ['choice-roman','choice-label','choice-target']){const el=document.createElement('span');el.className=cls;b.append(el);}
        }
        b.dataset.slot=key;
        b.querySelector('.choice-label').textContent=title;
        b.querySelector('.choice-target').textContent=b.classList.contains('unavailable') ? disabledReason(run,key) : hint;
        ordered.push(b);
      }
      box.replaceChildren(...ordered,...buttons.values());
    }
    [...box.children].forEach((button,i) => {
      const key=button.dataset.choice, action=run.section.choices.find(a=>a.key===key);
      button.querySelector('.choice-roman').textContent=roman(i+1)+'.';
      button.dataset.slotIndex=String(i);button.setAttribute('aria-keyshortcuts',String(i+1));
      if(action) {
        button.dataset.actionId=key;button.id=`action-${encodeURIComponent(key)}`;
        button.setAttribute('aria-label', `${i+1}. ${action.text}`);button.title=action.text;
        if(!combat)button.querySelector('.choice-label').textContent=action.text.replace(/\s*(?:and\s+)?turn to\s+\d+\.?$/i,'').trim()||action.text;
        const explain=()=>{$('actionExplanation').textContent=action.text;};
        button.addEventListener('mouseenter',explain);button.addEventListener('focus',explain);
      } else {
        button.setAttribute('aria-label',`${i+1}. ${button.querySelector('.choice-label').textContent}（${button.querySelector('.choice-target').textContent}）`);
      }
    });
    $('actionShelf').dataset.combat=String(combat);
    $('actionExplanation').textContent=combat?'戦闘中も配置は固定。使えない行動は、その場でグレー表示。':'行動を選ぶと、この頁に判断を書き込みます。';
    $('actionCount').textContent=`${run.section.choices.length} ACTIONS`;
    $('orderMode').value=run.choice_order||'original';
    const counts=run.position_stats||{decisions:0,first_display:0};
    $('positionNote').textContent=`画面先頭の選択 ${counts.first_display} / ${counts.decisions} 回（2択以上）`;
    $('orderNote').textContent=(run.choice_order==='balanced'?'表示順：偏り検証 · 戦闘は固定配置':'表示順：原順 · 戦闘は固定配置');
    const pagination=run.pagination;
    if(pagination) {
      $('leftFolio').textContent=`— ${pagination.left} —`;
      $('rightFolio').textContent=`— ${pagination.right} —`;
      $('paginationLabel').textContent=`仮想頁 ${pagination.left}–${pagination.right} / ${pagination.total}　·　§${run.current}`;
      $('pageProgress').max=pagination.section_count;$('pageProgress').value=pagination.spread+1;
      $('book').style.setProperty('--page-position',String((pagination.spread+1)/pagination.section_count));
    }
    $('choices').scrollTop=0;
  }
  function phase(name) {
    document.body.dataset.phase=name;
    $('readingPhase').textContent=({ready:'操作できます',thinking:'判断中',annotating:'選択を記入しています',turning:'頁を探しています'})[name]||name;
  }
  async function annotate(decision,{audio,reduced=false}={}) {
    phase('annotating');
    const source=decision.probability_source || (decision.source==='random'?'uniform':decision.source==='browser'?'browser_self_report':'provider');
    const scores=decision.probabilities||{}, hasScores=Object.keys(scores).length>0;
    $('inkLegend').textContent=hasScores ? (source==='uniform'?'Random の抽選確率':source==='browser_self_report'?'ブラウザAIの自己申告':'モデルが返した選択確率') : decision.source==='forced'?'分岐なし · エンジン処理':'手動選択 · 確率情報なし';
    $('inkLegend').hidden=false;
    const available=[...$('choices').querySelectorAll('[data-choice]')];
    const selected=available.find(b=>b.dataset.choice===decision.choice);
    for(const b of available) {
      const v=scores[b.dataset.choice];
      if(typeof v==='number' && Number.isFinite(v))b.append(...percent(v,b.dataset.choice));
    }
    if(!selected)return;
    // Only the local shelf scrolls; never move the page or viewport for an effect.
    const parent=$('choices');
    const r=selected.getBoundingClientRect(),pr=parent.getBoundingClientRect();
    if(r.bottom>pr.bottom)parent.scrollTop+=r.bottom-pr.bottom+5;
    if(r.top<pr.top)parent.scrollTop+=r.top-pr.top-5;
    selected.classList.add('ink-picked');
    const stroke=circle(selected);
    audio?.play('slash',.18);
    if(reduced) { stroke.style.strokeDashoffset='0'; await sleep(90); return; }
    const marks=available.flatMap(b=>[...b.querySelectorAll('.ink-percent')]);
    marks.forEach((m,i)=>m.animate([{opacity:0,translate:'4px -3px'},{opacity:1,translate:'0 0'}],{duration:160,delay:Math.min(i*40,200),fill:'both'}));
    await stroke.animate([{strokeDashoffset:'1'},{strokeDashoffset:'0'}],{duration:350,easing:'cubic-bezier(.15,.7,.4,1)',fill:'forwards'}).finished;
    await sleep(520);
  }
  function clearInk() {
    document.querySelectorAll('.ink-percent,.ink-circle,.ink-numeric').forEach(n=>n.remove());
    document.querySelectorAll('.ink-picked').forEach(n=>n.classList.remove('ink-picked'));
    $('inkLegend').hidden=true;
  }
  function init() {
    const shelf=$('actionShelf');
    shelf.addEventListener('mouseleave',()=>{$('actionExplanation').textContent=document.body.classList.contains('in-combat')?'戦闘中も配置は固定。使えない行動は、その場でグレー表示。':'行動の詳細はボタンにカーソルを合わせると表示。';});
  }
  window.ReaderUI={init,decorate,annotate,clearInk,phase};
})();

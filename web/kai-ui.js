/* Project Aon / Lone Wolf Kai core-rules compatibility UI. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const rules = [
    ['COMBAT SKILL と ENDURANCE', '新しいKaiキャラクターはCOMBAT SKILL 10〜19、ENDURANCE 20〜29。ENDURANCEが0以下になると冒険終了。'],
    ['Combat Ratio', '戦闘時のCOMBAT SKILLから敵のCOMBAT SKILLを引き、その差をCombat RatioとしてCombat Results Tableに使う。'],
    ['Random Number Table', '各戦闘ラウンドで0〜9を1つ抽選し、Combat Ratioと交差する表の結果で双方のENDURANCE減少を同時に処理する。Kは即死。'],
    ['Weaponskill', '選んだ武器を使用している時はCOMBAT SKILL +2。武器を1つも所持していない場合はCOMBAT SKILL −4。使用武器は1つだけ。'],
    ['Mindblast', 'Kai Disciplineを持ち、敵がMindblastに免疫でなければCOMBAT SKILL +2。'],
    ['Healing', 'Healingを持つ場合、戦闘のない番号節を通過するごとにENDURANCEを1回復する。開始時最大値を超えない。'],
    ['装備と荷物', '武器は最大2個、Backpackは最大8枠、Gold Crownsは最大50。Healing Potionは戦闘外でENDURANCEを4回復する。'],
    ['Evasion', '本文が回避を許す戦闘だけで選べる。回避するラウンドも通常どおり表を引くが、敵へのダメージは無視し、Lone Wolf側の損失だけ適用して逃げる。'],
    ['互換モードの範囲', 'Project Aon XMLのcombat属性と分岐リンクを自動処理する。本文だけに書かれた一時補正、アイテム取得、食事指示、特殊品効果は推測して自動化しない。'],
  ];
  let run = null, step = null, tab = 'inventory', busy = false;
  const text = (id, value) => { $(id).textContent = value; };
  const card = (title, detail, badge='') => {
    const el = document.createElement('article'); el.className = 'journal-card';
    const head = document.createElement('div'); head.className = 'journal-card-head';
    const strong = document.createElement('strong'); strong.textContent = title; head.append(strong);
    if (badge) { const tag=document.createElement('span'); tag.className='item-badge'; tag.textContent=badge; head.append(tag); }
    const p=document.createElement('p'); p.textContent=detail; el.append(head,p); return el;
  };
  function journal() {
    if (!run?.character || run.mode !== 'lonewolf_kai') return;
    const c=run.character, out=$('journalContents'); out.replaceChildren();
    document.querySelectorAll('[data-journal-tab]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.journalTab===tab)));
    if (tab==='inventory') {
      const active=c.active_weapon || 'Bare hands';
      out.append(card('使用中の武器', active, 'ACTIVE'));
      for (const weapon of c.weapons) {
        const el=card(weapon, weapon===active ? '現在の戦闘に使用する武器。' : '所持している武器。', weapon===active ? '使用中' : 'WEAPON');
        const action=run.section.choices.find(a=>a.key===`kai:equip:${weapon}`);
        if (action) { const btn=document.createElement('button'); btn.className='journal-action'; btn.textContent='この武器を使う'; btn.disabled=busy||run.status!=='live'; btn.addEventListener('click',()=>{$('journalDialog').close();step(action.key);});el.append(btn); }
        out.append(el);
      }
      for (const item of c.backpack) {
        const el=card(item.name+(item.count>1?` ×${item.count}`:''), item.name==='Healing Potion'?'ENDURANCEを4回復する。':'Backpack Item', 'BACKPACK');
        const action=run.section.choices.find(a=>a.key==='kai:potion' && item.name==='Healing Potion');
        if (action) { const btn=document.createElement('button');btn.className='journal-action';btn.textContent='使う';btn.disabled=busy||run.status!=='live';btn.addEventListener('click',()=>{$('journalDialog').close();step(action.key);});el.append(btn); }
        out.append(el);
      }
      out.append(card('Gold Crowns', String(c.gold), `MAX ${c.limits.gold}`));
      if (c.special_items.length) for (const item of c.special_items) out.append(card(item,'Special Item','SPECIAL'));
      else out.append(card('Special Items','なし。','SPECIAL'));
    } else if (tab==='clues') {
      out.append(card('Kai Disciplines', c.disciplines.join(' ／ '), `${c.disciplines.length} DISCIPLINES`));
      if (c.disciplines.includes('Weaponskill')) out.append(card('Weaponskill', c.weaponskill_weapon+' を使用中なら COMBAT SKILL +2。','+2 CS'));
      if (c.disciplines.includes('Mindblast')) out.append(card('Mindblast','免疫のない敵に対し COMBAT SKILL +2。','+2 CS'));
      if (c.disciplines.includes('Healing')) out.append(card('Healing','戦闘のない番号節を通過するごとに ENDURANCE +1。','+1 END'));
      out.append(card('現在のCOMBAT SKILL内訳', c.combat_skill_notes.join(' · '), `TOTAL ${c.combat_skill}`));
    } else {
      for (const [title,detail] of rules) out.append(card(title,detail));
    }
  }
  function open(tabName) {
    if (!run?.character || run.mode!=='lonewolf_kai') return;
    window.gamebook?.stop(true); tab=tabName; journal(); $('journalDialog').showModal();
  }
  function render(next) {
    run=next; const active=run.mode==='lonewolf_kai';
    document.body.classList.toggle('kai-mode',active);
    if (!active) return;
    document.body.classList.remove('rpg-mode');
    $('characterPanel').hidden=false; $('journalButtons').hidden=false;
    $('battlePanel').hidden=!run.combat_state; $('combatBanner').hidden=!run.combat_state;
    $('blockedChoices').replaceChildren(); $('battleEvents').replaceChildren();
    text('modeTitle','KAI RULES · PROJECT AON');
    text('modeDetail','Combat Results Table・Action Chart・Kai Disciplines。本文固有の状態変化は推測しません。');
    document.querySelector('label[for="hpMeter"]').textContent='ENDURANCE';
    document.querySelector('label[for="focusMeter"]').closest('.vital-row').hidden=true; $('focusMeter').hidden=true;
    const supplies=document.querySelectorAll('.supply-row > div > span'); if(supplies[0])supplies[0].textContent='Gold Crowns';if(supplies[1])supplies[1].textContent='Combat Ratio';
    text('hpValue',`${run.character.endurance} / ${run.character.max_endurance}`); $('hpMeter').max=run.character.max_endurance;$('hpMeter').value=run.character.endurance;
    text('goldValue',run.character.gold); text('tideValue',run.combat_state?`${run.combat_state.combat_ratio>=0?'+':''}${run.combat_state.combat_ratio}`:'—'); $('tideValue').classList.remove('urgent');
    text('gearStats',`COMBAT SKILL ${run.character.combat_skill} · Base ${run.character.base_combat_skill} · ${run.character.active_weapon||'Bare hands'}`);
    const tabs=document.querySelectorAll('[data-journal-tab]');if(tabs[0])tabs[0].textContent='Action Chart';if(tabs[1])tabs[1].textContent='Kai Disciplines';if(tabs[2])tabs[2].textContent='互換ルール';
    $('bagBtn').textContent='Action Chart';$('cluesBtn').textContent='Disciplines';$('rulesBtn').textContent='?';
    const b=run.combat_state;
    if(b){
      text('combatBanner',`⚔ ${b.name} · Round ${b.round} · Combat Ratio ${b.combat_ratio>=0?'+':''}${b.combat_ratio}`);
      text('enemyName',b.name); text('enemyHP',`${b.endurance} / ${b.max_endurance}`); $('enemyMeter').max=b.max_endurance;$('enemyMeter').value=b.endurance;
      text('enemyStats',`COMBAT SKILL ${b.combat_skill} · ${b.mindblast_immune?'Mindblast immune':'Mindblast applicable'}`);
      text('enemyIntent','COMBAT RESULTS TABLE'); text('enemyHint','0〜9のRandom NumberとCombat Ratioから双方のENDURANCE損失を決定。');
      text('combatRound',`ROUND ${String(b.round).padStart(2,'0')}`); text('preparedNote',b.can_evade?'本文がEvasionを許している。':'Evasion option is not detected in this passage.');
    }
    for(const ev of run.last_decision?.events||[]){const li=document.createElement('li');li.textContent=ev.text;li.dataset.kind=ev.kind;$('battleEvents').append(li);}
    $('battleLogPanel').hidden=!run.last_decision?.events?.length;
    if($('journalDialog').open) journal();
  }
  window.KaiUI={
    init(callback){
      step=callback;
      $('bagBtn').addEventListener('click',()=>open('inventory'));
      $('cluesBtn').addEventListener('click',()=>open('clues'));
      $('rulesBtn').addEventListener('click',()=>open('rules'));
      document.querySelectorAll('[data-journal-tab]').forEach(b=>b.addEventListener('click',()=>{if(run?.mode!=='lonewolf_kai')return;tab=b.dataset.journalTab;journal();}));
    },
    render,
    busy(value){busy=value;document.querySelectorAll('.journal-action').forEach(b=>b.disabled=value||run?.status!=='live');},
    sound(events,audio){const kinds=new Set((events||[]).map(e=>e.kind));if(kinds.has('victory'))audio.play('victory');else if(kinds.has('combat')||kinds.has('hurt'))audio.play('clash',.2);else if(kinds.has('heal'))audio.play('heal',.65);else if(kinds.has('dice'))audio.play('dice',.3);else if(kinds.has('flee'))audio.play('page',.25);},
  };
})();

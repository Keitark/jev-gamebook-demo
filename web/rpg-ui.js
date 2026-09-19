/* Inventory/character views consume authoritative server snapshots only. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const text = (id, value) => { $(id).textContent = value; };
  const KINDS = {weapon:'武器', armor:'防具', heal:'回復', bomb:'投擲', smoke:'撤退', quest:'大事なもの'};
  const rules = [
    ['戦闘の一手', '攻撃、防御、精密攻撃、薬の使用、撤退のいずれかで一手。通常攻撃はd6＋技量＋武器命中が敵の回避値以上で命中。被害はd6＋武器威力−装甲（最低1）。'],
    ['敵の予備動作を読む', '大振りは威力＋3。「溜め」「立て直し」では敵は攻撃しない。「身を固める」は敵の回避値＋2。構えは毎手、先に表示する。'],
    ['集中と防御', '精密攻撃は集中2で必中、武器威力＋5、敵装甲を無視。防御は集中＋2、今回の回避＋2、被害−4、次の通常攻撃の命中＋2。集中の上限は4。防御の備えは重複しない。'],
    ['敵の命中', '敵はd6＋敵技量≧7＋敏捷の半分（切捨て）で命中。防御時は目標値がさらに2上がる。敵の威力はd6＋敵威力、そこから防具と防御の軽減を引く。最小被害0。'],
    ['荷物と装備', '武器と防具は各1点。入手しただけでは能力は変わらない。装備変更は戦闘外のみ。回復薬と清め布は戦闘中も使えるが敵の手番が進む。食事は戦闘外のみ。回復は上限を超えない。'],
    ['撤退と戦利品', '撤退可能な戦闘ではd6＋敏捷≧8で成功。煙玉なら確実に撤退。逃げた敵は次の遭遇で全快するが、倒した敵は復活せず、戦利品も一度だけ。最終戦からは撤退できない。'],
    ['潮と探索', '時計ではなく行動コスト。〔潮位＋N〕の選択と明記された出来事で進む。戦闘ラウンドや道具操作では進まない。16で時間切れ。揚水場は一度だけ3下げる。'],
    ['手がかりと結末', '選択できない理由は頁の下に表示。Jevにも実際に選べる行動だけを渡す。鍵、協力者、契約の原本などの記録は「手がかり」タブに残る。手入力のプロフィールで能力や道具は増えない。'],
    ['記録について', '「記録を保存」で選択、ダイス、状態の前後、結末をJSON保存。サーバーを再起動すると実行中の旅は失われる。この版に保存ファイルの読込機能はない。'],
  ];
  let run = null, step = null, tab = 'inventory', busy = false;
  function meter(id, value, max) { const m = $(id); m.max = max; m.value = value; }
  function card(title, detail, badge = '') {
    const el = document.createElement('article'); el.className = 'journal-card';
    const head = document.createElement('div'); head.className = 'journal-card-head';
    const name = document.createElement('strong'); name.textContent = title; head.append(name);
    if (badge) { const tag = document.createElement('span'); tag.className = 'item-badge'; tag.textContent = badge; head.append(tag); }
    const p = document.createElement('p'); p.textContent = detail; el.append(head, p); return el;
  }
  function journal() {
    if (!run?.character || run.mode !== 'story_rpg') return;
    const c = run.character, container = $('journalContents'); container.replaceChildren();
    document.querySelectorAll('[data-journal-tab]').forEach(b => { b.setAttribute('aria-pressed', String(b.dataset.journalTab === tab)); });
    if (tab === 'inventory') {
      for (const item of c.inventory) {
        const el = card(item.name + (item.count > 1 ? ` ×${item.count}` : ''), item.description,
          item.equipped ? '装備中' : KINDS[item.kind]);
        const action = run.section.choices.find(a => a.key === `use:${item.id}` || a.key === `equip:${item.id}`);
        if (action) {
          const button = document.createElement('button'); button.className = 'journal-action';
          button.textContent = action.kind === 'equipment' ? '装備する' : '使う';
          button.disabled = busy || run.status !== 'live';
          button.addEventListener('click', () => { $('journalDialog').close(); step(action.key); }); el.append(button);
        }
        container.append(el);
      }
    } else if (tab === 'clues') {
      container.append(card('協力してくれる人', c.allies.length ? c.allies.join(' ／ ') : 'まだいない。'));
      container.append(card('揚水場', c.sluice_open ? '始動済み。街の水の逃げ道ができた。' : '未始動。'));
      for (const clue of c.clues) container.append(card(clue.title, clue.text, '記録済み'));
      if (!c.clues.length) container.append(card('白い余白', '探索で見聞きした手がかりが、ここに記されていく。'));
    } else {
      for (const [title, detail] of rules) container.append(card(title, detail));
    }
  }
  function open(tabName) { if (!run?.character || run.mode !== 'story_rpg') return; window.gamebook?.stop(true); tab = tabName; journal(); $('journalDialog').showModal(); }
  function render(next) {
    run = next; const active = run.mode === 'story_rpg';
    document.body.classList.toggle('rpg-mode', active);
    $('characterPanel').hidden = !active; $('journalButtons').hidden = !active;
    $('battlePanel').hidden = !active || !run.combat_state;
    $('combatBanner').hidden = !active || !run.combat_state;
    $('blockedChoices').replaceChildren(); $('battleEvents').replaceChildren();
    text('modeTitle', active ? 'FULL RULES · 日本語編' : 'NAVIGATION EDITION');
    text('modeDetail', active ? '戦闘・装備・所持品・条件判定あり。' : '分岐を辿る実験版。戦闘・所持品・条件判定は未実装。');
    if (!active) { if ($('journalDialog').open && document.body.classList.contains('rpg-mode')) $('journalDialog').close(); return; }
    document.querySelector('label[for="hpMeter"]').textContent = '体力';
    document.querySelector('label[for="focusMeter"]').closest('.vital-row').hidden = false; $('focusMeter').hidden = false;
    document.querySelector('label[for="focusMeter"]').textContent = '集中';
    const supplies = document.querySelectorAll('.supply-row > div > span'); if (supplies[0]) supplies[0].textContent = '銀貨'; if (supplies[1]) supplies[1].textContent = '潮位';
    const tabs = document.querySelectorAll('[data-journal-tab]'); if (tabs[0]) tabs[0].textContent = '荷物と装備'; if (tabs[1]) tabs[1].textContent = '手がかり'; if (tabs[2]) tabs[2].textContent = 'ルール';
    $('bagBtn').textContent = '荷物・装備'; $('cluesBtn').textContent = '手がかり'; $('rulesBtn').textContent = '?';
    $('leftPage').lang = 'ja'; $('rightPage').lang = 'ja';
    text('hpValue', `${run.character.hp} / ${run.character.max_hp}`);
    meter('hpMeter', run.character.hp, run.character.max_hp);
    text('focusValue', `${run.character.focus} / ${run.character.max_focus}`);
    meter('focusMeter', run.character.focus, run.character.max_focus);
    text('goldValue', run.character.gold); text('tideValue', `${run.character.tide} / ${run.character.tide_limit}`);
    $('tideValue').classList.toggle('urgent', run.character.tide >= 12);
    text('gearStats', `技量 ${run.character.skill}　敏捷 ${run.character.agility}　威力 ${run.character.power}　装甲 ${run.character.armor}`);
    for (const choice of run.blocked_choices || []) {
      const el = document.createElement('div'); el.className = 'blocked-choice';
      const label = document.createElement('strong'); label.textContent = '未達条件 · ' + choice.text;
      const detail = document.createElement('span'); detail.textContent = choice.reason;
      el.append(label, detail); $('blockedChoices').append(el);
    }
    const b = run.combat_state;
    if (b) {
      text('combatBanner', `⚔　${b.name}　／　第 ${b.round} 手`);
      text('enemyName', b.name); text('enemyHP', `${b.hp} / ${b.max_hp}`);
      meter('enemyMeter', b.hp, b.max_hp);
      text('enemyIntent', b.intent_name); text('enemyHint', b.intent_hint);
      text('enemyStats', `回避 ${b.guard} · 装甲 ${b.armor} · 技量 ${b.skill}`);
      text('combatRound', `ROUND ${String(b.round).padStart(2, '0')}`);
      text('preparedNote', b.prepared ? '防御の備え：次の通常攻撃 命中＋2' : '表示は次の敵の構え。先にあなたが行動する。');
    }
    for (const ev of run.last_decision?.events || []) {
      const li = document.createElement('li'); li.textContent = ev.text; li.dataset.kind = ev.kind;
      $('battleEvents').append(li);
    }
    $('battleLogPanel').hidden = !run.last_decision?.events?.length;
    if ($('journalDialog').open) journal();
  }
  window.RPGUI = {
    init(callback) {
      step = callback;
      $('bagBtn').addEventListener('click', () => open('inventory'));
      $('cluesBtn').addEventListener('click', () => open('clues'));
      $('rulesBtn').addEventListener('click', () => open('rules'));
      document.querySelectorAll('[data-journal-tab]').forEach(b => b.addEventListener('click', () => { tab = b.dataset.journalTab; journal(); }));
    },
    render,
    busy(value) { busy = value; document.querySelectorAll('.journal-action').forEach(b => { b.disabled = value || run?.status !== 'live'; }); },
    sound(events, audio) {
      const kinds = new Set((events || []).map(e => e.kind));
      if (kinds.has('victory')) audio.play('victory');
      else if (kinds.has('hit') || kinds.has('hurt')) audio.play('clash', .22);
      else if (kinds.has('heal')) audio.play('heal', .7);
      else if (kinds.has('guard')) audio.play('guard', .25);
      else if (kinds.has('dice')) audio.play('dice', .3);
      else if (kinds.has('equip')) audio.play('tap');
    },
  };
})();

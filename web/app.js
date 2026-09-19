(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const roman = n => ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'][n - 1] || String(n);
  const sourceNames = {random: 'RANDOM / UNIFORM', jev: 'JEV / TYPESAFE', openrouter: 'JEV / OPENROUTER', manual: 'MANUAL / HUMAN', forced: 'ENGINE / CONTINUATION'};
  const readPref = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch (_) { return fallback; } };
  const savePref = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {} };
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const text = (id, value) => { $(id).textContent = value; };
  const audio = new PaperAudio({enabled: readPref('gb.sound', false), volume: readPref('gb.volume', .35)});
  const turner = new PageTurn({book: $('book'), spread: $('spread'), stage: $('turnStage'), audio, onRenderer: label => text('rendererStatus', label)});
  turner.reduced = readPref('gb.motion', matchMedia('(prefers-reduced-motion: reduce)').matches);
  document.body.classList.toggle('large-type', readPref('gb.largeType', false));
  const app = {run: null, status: null, busy: false, auto: false, timer: null, ready: false, error: null};
  let noticeTimer;

  function notice(message, error = false) {
    clearTimeout(noticeTimer); text('notice', message);
    $('notice').classList.toggle('error', error); $('notice').hidden = false;
    if (!error) noticeTimer = setTimeout(() => { $('notice').hidden = true; }, 5000);
  }
  function log(message, detail = '') {
    const li = document.createElement('li'), time = document.createElement('time'), line = document.createElement('span');
    time.textContent = new Date().toLocaleTimeString('ja-JP', {hour12: false}); line.className = 'event-text'; line.textContent = message;
    if (detail) { const small = document.createElement('small'); small.textContent = detail; line.append(small); }
    li.append(time, line); $('events').prepend(li);
    while ($('events').children.length > 60) $('events').lastChild.remove();
  }
  async function api(path, data) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 70000);
    try {
      const options = {signal: controller.signal, headers: {}};
      if (data !== undefined) {
        options.method = 'POST'; options.headers = {'Content-Type': 'application/json', 'X-Gamebook-Token': app.status.csrf};
        options.body = JSON.stringify(data);
      }
      const response = await fetch(path, options);
      let result;
      try { result = await response.json(); } catch (_) { throw new Error('サーバーがJSON以外の応答を返しました。'); }
      if (!response.ok) { const error = new Error(result.error || `HTTP ${response.status}`); error.status = response.status; throw error; }
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('通信がタイムアウトしました。自動リトライはしません。次の操作前に現在の節を確認してください。');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function soundButton() {
    $('soundBtn').setAttribute('aria-pressed', String(audio.enabled));
    $('soundBtn').querySelector('span').textContent = audio.enabled ? '音 ON' : '音 OFF';
    $('soundBtn').querySelector('use').setAttribute('href', audio.enabled ? '#i-sound' : '#i-mute');
  }
  function controls() {
    const live = app.run?.status === 'live';
    $('stepBtn').disabled = app.busy || !live;
    $('resetBtn').disabled = app.busy; $('settingsBtn').disabled = app.busy;
    $('backend').disabled = app.busy; $('exportBtn').disabled = !app.run || app.busy;
    $('autoBtn').disabled = !live && !app.auto;
    $('autoBtn').setAttribute('aria-pressed', String(app.auto));
    $('autoBtn').querySelector('span').textContent = app.auto ? '停止する' : '連続実行';
    $('autoBtn').querySelector('use').setAttribute('href', app.auto ? '#i-stop' : '#i-play');
    $('stepBtn').querySelector('span').textContent = app.busy ? ($('backend').value === 'random' ? 'ページを進めています…' : '判断を待っています…') : '次の一手';
    document.querySelectorAll('.choice-button').forEach(button => { button.disabled = app.busy || !live; });
    if (!live && app.run) text('helpText', '旅が終わりました。記録を保存するか、新しい旅を始めてください。');
    else if (app.auto) text('helpText', '自動実行中 · 停止すると現在の1手を終えて止まります');
    else text('helpText', '1–3 で選択 · Space で1手 · A で自動実行');
  }
  function backendNote() {
    const value = $('backend').value;
    text('backendNote', value === 'random' ? '候補から均等に選択。API呼び出しなし。' : '1手ごとにAPIを呼び出します。キーは .env から。');
    savePref('gb.backend', value);
  }
  function stop(silent = false) {
    const was = app.auto; app.auto = false; clearTimeout(app.timer); app.timer = null; controls();
    if (was && !silent) log('Auto paused', app.busy ? '通信中の1手が完了してから停止します。' : '自動実行を停止しました。');
  }
  function showDecision(d) {
    $('decisionEmpty').hidden = !!d; $('decisionPanel').hidden = !d;
    if (!d) return;
    text('decisionSource', `${sourceNames[d.source] || d.source} · LAST STEP`);
    text('decisionFrom', String(d.section).padStart(2, '0')); text('decisionTo', String(d.target).padStart(2, '0'));
    text('pickedText', d.choice_text);
    $('confidenceRow').hidden = d.confidence === null;
    text('confidenceName', d.source === 'random' ? '選択の抽選確率' : 'Model confidence');
    text('confidenceValue', d.confidence === null ? '—' : `${Math.round(d.confidence * 100)}%`);
    $('probabilities').replaceChildren();
    for (const [i, option] of (d.options || []).entries()) {
      const probability = d.probabilities?.[option.key];
      if (typeof probability !== 'number') continue;
      const row = document.createElement('div'); row.className = 'probability'; row.classList.toggle('selected', option.key === d.choice);
      const head = document.createElement('div'); head.className = 'prob-head';
      const label = document.createElement('span'); label.className = 'prob-label'; label.title = option.text;
      label.textContent = `${roman(i + 1)} · ${option.text}`;
      const value = document.createElement('span'); value.textContent = `${(probability * 100).toFixed(1)}%`;
      head.append(label, value);
      const track = document.createElement('div'); track.className = 'prob-track';
      track.setAttribute('role', 'meter'); track.setAttribute('aria-label', option.text);
      track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', '100'); track.setAttribute('aria-valuenow', String(probability * 100));
      const fill = document.createElement('div'); fill.className = 'prob-fill'; fill.style.width = `${probability * 100}%`; track.append(fill);
      row.append(head, track); $('probabilities').append(row);
    }
    const model = ['jev', 'openrouter'].includes(d.source);
    text('latencyName', model ? 'API往復時間' : 'ローカル選択時間');
    text('latencyValue', ['manual', 'forced'].includes(d.source) ? 'API call: none' : `${d.latency_ms.toFixed(model ? 0 : 2)} ms`);
    text('decisionNote', d.source === 'random' ? '均等分布からの抽選です。Jevの推論結果ではありません。' :
      d.source === 'manual' ? 'あなたが選んだ分岐です。モデルへの問い合わせはしていません。' :
      d.source === 'forced' ? '分岐のない続きはエンジンが進めます。モデル呼び出しは不要です。' : '選択確率やconfidenceは、冒険のクリア率ではありません。');
  }
  function render(run) {
    app.run = run;
    const section = run.section;
    text('sectionStat', run.current.padStart(2, '0')); text('movesStat', run.steps); text('visitedStat', new Set(run.path).size);
    text('runStatus', run.status === 'live' ? 'EXPLORING' : run.status.toUpperCase());
    text('bookTitle', run.title); text('runningTitle', run.title.toUpperCase()); text('sectionNumber', run.current);
    text('passageTitle', section.title || `Section ${run.current}`);
    text('bookCaption', run.book === 'demo' ? 'AN ORIGINAL SHORT ADVENTURE' : 'PROJECT AON · LONE WOLF I');
    text('sourceNote', run.book === 'demo' ? 'Original story & illustration. Navigation edition.' : 'Text: Project Aon. Decorative illustration is not from the book.');
    text('ledgerLabel', run.last_decision ? `LAST DECISION · § ${run.last_decision.section}` : 'YOUR CHARGE');
    text('ledgerNote', run.last_decision ? `“${run.last_decision.choice_text}”` : run.objective);
    text('leftFolio', `— ${roman(run.steps + 1).toLowerCase()} —`); text('rightFolio', `— ${run.current} —`);
    text('pathCount', run.path.length); $('path').replaceChildren();
    const visiblePath = run.path.slice(-45);
    if (run.path.length > 45) { const el = document.createElement('span'); el.textContent = '…'; $('path').append(el); }
    visiblePath.forEach((sid, i) => { const el = document.createElement('span'); el.textContent = sid; if (i === visiblePath.length - 1) el.className = 'current'; $('path').append(el); });
    $('path').scrollTop = $('path').scrollHeight;
    $('storyText').replaceChildren();
    const paragraphs = section.paragraphs?.length ? section.paragraphs : section.text.split(/\n\s*\n/);
    for (const paragraph of paragraphs) { const p = document.createElement('p'); p.textContent = paragraph; $('storyText').append(p); }
    $('choices').replaceChildren();
    section.choices.forEach((choice, i) => {
      const button = document.createElement('button'); button.className = 'choice-button'; button.dataset.choice = choice.key;
      const num = document.createElement('span'); num.className = 'choice-roman'; num.textContent = roman(i + 1) + '.';
      const label = document.createElement('span'); label.className = 'choice-label';
      label.textContent = choice.text.replace(/\s*(?:and\s+)?turn to\s+\d+\.?$/i, '').trim() || choice.text;
      const target = document.createElement('span'); target.className = 'choice-target'; target.textContent = `§ ${choice.target}`;
      button.append(num, label, target); button.title = `選択 ${i + 1} → ${choice.target}`;
      button.addEventListener('click', () => step(choice.key)); $('choices').append(button);
    });
    $('ending').hidden = run.status === 'live';
    $('choices').hidden = run.status !== 'live';
    text('choiceHeading', run.status === 'live' ? 'Which path will you take?' : 'The end of this journey');
    if (run.status !== 'live') {
      text('endingTitle', run.status === 'success' ? 'Your journey is complete.' : run.status === 'deadend' ? 'Your story ends here.' : 'The book is closed for now.');
      text('endingNote', run.status === 'success' ? (run.book === 'demo' ? 'A letter delivered. A path remembered.' : 'Ending section reached. Full rules were not simulated.') : `Run stopped: ${run.status.replaceAll('_', ' ')}.`);
    }
    updateScrollHint(); requestAnimationFrame(updateScrollHint);
    $('passageScroll').scrollTop = 0; showDecision(run.last_decision);
    try { sessionStorage.setItem('gb.run', run.run_id); } catch (_) {}
    controls();
  }
  function updateScrollHint() {
    const el = $('passageScroll');
    const more = el.scrollHeight - el.clientHeight - el.scrollTop > 8;
    $('pageHint').classList.toggle('scroll-hint', more);
    text('pageHint', more ? '↓ ページ内をスクロールして続きを表示' : app.run?.section.combat?.length ? 'Combat described · rules not simulated' : 'Choose a passage to turn the page');
  }
  $('passageScroll').addEventListener('scroll', updateScrollHint, {passive:true});
  new ResizeObserver(updateScrollHint).observe($('passageScroll'));
  async function step(choice = null) {
    if (app.busy || app.run?.status !== 'live') return;
    if (choice) stop(true);
    app.busy = true; controls(); $('notice').hidden = true;
    try {
      await audio.unlock(); soundButton(); audio.play('ink');
      const data = {revision: app.run.revision, backend: $('backend').value};
      if (choice) data.choice = choice;
      const result = await api(`/api/runs/${app.run.run_id}/step`, data);
      const selected = [...$('choices').children].find(b => b.dataset.choice === result.last_decision.choice);
      selected?.classList.add('selected'); showDecision(result.last_decision);
      await wait(turner.reduced ? 30 : 320);
      await turner.turn(() => render(result));
      const d = result.last_decision;
      log(`§ ${d.section} → § ${d.target}`, sourceNames[d.source]);
      if (result.status !== 'live') {
        stop(true); audio.play(result.status === 'success' ? 'win' : 'end');
        log(result.status === 'success' ? 'Journey complete' : 'Journey ended', result.status);
      }
    } catch (error) {
      stop(true); app.error = error.message; notice(error.message, true); log('Step paused', error.message);
      // Resynchronise after a stale duplicate, but never repeat a paid decision.
      if (error.status === 409 && app.run) {
        try { render(await api(`/api/runs/${app.run.run_id}`)); } catch (_) {}
      }
    } finally {
      app.busy = false; controls();
      if (app.auto && app.run.status === 'live') app.timer = setTimeout(() => step(), Number($('pace').value));
    }
  }
  async function newRun({book, profile, seed} = {}) {
    stop(true); app.busy = true; controls();
    try {
      const run = await api('/api/runs', {book: book || app.run?.book || 'demo', profile: profile ?? $('profile').value, seed: seed ?? Number($('seed').value)});
      render(run); $('events').replaceChildren(); log('A new journey', run.title); $('notice').hidden = true;
    } finally { app.busy = false; controls(); }
  }
  function refreshStatus() {
    for (const value of ['jev', 'openrouter']) {
      const option = $('backend').querySelector(`option[value="${value}"]`);
      option.disabled = !app.status.keys[value];
      option.textContent = `Jev — ${value === 'jev' ? 'TypeSafe' : 'OpenRouter'}${option.disabled ? '（キー未設定）' : ''}`;
    }
    text('keyStatus', `TypeSafe: ${app.status.keys.jev ? '設定済み' : '未設定'} / OpenRouter: ${app.status.keys.openrouter ? '設定済み' : '未設定'}。キーを .env に記入したらサーバーを再起動してください。`);
    $('connection').classList.remove('error'); $('connection').querySelector('span').textContent = 'LOCAL READING ROOM';
    const needsAon = $('bookSelect').value === 'aon' && !app.status.books.find(b => b.id === 'aon').ready;
    $('aonInstall').hidden = !needsAon;
  }
  $('stepBtn').addEventListener('click', () => step());
  $('autoBtn').addEventListener('click', async () => {
    if (app.auto) { stop(); return; }
    if (app.busy || app.run?.status !== 'live') return;
    app.auto = true; controls();
    await audio.unlock(); soundButton();
    if (!app.auto) return;
    log('Auto started', $('backend').selectedOptions[0].textContent); step();
  });
  $('backend').addEventListener('change', () => { stop(true); backendNote(); });
  $('resetBtn').addEventListener('click', async () => {
    if (app.busy) return;
    if (app.run?.steps && !confirm('新しい旅を始めます。現在の記録は必要なら先に保存してください。')) return;
    try { await audio.unlock(); await newRun(); } catch (error) { notice(error.message, true); }
  });
  $('soundBtn').addEventListener('click', async () => { await audio.toggle(); savePref('gb.sound', audio.enabled); soundButton(); });
  $('settingsBtn').addEventListener('click', () => {
    stop(); $('bookSelect').value = app.run?.book || 'demo'; refreshStatus(); $('settings').showModal();
  });
  $('bookSelect').addEventListener('change', refreshStatus);
  $('licenseCheck').addEventListener('change', () => { $('downloadBtn').disabled = !$('licenseCheck').checked; });
  $('downloadBtn').disabled = true;
  $('downloadBtn').addEventListener('click', async () => {
    $('downloadBtn').disabled = true; text('downloadBtn', '取得しています…');
    try { app.status = await api('/api/books/aon/download', {license_reviewed: $('licenseCheck').checked}); refreshStatus(); notice('公式XMLを取得しました。設定を適用すると開きます。'); }
    catch (error) { notice(error.message, true); }
    finally { $('downloadBtn').disabled = !$('licenseCheck').checked; text('downloadBtn', '公式XMLを取得'); }
  });
  $('volume').value = Math.round(audio.volume * 100); text('volumeLabel', `${$('volume').value}%`);
  $('volume').addEventListener('input', () => { audio.setVolume(Number($('volume').value) / 100); savePref('gb.volume', audio.volume); text('volumeLabel', `${$('volume').value}%`); });
  $('motion').checked = turner.reduced;
  $('motion').addEventListener('change', () => { turner.reduced = $('motion').checked; savePref('gb.motion', turner.reduced); });
  $('largeType').checked = document.body.classList.contains('large-type');
  $('largeType').addEventListener('change', () => { document.body.classList.toggle('large-type', $('largeType').checked); savePref('gb.largeType', $('largeType').checked); });
  $('applySettings').addEventListener('click', async () => {
    $('applySettings').disabled = true;
    try {
      const seed = Number($('seed').value);
      if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) throw new Error('seed は 0〜4294967295 の整数にしてください。');
      await newRun({book: $('bookSelect').value, profile: $('profile').value, seed}); $('settings').close();
    } catch (error) { notice(error.message, true); }
    finally { $('applySettings').disabled = false; }
  });
  $('exportBtn').addEventListener('click', async () => {
    if (!app.run) return;
    try {
      const result = await api(`/api/runs/${app.run.run_id}/export`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type: 'application/json'}));
      const a = document.createElement('a'); a.href = url; a.download = `gamebook-${app.run.book}-${Date.now()}.json`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { notice(error.message, true); }
  });
  document.addEventListener('keydown', event => {
    if ($('settings').open || /^(INPUT|TEXTAREA|SELECT|BUTTON|A)$/.test(event.target.tagName) || event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
    if (/^[1-9]$/.test(event.key)) {
      const choice = app.run?.section.choices[Number(event.key) - 1];
      if (choice) { event.preventDefault(); step(choice.key); }
    } else if (event.code === 'Space') { event.preventDefault(); step(); }
    else if (event.key.toLowerCase() === 'a') { event.preventDefault(); $('autoBtn').click(); }
    else if (event.key === 'Escape') stop();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { stop(); audio.suspend(); } });
  window.addEventListener('pagehide', () => { stop(true); audio.suspend(); });

  async function boot() {
    app.busy = true; controls(); soundButton();
    try {
      app.status = await api('/api/status'); refreshStatus();
      let backend = readPref('gb.backend', 'random');
      if (!['random', 'jev', 'openrouter'].includes(backend) || (backend !== 'random' && !app.status.keys[backend])) backend = 'random';
      $('backend').value = backend; backendNote();
      let oldId;
      try { oldId = sessionStorage.getItem('gb.run'); } catch (_) {}
      if (oldId) {
        try { render(await api(`/api/runs/${oldId}`)); log('Journey resumed', app.run.title); } catch (_) { oldId = null; }
      }
      if (!oldId) await newRun({book: 'demo', profile: '', seed: 17});
      app.ready = true;
    } catch (error) {
      app.error = error.message; $('connection').classList.add('error'); $('connection').querySelector('span').textContent = 'CONNECTION ERROR';
      notice(`接続できませんでした。python web_app.py で起動してください。 ${error.message}`, true);
    } finally { app.busy = false; controls(); }
  }
  // Read-only state plus public UI operations for automated interaction tests.
  window.gamebook = {app, audio, turner, step, newRun, stop};
  boot();
})();

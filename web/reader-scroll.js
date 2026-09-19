/* Auto-read long passages for visual/browser-use readers.
 * Only the narrative viewport moves. The fixed action shelf never moves.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const state = {
    busy: false, token: 0, promise: Promise.resolve(), section: null,
    reason: 'idle', passes: 0, maxScroll: 0,
  };

  function phase(name) {
    document.body.dataset.phase = name;
    const live = $('readingPhase');
    if (live) live.textContent = name === 'reading' ? '本文を読んでいます' : '操作できます';
  }

  function marker(show, label = 'READING ↓') {
    let node = document.getElementById('autoReadMarker');
    if (!node) {
      node = document.createElement('div');
      node.id = 'autoReadMarker';
      node.className = 'auto-read-marker';
      node.setAttribute('aria-hidden', 'true');
      $('rightPage')?.append(node);
    }
    node.textContent = label;
    node.hidden = !show;
  }

  function cancel(reason = 'cancelled') {
    state.token += 1;
    state.reason = reason;
    state.busy = false;
    marker(false);
    const el = $('passageScroll');
    if (el) el.classList.remove('auto-reading');
    if (document.body.dataset.phase === 'reading') phase('ready');
  }

  function animateScroll(el, target, duration, token) {
    const start = el.scrollTop, distance = target - start;
    if (Math.abs(distance) < 2) return Promise.resolve(true);
    const begin = performance.now();
    return new Promise(resolve => {
      const frame = now => {
        if (token !== state.token) return resolve(false);
        const t = Math.min(1, (now - begin) / duration);
        const eased = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        el.scrollTop = start + distance * eased;
        if (t < 1) requestAnimationFrame(frame); else resolve(true);
      };
      requestAnimationFrame(frame);
    });
  }

  async function waitForReady(token) {
    const started = performance.now();
    while (token === state.token) {
      const p = document.body.dataset.phase || 'ready';
      if (p === 'ready' && !window.gamebook?.turner?.busy) return true;
      if (performance.now() - started > 9000) return false;
      await sleep(80);
    }
    return false;
  }

  async function run(sectionId, token) {
    const el = $('passageScroll');
    if (!el) return;
    // Let fonts, Japanese line breaking and the page-turn renderer settle.
    if (!await waitForReady(token)) return;
    await sleep(260);
    if (token !== state.token) return;

    const max = Math.max(0, el.scrollHeight - el.clientHeight);
    state.maxScroll = max;
    if (max <= 18) {
      el.scrollTop = 0;
      state.reason = 'fits';
      state.busy = false;
      return;
    }

    state.busy = true;
    state.reason = 'reading';
    state.passes = 0;
    phase('reading');
    marker(true);
    el.classList.add('auto-reading');
    el.scrollTop = 0;

    // Give the visual model a clean first view before moving.
    await sleep(620);
    const stepSize = Math.max(120, el.clientHeight * .72);
    let target = 0;
    while (token === state.token && target < max - 2 && state.passes < 10) {
      target = Math.min(max, target + stepSize);
      state.passes += 1;
      marker(true, target >= max - 2 ? 'READING · END' : `READING ↓ ${state.passes}`);
      const ok = await animateScroll(el, target, 620, token);
      if (!ok) return;
      await sleep(target >= max - 2 ? 620 : 460);
    }
    if (token !== state.token) return;

    // Leave the text at the end: the action shelf is fixed and remains visible.
    el.scrollTop = max;
    el.classList.remove('auto-reading');
    marker(false);
    state.busy = false;
    state.reason = 'done';
    if (document.body.dataset.phase === 'reading') phase('ready');
  }

  function schedule(run) {
    if (!run || !run.current) return;
    // Combat/item turns stay on the same section; don't reread the passage.
    if (state.section === run.current) return;
    state.section = run.current;
    cancel('new-section');
    state.section = run.current;
    state.busy = true;
    state.reason = 'pending';
    const token = state.token;
    state.promise = run.current ? runAuto(run.current, token) : Promise.resolve();
  }

  async function runAuto(sectionId, token) {
    try { await run(sectionId, token); }
    finally {
      if (token === state.token && state.busy) {
        state.busy = false;
        marker(false);
        $('passageScroll')?.classList.remove('auto-reading');
        if (document.body.dataset.phase === 'reading') phase('ready');
      }
    }
  }

  async function finish() {
    try { await state.promise; } catch (_) {}
  }

  function snapshot() {
    const el = $('passageScroll');
    return {
      busy: state.busy, section: state.section, reason: state.reason,
      passes: state.passes, scrollTop: el?.scrollTop || 0,
      maxScroll: Math.max(0, (el?.scrollHeight || 0) - (el?.clientHeight || 0)),
    };
  }

  function init() {
    const el = $('passageScroll');
    if (!el) return;
    // A person explicitly touching/wheeling the passage takes control.
    for (const type of ['wheel', 'touchstart', 'pointerdown']) {
      el.addEventListener(type, () => {
        if (state.busy) cancel('manual-scroll');
      }, {passive: true});
    }
  }

  window.ReaderScroll = {init, schedule, finish, cancel, snapshot, get busy(){ return state.busy; }};
})();

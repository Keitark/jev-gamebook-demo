/* Original procedural effects. No sound files, autoplay, music or network calls. */
(() => {
  'use strict';
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  function rng(seed) {
    let s = seed | 0;
    return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return (s >>> 0) / 4294967296; };
  }
  function noise(ctx, duration, seed) {
    const random = rng(seed || 18371);
    const buffer = ctx.createBuffer(1, Math.ceil(duration * ctx.sampleRate), ctx.sampleRate);
    const samples = buffer.getChannelData(0);
    let previous = 0;
    for (let i = 0; i < samples.length; i++) {
      const white = random() * 2 - 1;
      previous = (previous + .025 * white) / 1.025;
      const t = i / ctx.sampleRate;
      // Paper fibres: a broad swish with a soft, irregular flutter.
      const flutter = .55 + .22 * Math.sin(t * 97) + .13 * Math.sin(t * 163 + .6);
      samples[i] = (white * .58 + previous * 3) * flutter;
    }
    return buffer;
  }
  function tone(ctx, output, when, hz, gain, length) {
    const oscillator = ctx.createOscillator(), envelope = ctx.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(hz, when);
    oscillator.frequency.exponentialRampToValueAtTime(hz * .994, when + length);
    envelope.gain.setValueAtTime(0, when);
    envelope.gain.linearRampToValueAtTime(gain, when + .012);
    envelope.gain.exponentialRampToValueAtTime(.0001, when + length);
    oscillator.connect(envelope).connect(output);
    oscillator.start(when); oscillator.stop(when + length + .02);
    oscillator.onended = () => { oscillator.disconnect(); envelope.disconnect(); };
  }
  function synth(ctx, destination, kind, when, duration, seed, direction = 1, level = 1) {
    const output = ctx.createGain(); output.gain.value = level; output.connect(destination);
    if (kind === 'slash' || kind === 'flutter') {
      const length = kind === 'slash' ? .16 : .095;
      const src=ctx.createBufferSource();src.buffer=noise(ctx,length,seed);
      const hp=ctx.createBiquadFilter(),band=ctx.createBiquadFilter(),env=ctx.createGain(),pan=ctx.createStereoPanner();
      hp.type='highpass';hp.frequency.value=kind==='slash'?1000:600;
      band.type='lowpass';band.Q.value=.6;
      band.frequency.setValueAtTime(kind==='slash'?7200:4000,when);
      band.frequency.exponentialRampToValueAtTime(1300,when+length);
      env.gain.setValueAtTime(0,when);env.gain.linearRampToValueAtTime(kind==='slash'?.55:.35,when+.007);
      env.gain.exponentialRampToValueAtTime(.0001,when+length);
      pan.pan.setValueAtTime(.3*direction,when);pan.pan.linearRampToValueAtTime(-.3*direction,when+length);
      src.connect(hp).connect(band).connect(env).connect(pan).connect(output);
      src.start(when);src.stop(when+length);
      src.onended=()=>[src,hp,band,env,pan].forEach(n=>n.disconnect());
      if(kind==='slash')tone(ctx,output,when+.014,170,.075,.045);
    } else if (kind === 'paper' || kind === 'ink') {
      const length = kind === 'ink' ? .12 : Math.max(.25, duration);
      const source = ctx.createBufferSource(); source.buffer = noise(ctx, length, seed);
      const hp = ctx.createBiquadFilter(), lp = ctx.createBiquadFilter(), envelope = ctx.createGain();
      hp.type = 'highpass'; hp.frequency.value = kind === 'ink' ? 1200 : 310;
      lp.type = 'lowpass'; lp.Q.value = .45;
      lp.frequency.setValueAtTime(kind === 'ink' ? 4000 : 1900, when);
      if (kind === 'paper') {
        lp.frequency.linearRampToValueAtTime(3400, when + length * .47);
        lp.frequency.linearRampToValueAtTime(900, when + length * .98);
      }
      envelope.gain.setValueAtTime(0, when);
      envelope.gain.linearRampToValueAtTime(kind === 'ink' ? .18 : .8, when + length * .12);
      envelope.gain.linearRampToValueAtTime(kind === 'ink' ? .08 : .48, when + length * .62);
      envelope.gain.linearRampToValueAtTime(0, when + length);
      const pan = ctx.createStereoPanner();
      pan.pan.setValueAtTime(.4 * direction, when);
      pan.pan.linearRampToValueAtTime(-.4 * direction, when + length);
      source.connect(hp).connect(lp).connect(envelope).connect(pan).connect(output);
      source.start(when); source.stop(when + length);
      if (kind === 'paper') tone(ctx, output, when + length * .88, 86, .12, .16);
      source.onended = () => { [source, hp, lp, envelope, pan].forEach(n => n.disconnect()); };
    } else if (kind === 'clash') {
      const src = ctx.createBufferSource(); src.buffer = noise(ctx, .19, seed);
      const filter = ctx.createBiquadFilter(), env = ctx.createGain();
      filter.type = 'highpass'; filter.frequency.value = 950;
      env.gain.setValueAtTime(.24, when); env.gain.exponentialRampToValueAtTime(.0001, when + .18);
      src.connect(filter).connect(env).connect(output); src.start(when); src.stop(when + .19);
      src.onended = () => { src.disconnect(); filter.disconnect(); env.disconnect(); };
      tone(ctx, output, when, 430, .09, .23); tone(ctx, output, when, 1173, .045, .16);
    } else if (kind === 'guard') {
      tone(ctx, output, when, 160, .16, .12); tone(ctx, output, when + .03, 320, .06, .18);
    } else if (kind === 'heal') {
      [392, 493.88, 587.33].forEach((hz, i) => tone(ctx, output, when + i * .1, hz, .055, .45));
    } else if (kind === 'dice') {
      [0, .07, .16].forEach((t, i) => tone(ctx, output, when + t, 900 - i * 170, .09 - i * .02, .06));
    } else if (kind === 'victory') {
      tone(ctx, output, when, 293.66, .09, .55); tone(ctx, output, when + .1, 440, .06, .5);
    } else if (kind === 'win') {
      [261.63, 329.63, 392].forEach((hz, i) => tone(ctx, output, when + i * .13, hz, .11, .95));
    } else if (kind === 'end') {
      tone(ctx, output, when, 146.83, .13, .9);
      tone(ctx, output, when + .06, 220, .05, .6);
    } else if (kind === 'tap') {
      tone(ctx, output, when, 660, .05, .08);
    }
    // A silent source provides a cleanup clock in both live and offline contexts.
    const cleanup = ctx.createBufferSource(); cleanup.buffer = ctx.createBuffer(1, 1, ctx.sampleRate);
    cleanup.connect(ctx.createGain()); cleanup.start(when + Math.max(duration, 1.5) + .1);
    cleanup.onended = () => { output.disconnect(); cleanup.disconnect(); };
  }

  class PaperAudio {
    constructor({enabled = false, volume = .35} = {}) {
      this.enabled = enabled; this.volume = clamp(volume, 0, 1);
      this.ctx = null; this.master = null; this.events = []; this.counter = 0;
    }
    async unlock() {
      if (!this.enabled) return;
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) { this.enabled = false; return; }
      try {
        if (!this.ctx) {
          this.ctx = new Context(); this.master = this.ctx.createGain();
          this.master.gain.value = this.volume * .7;
          this.master.connect(this.ctx.destination);
        }
        if (this.ctx.state === 'suspended') await this.ctx.resume();
      } catch (_) { this.enabled = false; }
    }
    setVolume(value) {
      this.volume = clamp(Number(value) || 0, 0, 1);
      if (this.master) this.master.gain.setTargetAtTime(this.enabled ? this.volume * .7 : 0, this.ctx.currentTime, .025);
    }
    async toggle() {
      this.enabled = !this.enabled;
      await this.unlock(); this.setVolume(this.volume);
      if (this.enabled) this.play('tap');
      return this.enabled;
    }
    play(kind, duration = 1.15, direction = 1) {
      if (!this.enabled || !this.ctx || this.ctx.state !== 'running' || !this.volume) return;
      const seed = 9137 + ++this.counter * 217;
      this.events.push({kind, duration, direction, seed, time: performance.now(), volume: this.volume * .7});
      if (this.events.length > 1000) this.events.shift();
      synth(this.ctx, this.master, kind, this.ctx.currentTime + .005, duration, seed, direction);
    }
    async suspend() { if (this.ctx?.state === 'running') await this.ctx.suspend(); }
    // Used by the reproducible capture tool: exactly the same synth and event timing.
    static async renderWav(events, seconds) {
      const rate = 44100;
      const ctx = new OfflineAudioContext(2, Math.ceil(seconds * rate), rate);
      for (const ev of events) {
        if (ev.time < 0 || ev.time / 1000 >= seconds) continue;
        synth(ctx, ctx.destination, ev.kind, ev.time / 1000, ev.duration, ev.seed, ev.direction, ev.volume);
      }
      const audio = await ctx.startRendering(), frames = audio.length;
      const bytes = new ArrayBuffer(44 + frames * 4), view = new DataView(bytes);
      function string(at, str) { for (let i = 0; i < str.length; i++) view.setUint8(at + i, str.charCodeAt(i)); }
      string(0, 'RIFF'); view.setUint32(4, 36 + frames * 4, true); string(8, 'WAVE');
      string(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
      view.setUint16(22, 2, true); view.setUint32(24, rate, true); view.setUint32(28, rate * 4, true);
      view.setUint16(32, 4, true); view.setUint16(34, 16, true); string(36, 'data'); view.setUint32(40, frames * 4, true);
      const left = audio.getChannelData(0), right = audio.getChannelData(1);
      for (let i = 0; i < frames; i++) {
        view.setInt16(44 + i * 4, clamp(left[i], -1, 1) * 32767, true);
        view.setInt16(46 + i * 4, clamp(right[i], -1, 1) * 32767, true);
      }
      return new Blob([bytes], {type: 'audio/wav'});
    }
  }
  window.PaperAudio = PaperAudio;
})();

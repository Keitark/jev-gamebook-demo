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
        const matches = [...node.textContent.matchAll(/\S+/g)];
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
      if (node.tagName === 'IMG') {
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
    async turn(renderNext) {
      if (this.busy) return;
      this.busy = true; this.book.classList.add('turning');
      const right = document.getElementById('rightPage'), left = document.getElementById('leftPage');
      const mobile = getComputedStyle(left).display === 'none';
      const rect = this.spread.getBoundingClientRect(), w = mobile ? rect.width : rect.width / 2, h = rect.height;
      let cleanup = () => {};
      try {
        const front = capturePaper(right), oldLeft = capturePaper(left);
        const still = document.createElement('div'); still.className = 'sheet-old-left';
        if (oldLeft) still.style.backgroundImage = `url(${oldLeft.toDataURL()})`;
        else still.style.display = 'none';
        this.stage.append(still);
        // A front cover prevents a new-text flash while the back texture is captured.
        const cover = document.createElement('div'); cover.className = 'sheet-old-left';
        cover.style.left = mobile ? '0' : '50%'; cover.style.width = mobile ? '100%' : '50%';
        cover.style.backgroundImage = `url(${front.toDataURL()})`; cover.style.zIndex = '5';
        this.stage.append(cover);
        renderNext();
        const back = capturePaper(mobile ? right : left);
        if (this.reduced || mobile) {
          this.audio.play('paper', .32);
          const animation = cover.animate([{opacity: 1, transform: 'translateX(0)'}, {opacity: 0, transform: 'translateX(-12px)'}], {duration: 240, easing: 'ease-out'});
          await animation.finished;
          return;
        }
        const shadow = document.createElement('div'); shadow.className = 'sheet-shadow'; this.stage.append(shadow);
        const mode = this.engine;
        let frame;
        if (mode === 'three') {
          try {
            const three = this.makeThree(front, back, w, h);
            frame = three.frame; cleanup = three.cleanup;
          } catch (_) {
            this.engine = 'css3d'; this.onRenderer('CSS 3D · curved paper');
          }
        }
        if (!frame) {
          const css = this.makeStrips(front, back, w, h); frame = css.frame; cleanup = css.cleanup;
        }
        frame(0); cover.remove();
        this.audio.play('paper', this.duration / 1000);
        this.onRenderer(this.engine === 'three' ? 'Three.js r180 · curved mesh' : 'CSS 3D · curved paper');
        await new Promise(resolve => {
          const started = performance.now();
          const draw = now => {
            const t = clamp((now - started) / this.duration, 0, 1);
            this.lastProgress = t; frame(t);
            const p = smooth(t);
            shadow.style.opacity = String(Math.sin(Math.PI * p) * .18);
            shadow.style.transform = `scaleX(${.35 + Math.abs(Math.cos(Math.PI * p)) * .65})`;
            if (t < 1) requestAnimationFrame(draw); else resolve();
          };
          requestAnimationFrame(draw);
        });
      } finally {
        cleanup(); this.stage.replaceChildren(); this.book.classList.remove('turning');
        this.busy = false; this.lastProgress = null;
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
    makeThree(front, back, w, h) {
      const T = this.THREE, renderer = this.renderer, cols = 56, rows = 12;
      const pad = Math.ceil(h * .45), totalW = w * 2 + pad * 2, totalH = h + pad * 2;
      renderer.setSize(totalW, totalH);
      Object.assign(renderer.domElement.style, {left: `${-pad}px`, top: `${-pad}px`, width: `${totalW}px`, height: `${totalH}px`});
      this.stage.append(renderer.domElement);
      const scene = new T.Scene();
      const camera = new T.PerspectiveCamera(2 * Math.atan(totalH / 3000) * 180 / Math.PI, totalW / totalH, 1, 3000);
      camera.position.z = 1500;
      const geometry = new T.BufferGeometry();
      const positions = new Float32Array((cols + 1) * (rows + 1) * 3);
      const colors = new Float32Array(positions.length), uvs = new Float32Array((cols + 1) * (rows + 1) * 2), indices = [];
      for (let y = 0; y <= rows; y++) for (let x = 0; x <= cols; x++) {
        const i = y * (cols + 1) + x; uvs[i * 2] = x / cols; uvs[i * 2 + 1] = 1 - y / rows;
        if (y < rows && x < cols) { const a = i, b = i + 1, c = i + cols + 1, d = c + 1; indices.push(a, c, b, b, c, d); }
      }
      geometry.setAttribute('position', new T.BufferAttribute(positions, 3).setUsage(T.DynamicDrawUsage));
      geometry.setAttribute('color', new T.BufferAttribute(colors, 3).setUsage(T.DynamicDrawUsage));
      geometry.setAttribute('uv', new T.BufferAttribute(uvs, 2)); geometry.setIndex(indices);
      const ftex = new T.CanvasTexture(front), btex = new T.CanvasTexture(back);
      [ftex, btex].forEach(tex => { tex.colorSpace = T.SRGBColorSpace; tex.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8); });
      btex.repeat.x = -1; btex.offset.x = 1;
      const fmat = new T.MeshBasicMaterial({map: ftex, side: T.FrontSide, vertexColors: true, toneMapped: false});
      const bmat = new T.MeshBasicMaterial({map: btex, side: T.BackSide, vertexColors: true, toneMapped: false});
      const frontMesh = new T.Mesh(geometry, fmat), backMesh = new T.Mesh(geometry, bmat);
      frontMesh.frustumCulled = backMesh.frustumCulled = false; scene.add(frontMesh, backMesh);
      return {
        frame(t) {
          const pts = curve(w, t, cols), bend = Math.sin(Math.PI * t);
          for (let y = 0; y <= rows; y++) for (let x = 0; x <= cols; x++) {
            const i = (y * (cols + 1) + x) * 3, p = pts[x];
            positions[i] = p.x;
            positions[i + 1] = h / 2 - y * h / rows;
            positions[i + 2] = p.z + 1 + bend * 13 * (y / rows - .5) * (x / cols) ** 2;
            const shade = 1 - bend * (.025 + .08 * Math.abs(Math.sin(p.angle)));
            colors[i] = colors[i + 1] = colors[i + 2] = shade;
          }
          geometry.attributes.position.needsUpdate = true; geometry.attributes.color.needsUpdate = true;
          renderer.render(scene, camera);
        },
        cleanup() { renderer.clear(); renderer.domElement.remove(); geometry.dispose(); ftex.dispose(); btex.dispose(); fmat.dispose(); bmat.dispose(); }
      };
    }
  }
  window.PageTurn = PageTurn;
  window.GamebookPaper = {capturePaper, curve};
})();

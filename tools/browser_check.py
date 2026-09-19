"""Render the real assets in Chromium and bridge only our local JSON API.

This in-memory harness is useful in environments whose browser policy blocks
localhost navigation. It does not change browser policy or mock model results.
For normal full-HTTP testing use tools/smoke_browser.py instead.
"""
from __future__ import annotations
import base64
import json
import re
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from web_app import LocalServer


def memory_page(page, server):
    def bridge(data):
        if not re.fullmatch(r"/api/[a-zA-Z0-9_/-]+", data['path']):
            raise ValueError('Only the test server JSON API may be bridged')
        body = data.get('body')
        req = Request(f"http://127.0.0.1:{server.server_port}" + data['path'],
                      data=body.encode() if body else None,
                      headers=data.get('headers', {}), method=data.get('method', 'GET'))
        try:
            with urlopen(req, timeout=70) as r:
                return {'status': r.status, 'body': r.read().decode()}
        except HTTPError as exc:
            return {'status': exc.code, 'body': exc.read().decode()}
    page.expose_function('__localApiTestBridge', bridge)
    html = (ROOT / 'web/index.html').read_text(encoding="utf-8")
    html = re.sub(r'<link[^>]*>', '', html)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    svg = base64.b64encode((ROOT / 'web/engraving.svg').read_bytes()).decode()
    html = html.replace('/static/engraving.svg', f'data:image/svg+xml;base64,{svg}')
    page.set_content(html)
    for style in ('style.css', 'rpg.css', 'reader.css'):
        page.add_style_tag(content=(ROOT / 'web' / style).read_text(encoding="utf-8"))
    page.evaluate('''() => {
        window.fetch = async (url, init = {}) => {
            if (!String(url).startsWith('/api/')) throw new Error('Not a local test API route');
            const r = await window.__localApiTestBridge({path:String(url),method:init.method || 'GET',body:init.body,headers:init.headers || {}});
            return new Response(r.body, {status:r.status, headers:{'Content-Type':'application/json'}});
        };
    }''')
    for name in ['rpg-ui.js', 'kai-ui.js', 'sound.js', 'page-turn.js', 'reader-ui.js', 'app.js']:
        page.add_script_tag(content=(ROOT / 'web' / name).read_text(encoding="utf-8"))
    page.wait_for_function('window.gamebook?.app.ready', timeout=10000)
    page.evaluate('document.fonts.ready')


def main():
    server = LocalServer(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    output = Path('/mnt/data/jev-live-preview'); output.mkdir(exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':1600, 'height':1000}, device_scale_factor=1)
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            memory_page(page, server)
            page.evaluate("gamebook.newRun({book:'demo', seed:17})")
            page.screenshot(path=str(output/'screen-initial.png'))
            print(json.dumps(page.evaluate('''() => ({
                ready:gamebook.app.ready,renderer:gamebook.turner.engine,overflow:document.body.scrollWidth>innerWidth,
                paper:document.getElementById('rightPage').getBoundingClientRect().toJSON(),
                scroll:[document.getElementById('passageScroll').scrollHeight,document.getElementById('passageScroll').clientHeight],
                verso:[document.querySelector('.verso-content').scrollHeight,document.querySelector('.verso-content').clientHeight]
            })''')))
            page.locator('#soundBtn').click()
            page.locator('[data-choice="c0"]').click()
            page.wait_for_function('gamebook.turner.busy', timeout=5000)
            page.wait_for_timeout(460)
            page.screenshot(path=str(output/'screen-turn.png'))
            page.wait_for_function('!gamebook.app.busy', timeout=7000)
            page.screenshot(path=str(output/'screen-after.png'))
            print('After', page.evaluate('({section:gamebook.app.run.current,sound:gamebook.audio.enabled,audioState:gamebook.audio.ctx?.state,events:gamebook.audio.events})'))
            print('Browser errors', errors)
            page.set_viewport_size({'width':390, 'height':844})
            page.wait_for_timeout(100)
            page.screenshot(path=str(output/'screen-mobile.png'),full_page=True)
            print('Mobile overflow', page.evaluate('document.body.scrollWidth > innerWidth'))
            browser.close()
    finally:
        server.shutdown();server.server_close()

if __name__ == '__main__':
    main()

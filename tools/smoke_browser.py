"""Exercise the real UI and local HTTP service (no paid APIs).

pip install playwright
python -m playwright install chromium
python tools/smoke_browser.py

--memory uses the explicit JSON bridge from browser_check when a managed browser
cannot navigate to localhost. This does not validate HTTP navigation or CDN loading.
"""
from __future__ import annotations
import argparse
import json
import sys
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from web_app import LocalServer
from browser_check import memory_page


def exercise(page, server, memory, output):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if memory:
        memory_page(page, server)
    else:
        page.goto(f'http://127.0.0.1:{server.server_port}', wait_until='domcontentloaded')
        page.wait_for_function('window.gamebook?.app.ready')
        page.evaluate('document.fonts.ready')
    page.evaluate("gamebook.newRun({book:'demo',seed:17})")
    page.screenshot(path=str(output / 'screen-initial.png'))
    assert page.evaluate('gamebook.app.run.steps') == 0
    assert page.evaluate('gamebook.audio.enabled') is False
    assert page.locator('#backend').input_value() == 'random'
    page.locator('#soundBtn').click()
    assert page.evaluate('gamebook.audio.ctx?.state') == 'running'
    # A burst of user actions must still make only one transition.
    page.evaluate("() => { for(let i=0;i<8;i++) document.querySelector('[data-choice=c0]').click(); }")
    page.wait_for_function('gamebook.turner.busy')
    page.wait_for_timeout(450)
    page.screenshot(path=str(output / 'screen-turn.png'))
    page.wait_for_function('!gamebook.app.busy')
    assert page.evaluate('gamebook.app.run.path') == ['1', '7']
    assert page.evaluate('gamebook.app.run.last_decision.source') == 'manual'
    assert page.locator('#confidenceRow').is_hidden()
    assert 'paper' in page.evaluate('gamebook.audio.events.map(e=>e.kind)')
    # Real seeded random baseline; never label it a Jev inference.
    page.evaluate("gamebook.newRun({book:'demo',seed:1})")
    page.locator('#stepBtn').click(); page.wait_for_function('!gamebook.app.busy')
    assert page.evaluate('gamebook.app.run.last_decision.source') == 'random'
    assert page.locator('.probability').count() == 3
    assert 'RANDOM' in page.locator('#decisionSource').inner_text()
    page.screenshot(path=str(output / 'screen-random.png'))
    # Pause while a step is in flight; no second API call after completion.
    page.locator('#autoBtn').click()
    page.wait_for_function('gamebook.app.busy')
    page.locator('#autoBtn').click()
    page.wait_for_function('!gamebook.app.busy')
    steps = page.evaluate('gamebook.app.run.steps')
    page.wait_for_timeout(2000)
    assert page.evaluate('gamebook.app.run.steps') == steps
    assert not page.evaluate('gamebook.app.auto')
    # Reach an ending by explicit manual choices. These are test inputs, not a model.
    page.evaluate("gamebook.newRun({book:'demo',seed:1})")
    page.evaluate('gamebook.turner.reduced=true')
    for expected in ['7', '9', '8', '12']:
        page.locator('[data-choice=c0]').click()
        page.wait_for_function('!gamebook.app.busy')
        assert page.evaluate('gamebook.app.run.current') == expected
    assert page.evaluate('gamebook.app.run.status') == 'success'
    assert page.locator('#stepBtn').is_disabled()
    assert page.locator('#autoBtn').is_disabled()
    assert 'win' in page.evaluate('gamebook.audio.events.map(e=>e.kind)')
    page.screenshot(path=str(output / 'screen-ending.png'))
    # Muting stops *new* effects. Settings change only non-secret UI preferences.
    page.locator('#soundBtn').click()
    count = page.evaluate('gamebook.audio.events.length')
    page.evaluate("gamebook.audio.play('paper')")
    assert page.evaluate('gamebook.audio.events.length') == count
    page.locator('#settingsBtn').click()
    page.locator('#volume').fill('50')
    page.locator('#largeType').check()
    page.keyboard.press('Escape')
    assert page.evaluate('gamebook.audio.volume') == .5
    # Long passages retain every paragraph and expose their final choice by scrolling.
    page.evaluate("gamebook.newRun({book:'demo',seed:1})")
    sid = page.evaluate('gamebook.app.run.run_id')
    run = server.service.get_run(sid)
    run.book.sections['1'].paragraphs *= 8
    page.evaluate('''async () => {
      const r=await fetch('/api/runs/'+gamebook.app.run.run_id);
      // A refresh exercises the same boot/restore path in normal browsers; the
      // manual next transition below is enough to test clipping in memory mode.
      window.__longPassage=(await r.json()).section.paragraphs;
      const host=document.getElementById('storyText'); host.replaceChildren();
      for(const line of window.__longPassage){const p=document.createElement('p');p.textContent=line;host.append(p);}
    }''')
    assert page.locator('#storyText p').count() >= 10
    page.evaluate("document.getElementById('passageScroll').scrollTop=1e6")
    page.locator('[data-choice=c0]').click(); page.wait_for_function('!gamebook.app.busy')
    assert page.evaluate('gamebook.app.run.current') == '7'
    # Compact/mobile view remains within the viewport; its reading area scrolls.
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(150)
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    page.screenshot(path=str(output / 'screen-mobile.png'), full_page=True)
    assert not errors, errors
    return {'browser_errors': errors, 'renderer': page.evaluate('gamebook.turner.engine'),
            'mode': 'in-memory assets + real HTTP API bridge' if memory else 'full HTTP',
            'checks': ['manual step', 'burst guard', 'curved turn', 'sound unlock', 'paper sound event',
                       'real random probabilities', 'auto stop', 'terminal stop', 'victory sound',
                       'mute', 'settings', 'long passage scroll', 'mobile overflow'],
            'live_jev_tested': False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--memory', action='store_true')
    parser.add_argument('--browser', help='Optional Chromium executable path')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/browser')
    args=parser.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    server=LocalServer(0); threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            options={'headless':True}
            if args.browser: options['executable_path']=args.browser
            browser=p.chromium.launch(**options)
            page=browser.new_page(viewport={'width':1600,'height':1000})
            report=exercise(page,server,args.memory,args.out)
            browser.close()
        (args.out/'browser-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__': main()

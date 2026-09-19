"""Real UI + server regression checks for browser-use and ink/page effects.

--memory is the explicit managed-browser fallback; no paid model is invoked.
"""
import argparse
import json
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from web_app import LocalServer, GamebookService
from browser_check import memory_page


def main():
    p=argparse.ArgumentParser();p.add_argument('--memory',action='store_true');p.add_argument('--browser');p.add_argument('--out',type=Path,default=ROOT/'artifacts/reader')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[]
    fixture_dir=tempfile.TemporaryDirectory()
    (Path(fixture_dir.name)/'01fftd.xml').write_bytes((ROOT/'tests/kai_fixture.xml').read_bytes())
    server=LocalServer(0,GamebookService(Path(fixture_dir.name)));threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            opts={'headless':True}
            if args.browser:opts['executable_path']=args.browser
            browser=pw.chromium.launch(**opts)
            page=browser.new_page(viewport={'width':1920,'height':1080})
            page.on('pageerror',lambda e:errors.append(str(e)))
            if args.memory:memory_page(page,server)
            else:
                page.goto(f'http://127.0.0.1:{server.server_port}');page.wait_for_function('gamebook.app.ready')
            page.evaluate('gamebook.turner.reduced=true')
            def call(key):
                page.evaluate('(key)=>gamebook.step(key)',key)
                assert page.evaluate('gamebook.app.error') is None
            def rect(selector): return page.locator(selector).bounding_box()
            base=rect('#book');shelf=rect('#actionShelf');control=rect('#stepBtn')
            assert page.locator('#choices').count()==1 and page.locator('#passageScroll #choices').count()==0
            checks.append('one persistent action shelf outside narrative scroll')
            for key in ['gate','harbor','alley','save']:call(key)
            assert page.evaluate('gamebook.app.run.current')=='5'
            for before,selector in [(base,'#book'),(shelf,'#actionShelf'),(control,'#stepBtn')]:
                after=rect(selector)
                for v in ['x','y','width','height']: assert abs(before[v]-after[v])<1,(selector,v,before,after)
            checks.append('combat does not move book, shelf or next-step button')
            boxes=page.locator('#choices .choice-button').evaluate_all('(els)=>els.map(e=>({slot:e.dataset.slot,box:e.getBoundingClientRect().toJSON()}))')
            assert len(boxes)==8 and all(0<=b['box']['top']<b['box']['bottom']<=1080 for b in boxes)
            assert page.locator('#choices [data-slot="use:smoke"]').is_disabled()
            checks.append('all eight fixed combat slots visible including unavailable slots')
            call('combat:precision')
            assert page.locator('[data-slot="combat:precision"]').is_disabled()
            after=page.locator('#choices .choice-button').evaluate_all('(els)=>els.map(e=>({slot:e.dataset.slot,box:e.getBoundingClientRect().toJSON()}))')
            assert [b['slot'] for b in boxes]==[b['slot'] for b in after]
            assert all(abs(a['box']['top']-b['box']['top'])<1 for a,b in zip(boxes,after))
            checks.append('depleted focus does not compact or reorder buttons')
            # Keyboard 3 means the fixed third slot (guard), not legal-array index 2.
            page.locator('#storyText').click();page.keyboard.press('3');page.wait_for_function('!gamebook.app.busy')
            assert page.evaluate('gamebook.app.run.last_decision.choice')=='combat:guard'
            checks.append('keyboard shortcuts follow physical slots')
            folio=page.locator('#rightFolio').inner_text();previous_plan=page.evaluate('gamebook.turner.lastPlan')
            call('combat:guard')
            assert page.locator('#rightFolio').inner_text()==folio and page.evaluate('gamebook.turner.lastPlan')==previous_plan
            checks.append('combat and consumables keep the same folio and do not flip')
            page.screenshot(path=str(args.out/'combat-fixed.png'))
            # Stress the right-hand log, not the story or game state.
            page.evaluate('''()=>{for(let i=0;i<100;i++){const li=document.createElement('li');li.textContent='Layout stress entry '+i;document.getElementById('events').append(li);}}''')
            assert abs(rect('#book')['y']-base['y'])<1 and abs(rect('#actionShelf')['y']-shelf['y'])<1
            checks.append('long sidebar log cannot expand viewport grid')
            for width,height in [(1366,768),(1280,720),(1920,1080)]:
                page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(60)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert page.locator('#choices button').evaluate_all('(els)=>els.every(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;})')
                assert rect('#stepBtn')['y']+rect('#stepBtn')['height']<=height
            checks.append('desktop 720p, 768p and 1080p keep controls in viewport')
            page.evaluate("gamebook.newRun({book:'demo',seed:1,choiceOrder:'original'})")
            page.evaluate('gamebook.turner.reduced=false')
            if not page.evaluate('gamebook.audio.enabled'):page.locator('#soundBtn').click()
            page.locator('#stepBtn').click()
            page.wait_for_function("document.body.dataset.phase==='annotating'")
            assert page.locator('.ink-percent').count()==3 and page.locator('.ink-circle').count()==1
            assert 'Random' in page.locator('#inkLegend').inner_text()
            assert page.evaluate('gamebook.observe().ready') is False
            assert page.locator('#stepBtn').is_disabled()
            assert page.locator('.ink-percent').first.get_attribute('aria-hidden')=='true'
            page.wait_for_timeout(400)
            page.screenshot(path=str(args.out/'ink-random.png'))
            page.wait_for_function('!gamebook.app.busy',timeout=15000)
            assert page.evaluate('gamebook.app.run.current')=='7'
            plan=page.evaluate('gamebook.turner.lastPlan')
            assert plan['direction']==1 and plan['sheets']>1
            checks.append('real Random percentages, animated circle, busy guard, multi-sheet forward flip')
            assert page.evaluate('gamebook.audio.events.some(e=>e.kind==="slash")')
            assert page.evaluate('gamebook.audio.events.filter(e=>e.kind==="flutter").length')>=2
            checks.append('slash and staggered flutter use real Web Audio events')
            call('c0'); assert page.evaluate('gamebook.app.run.current')=='9'
            # page 9 -> 8 is a real backwards passage in the bundled story.
            page.locator('[data-choice="c0"]').click()
            page.wait_for_function("document.body.dataset.phase==='annotating'")
            assert page.locator('.ink-percent').count()==0 and '確率情報なし' in page.locator('#inkLegend').inner_text()
            page.wait_for_function('!gamebook.app.busy',timeout=15000)
            assert page.evaluate('gamebook.turner.lastPlan.direction')==-1
            assert page.evaluate('gamebook.app.run.current')=='8'
            checks.append('manual choice draws circle without invented scores; real backwards turn')
            page.evaluate("gamebook.newRun({book:'demo',seed:17,choiceOrder:'balanced'})")
            o=page.evaluate('gamebook.observe()')
            keys=[c['key'] for c in o['choices']]
            assert 'rng' not in o and 'sections' not in o and len(o['choices'])==3
            report={'run_id':o['run_id'],'revision':o['revision'],'choice':keys[1], 'probabilities':{k:(.8 if i==1 else .1) for i,k in enumerate(keys)}}
            page.evaluate('(r)=>{void gamebook.chooseWithProbabilities(r)}',report)
            page.wait_for_function("document.body.dataset.phase==='annotating'")
            assert '自己申告' in page.locator('#inkLegend').inner_text()
            assert page.locator('[data-choice="'+keys[1]+'"] .ink-numeric').inner_text()=='80%'
            assert page.locator('.ink-circle').count()==1
            page.wait_for_function('!gamebook.app.busy',timeout=15000)
            revision=page.evaluate('gamebook.app.run.revision')
            stale=page.evaluate('(r)=>gamebook.chooseWithProbabilities(r).then(()=>false,()=>true)',report)
            assert stale and page.evaluate('gamebook.app.run.revision')==revision
            checks.append('browser-agent self report maps by action IDs and rejects stale revision')
            page.evaluate('gamebook.turner.reduced=true')
            page.evaluate("gamebook.newRun({book:'ashbell',choiceOrder:'balanced'})")
            for key in ['gate','harbor','alley','save']:call(key)
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(80)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert page.locator('#choices button').count()==8
            page.screenshot(path=str(args.out/'mobile.png'),full_page=True)
            checks.append('390px mobile width and semantic action slots')
            page.set_viewport_size({'width':1920,'height':1080})
            page.locator('#settingsBtn').click();page.locator('#bookSelect').select_option('aon_kai')
            assert page.locator('#kaiSetup').is_visible()
            page.locator('#applySettings').click();page.wait_for_function('!gamebook.app.busy')
            assert page.evaluate('gamebook.app.run.mode')=='lonewolf_kai'
            assert page.locator('#choices button').count()==2
            assert page.locator('#hpValue').inner_text()=='25 / 25'
            page.locator('#bagBtn').click();assert 'Sword' in page.locator('#journalContents').inner_text();page.keyboard.press('Escape')
            call('kai:combat')
            assert page.locator('#battleEvents li').count()>=2
            assert page.evaluate('gamebook.app.run.pagination.total')==12
            checks.append('Kai setup, fixed CRT/evasion slots, Action Chart and real CRT round')
            page.evaluate("gamebook.newRun({book:'ashbell'})")
            assert page.locator('label[for=hpMeter]').inner_text()=='体力'
            assert page.locator('#focusMeter').is_visible()
            assert page.locator('#bagBtn').inner_text()=='荷物・装備'
            checks.append('switching Kai back to RPG restores labels and controls')
            assert not errors,errors
            report={'checks':checks,'browser_errors':errors,'renderer':page.evaluate('gamebook.turner.engine'),'transport':'actual assets + local HTTP API bridge' if args.memory else 'HTTP','live_model_called':False}
            (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2))
            browser.close()
    finally:server.shutdown();server.server_close();fixture_dir.cleanup()

if __name__=='__main__':main()

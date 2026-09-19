"""Browser smoke test for the Project Aon / Kai compatibility UI."""
from __future__ import annotations
import argparse, json, shutil, sys, tempfile, threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from web_app import GamebookService, LocalServer
from browser_check import memory_page


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--browser',default='/usr/bin/chromium'); ap.add_argument('--memory',action='store_true')
    args=ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); shutil.copy(ROOT/'tests/kai_fixture.xml', root/'01fftd.xml')
        service=GamebookService(root); server=LocalServer(0,service)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        checks=[]; errors=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1500,'height':980});page.on('pageerror',lambda e:errors.append(str(e)))
                if not args.memory:
                    page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle')
                    page.wait_for_function('window.gamebook?.app.ready',timeout=10000)
                else: memory_page(page,server)
                page.evaluate("gamebook.newRun({book:'aon_kai',seed:17,kaiConfig:{combat_skill:15,endurance:25,gold:10,disciplines:['Hunting','Healing','Weaponskill','Mindblast','Sixth Sense'],weaponskill_weapon:'Sword',weapons:['Sword'],active_weapon:'Sword',backpack:{'Meal':2,'Healing Potion':1},special_items:[]}})")
                page.wait_for_function("gamebook.app.run?.mode === 'lonewolf_kai'")
                assert page.locator('#modeTitle').inner_text() == 'KAI RULES · PROJECT AON'; checks.append('mode label')
                assert '25 / 25' in page.locator('#hpValue').inner_text(); checks.append('ENDURANCE display')
                assert page.locator('#battlePanel').is_visible(); checks.append('combat panel')
                assert page.locator('[data-choice="kai:combat"]').count()==1; checks.append('CRT action')
                page.locator('#bagBtn').click(); assert page.locator('#journalDialog').is_visible(); checks.append('Action Chart dialog'); page.locator('#journalDialog .dialog-close button').click()
                page.locator('[data-choice="kai:combat"]').click(); page.wait_for_function('!gamebook.app.busy',timeout=7000)
                assert page.locator('#battleEvents li').count() >= 2; checks.append('random number + CRT result')
                assert page.locator('#tideValue').inner_text() != '—'; checks.append('combat ratio display')
                page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(100)
                assert page.evaluate('document.body.scrollWidth <= innerWidth + 1'); checks.append('mobile no horizontal overflow')
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        print(json.dumps({'checks':checks,'errors':errors,'mode':'memory' if args.memory else 'http'},ensure_ascii=False,indent=2))
        if errors: raise SystemExit(1)

if __name__=='__main__':main()

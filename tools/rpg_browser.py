"""Real Japanese UI + real server API smoke test; never invokes paid models."""
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--memory', action='store_true')
    p.add_argument('--browser')
    p.add_argument('--out', type=Path, default=ROOT/'artifacts/ashbell')
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    server = LocalServer(0); threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            opts = {'headless': True}
            if args.browser: opts['executable_path'] = args.browser
            browser = pw.chromium.launch(**opts)
            page = browser.new_page(viewport={'width':1920, 'height':1080})
            errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
            if args.memory: memory_page(page, server)
            else:
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.wait_for_function('window.gamebook?.app.ready')
            assert page.evaluate('gamebook.app.run.book') == 'ashbell'
            assert page.locator('#hpValue').inner_text() == '30 / 30'
            assert page.locator('#leftPage').get_attribute('lang') == 'ja'
            assert page.locator('#characterPanel').is_visible()
            page.screenshot(path=str(args.out/'opening.png'))
            page.locator('#bagBtn').click()
            assert page.locator('.journal-card').count() == 6
            page.screenshot(path=str(args.out/'inventory.png'))
            page.locator('[data-journal-tab=rules]').click()
            assert '精密攻撃' in page.locator('#journalContents').inner_text()
            page.keyboard.press('Escape')
            page.locator('#soundBtn').click()
            assert page.evaluate('gamebook.audio.ctx.state') == 'running'
            page.evaluate('gamebook.turner.reduced=true')
            for key in ['gate','harbor','alley','save']:
                page.evaluate('(key)=>gamebook.step(key)', key)
            assert page.evaluate('gamebook.app.run.current') == '5'
            page.evaluate("() => {for(let i=0;i<8;i++) document.querySelector('[data-choice=\"combat:attack\"]').click();}")
            page.wait_for_function('!gamebook.app.busy')
            assert page.evaluate('gamebook.app.run.combat_state.round') == 2
            page.evaluate("gamebook.step('combat:attack')")
            assert page.locator('#hpValue').inner_text() == '21 / 30'
            assert page.locator('#enemyHP').inner_text() == '2 / 13'
            assert page.evaluate('gamebook.app.run.path') == ['1','2','3','4','5']
            page.wait_for_timeout(400)  # Let HP-bar transitions settle for the still.
            page.screenshot(path=str(args.out/'combat.png'))
            assert 'd6' in page.locator('#battleEvents').inner_text()
            page.evaluate("gamebook.step('use:tonic')")
            assert page.locator('#hpValue').inner_text() == '30 / 30'
            assert page.evaluate('gamebook.app.run.character.inventory.find(i=>i.id==="tonic").count') == 1
            page.evaluate("gamebook.step('combat:precision')")
            assert page.evaluate('gamebook.app.run.current') == '6'
            assert page.locator('#battlePanel').is_hidden()
            kinds = page.evaluate('gamebook.audio.events.map(e=>e.kind)')
            assert {'clash','heal','victory'}.issubset(kinds)
            page.locator('#cluesBtn').click()
            assert '整備屋の合図' in page.locator('#journalContents').inner_text()
            assert '灯' in page.locator('#journalContents').inner_text()
            page.keyboard.press('Escape')
            page.evaluate("gamebook.step('return')")
            page.evaluate("gamebook.step('market')")
            page.evaluate("gamebook.step('blade')")
            assert page.evaluate('gamebook.app.run.character.power') == 2
            page.locator('#bagBtn').click()
            page.locator('.journal-card').filter(has_text='月銀の細剣').locator('button').click()
            page.wait_for_function('!gamebook.app.busy')
            assert page.evaluate('gamebook.app.run.character.power') == 4
            assert page.evaluate('gamebook.app.run.character.gold') == 3
            page.screenshot(path=str(args.out/'equipment.png'))
            # Keyboard shortcuts do not fire while a journal dialog is active.
            page.locator('#bagBtn').click()
            revision = page.evaluate('gamebook.app.run.revision')
            page.keyboard.press('1')
            assert page.evaluate('gamebook.app.run.revision') == revision
            page.keyboard.press('Escape')
            page.set_viewport_size({'width':390,'height':844})
            page.wait_for_timeout(120)
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert page.locator('#hpValue').is_visible()
            page.screenshot(path=str(args.out/'mobile.png'), full_page=True)
            result = page.evaluate('''async()=>await (await fetch('/api/runs/'+gamebook.app.run.run_id+'/export')).json()''')
            assert result['mode'] == 'story_rpg' and result['trace'][-1]['after']['character']['power'] == 4
            assert not errors, errors
            report = {'checks': ['Japanese opening','HP/focus display','inventory dialog','rules dialog','audio unlock',
                       'battle entry','duplicate-click rejection','actual damage/dice','same-page combat rounds','potion consumption',
                       'victory/loot','combat/heal/victory sounds','known-clue journal','equipment changes stats','dialog keyboard guard',
                       'mobile width/HP','v2 export'], 'renderer': page.evaluate('gamebook.turner.engine'),
                      'mode': 'memory assets + real HTTP API' if args.memory else 'HTTP', 'errors': errors,
                      'paid_provider_called': False}
            (args.out/'browser-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False, indent=2))
            browser.close()
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__': main()

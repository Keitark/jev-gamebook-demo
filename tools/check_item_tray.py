"""Reader integration fixture with real RPG actions, not a model/demo playback.

Uses the repository's CSS, ReaderUI and atmosphere layer. The fixture implements
app.js's button/render contract and connects clicks to the actual RPGEngine.
This is deliberately not described as a full web_app.py HTTP/browser test.
Run: python tools/check_item_tray.py --browser /usr/bin/chromium
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from story_ja import make_story
from types import SimpleNamespace
from reader_presentation import ordered

HTML = '''<!doctype html><html lang="ja"><body class="rpg-mode">
<div id="book"><div id="spread" class="spread">
<section id="leftPage" class="paper verso"><div class="running-head">THE DECISION LIBRARY</div><h1>灰鐘の港と、名前のない朝</h1><p>道具別枠の実装テスト。戦闘結果はRPGエンジンが計算。</p><span id="leftFolio"></span></section>
<section id="rightPage" class="paper recto">
<div class="running-head">行動と道具の分離</div><div class="passage-header"><h2 id="fixtureTitle"></h2></div>
<div id="passageScroll" class="passage-scroll"><article class="story-text" id="storyText"></article></div>
<section id="actionShelf" class="action-shelf"><div class="action-shelf-top"><span id="actionCount"></span><span id="inkLegend" hidden></span></div><div class="choice-heading"><span></span><em>次の一手を、どうする。</em><span></span></div><div id="choices" class="choices"></div><div id="actionExplanation" class="action-explanation"></div></section>
<footer class="page-footer"><span id="rightFolio"></span></footer></section><div id="turnStage"></div></div></div>
<div hidden><select id="orderMode"><option>original</option><option>balanced</option></select><span id="positionNote"></span><span id="orderNote"></span><span id="paginationLabel"></span><progress id="pageProgress"></progress></div>
<aside class="right-rail" style="display:none"><span id="readingPhase"></span></aside>
</body></html>'''
FIXTURE_CSS='''#book{width:min(880px,calc(100vw - 40px));height:calc(100vh - 70px);margin:20px auto}
#spread{height:100%;display:flex}#rightPage,#leftPage{width:50%;min-width:0}#fixtureTitle{font-size:20px}
@media(max-width:760px){#leftPage{display:none}#rightPage{width:100%}}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default='/usr/bin/chromium')
    ap.add_argument('--out', type=Path, default=ROOT/'artifacts/item-tray')
    args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    engine = make_story().new_engine(17)
    checks=[]; errors=[]
    def check(label, value):
        if not value: raise AssertionError(label)
        checks.append(label)
    def snapshot():
        r = SimpleNamespace(engine=engine, book_id='ashbell', choice_order='original', seed=17, current=engine.current, revision=engine.steps)
        ob=engine.observation()
        return {'run_id':'local-rule-test','book':'ashbell','mode':'story_rpg','status':engine.status,
                'current':engine.current,'revision':engine.steps,'character':ob['character'],
                'combat_state':ob['combat'],'section':{'choices':ordered(r,ob['actions']), 'text':ob['section']['text'], 'title':ob['section']['title']}}
    def apply(key):
        engine.apply(key)
        return snapshot()
    for key in ['gate','harbor','alley','save']:
        apply(key)
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
        page=b.new_page(viewport={'width':1280,'height':720})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.expose_function('__realAction',apply)
        page.set_content(HTML)
        for name in ['style.css','rpg.css','reader.css','reader-atmosphere.css']:
            page.add_style_tag(content=(ROOT/'web'/name).read_text())
        page.add_style_tag(content=FIXTURE_CSS)
        for name in ['reader-ui.js','sound.js','page-turn.js','reader-atmosphere.js']:
            page.add_script_tag(content=(ROOT/'web'/name).read_text())
        page.evaluate('''() => {
          window.gamebook={app:{ready:true,busy:false,run:null}};
          window.paintFixture = run => {
            ReaderUI.clearInk();gamebook.app.run=run;
            document.getElementById('fixtureTitle').textContent=run.section.title;
            document.getElementById('storyText').replaceChildren(...run.section.text.map(text=>{const p=document.createElement('p');p.textContent=text;return p}));
            const container=document.getElementById('choices');container.replaceChildren();
            for (const action of run.section.choices) {
              const button=document.createElement('button');button.className='choice-button';button.dataset.choice=action.key;
              for(const cls of ['choice-roman','choice-label','choice-target']){const s=document.createElement('span');s.className=cls;button.append(s)}
              button.querySelector('.choice-label').textContent=action.text;
              button.addEventListener('click',async()=>{
                if(gamebook.app.busy)return;
                gamebook.app.busy=true;
                try{const result=await __realAction(action.key);gamebook.app.busy=false;paintFixture(result)}
                catch(e){gamebook.app.busy=false;window.actionError=String(e)}
              });container.append(button);
            }
            ReaderUI.decorate(run);
            document.querySelectorAll('.choice-button').forEach(button=>button.disabled=gamebook.app.busy||run.status!=='live'||button.classList.contains('unavailable'));
          };
          document.addEventListener('keydown', e=>{
            if(/^[1-9]$/.test(e.key)){const button=document.getElementById('choices').children[Number(e.key)-1];if(button&&!button.disabled&&button.dataset.choice){e.preventDefault();button.click()}}
          });
          ReaderUI.init();
        }''')
        page.evaluate('paintFixture',snapshot())
        ids=lambda sel:page.eval_on_selector_all(sel,'ns=>ns.map(n=>n.dataset.choice||n.dataset.slot)')
        check('four combat actions separate from consumables',ids('#choices .choice-button')==['combat:attack','combat:precision','combat:guard','combat:flee'])
        check('four fixed item positions',ids('#itemChoices .choice-button')==['use:tonic','use:bandage','use:saltbomb','use:smoke'])
        check('unavailable potion initially stays in its slot',page.locator('[data-slot="use:tonic"]').is_disabled())
        check('full action list still contains all legal item IDs',{a['key'] for a in snapshot()['section']['choices']}=={a['key'] for a in engine.actions()})
        # Geometry is tested against the real shelf styles at four viewport sizes.
        def boxes():
            return page.eval_on_selector_all('#actionShelf .choice-button','ns=>ns.map(n=>({key:n.dataset.choice||n.dataset.slot,x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y,width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height}))')
        for width,height in [(1280,720),(1366,768),(1920,1080),(390,844)]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(60)
            measurements=page.evaluate('''() => [...document.querySelectorAll('#actionShelf .choice-button')].map(n=>{
              const b=n.getBoundingClientRect(),p=n.parentElement.getBoundingClientRect();
              return {key:n.dataset.choice||n.dataset.slot,visible:b.top>=p.top-1&&b.bottom<=p.bottom+1&&b.left>=p.left-1&&b.right<=p.right+1,onscreen:b.bottom<=innerHeight&&b.right<=innerWidth};
            })''')
            if not all(m['visible'] and m['onscreen'] for m in measurements):
                print(width,height,measurements);page.screenshot(path=str(args.out/'layout-failure.png'));print(boxes())
            check(f'{width}x{height}: all combat and item slots fit without scrolling',all(m['visible'] and m['onscreen'] for m in measurements))
        page.set_viewport_size({'width':1280,'height':720});page.wait_for_timeout(60)
        before=boxes()
        for _ in range(2):
            page.locator('[data-choice="combat:attack"]').click();page.wait_for_function('!gamebook.app.busy')
        check('real combat damage applied',engine.hero.hp==21)
        after=boxes()
        check('slot positions unchanged when potion becomes available',all(abs(a['y']-z['y'])<1 and abs(a['x']-z['x'])<1 for a,z in zip(before,after)))
        old_steps=engine.steps
        page.locator('[data-choice="use:tonic"]').click();page.wait_for_function('!gamebook.app.busy')
        check('item click consumes one actual potion',engine.hero.inventory['tonic']==1)
        check('item click heals and spends one turn',engine.hero.hp==30 and engine.steps==old_steps+1)
        check('full-health potion is disabled in same slot',page.locator('[data-slot="use:tonic"]').is_disabled())
        check('remaining quantity shown', '残り 1' in page.locator('[data-slot="use:tonic"] .choice-target').inner_text())
        check('items have no conflicting number shortcuts',page.locator('#itemChoices [aria-keyshortcuts]').count()==0)
        check('main keyboard shortcuts stay 1-4',page.eval_on_selector_all('#choices .choice-button','ns=>ns.map(n=>n.getAttribute("aria-keyshortcuts"))')==['1','2','3','4'])
        # Finish via numeric shortcut; not via a replacement/simulated combat policy.
        old_steps=engine.steps;page.keyboard.press('2');page.wait_for_function('!gamebook.app.busy')
        check('numeric precision attack still reaches the engine',engine.steps==old_steps+1 and engine.battle is None)
        check('victory does not leave stale combat item buttons',page.locator('#itemChoices [data-slot="use:smoke"]').count()==0)
        for key in ['return','market']:
            page.evaluate('paintFixture',apply(key))
        check('purchasing a blade remains a narrative choice',page.locator('#choices [data-choice="blade"]').count()==1)
        page.evaluate('paintFixture',apply('blade'))
        equipment=next(a['key'] for a in engine.actions() if a['key'].startswith('equip:'))
        check('equipment action is in item tray',page.locator(f'#itemChoices [data-choice="{equipment}"]').count()==1)
        page.locator(f'#itemChoices [data-choice="{equipment}"]').click();page.wait_for_function('!gamebook.app.busy')
        check('actual weapon equipped',engine.hero.equipment['weapon']==equipment.split(':')[1])
        check('replaced equipment button removed',page.locator(f'[data-choice="{equipment}"]').count()==0)
        page.evaluate('ReaderUI.decorate(gamebook.app.run)')
        check('decoration is idempotent without losing legal items',set(ids('#actionShelf [data-choice]'))=={a['key'] for a in engine.actions()})
        # Explicit test scores, never represented as live Jev inference.
        choice=next(a['key'] for a in engine.actions() if a['key'].startswith('use:'))
        scores={a['key']:1/len(engine.actions()) for a in engine.actions()}
        page.evaluate('''report => {window.annotationDone=false;window.effectSounds=[];ReaderUI.annotate(report,{audio:{play(k){effectSounds.push(k)}},reduced:false}).then(()=>annotationDone=true)}''',{'source':'browser','choice':choice,'probabilities':scores})
        page.wait_for_function('annotationDone',timeout=7000)
        check('item receives its checkmark and probability',page.locator(f'#itemChoices [data-choice="{choice}"] .ink-check').count()==1 and page.locator(f'#itemChoices [data-choice="{choice}"] .ink-numeric').count()==1)
        check('selection slash still plays',page.evaluate('effectSounds.includes("slash")'))
        page.evaluate('ReaderUI.clearInk()')
        page.evaluate('''() => {const r={...gamebook.app.run,status:'ending',section:{...gamebook.app.run.section,choices:[]}};paintFixture(r)}''')
        check('ending clears and hides item tray',page.locator('#itemArea').is_hidden() and page.locator('#itemChoices [data-choice]').count()==0)
        page.evaluate('''() => paintFixture({mode:'navigation_only',book:'demo',current:'1',revision:0,status:'live',section:{title:'Navigation',text:['No character'],choices:[{key:'c0',text:'Continue',target:'2'}]}})''')
        check('navigation-only mode has no item tray',page.locator('#itemArea').is_hidden())
        # Kai mode uses its own potion/weapon IDs without changing their meaning.
        page.evaluate('''() => paintFixture({mode:'lonewolf_kai',book:'aon_kai',current:'2',revision:3,status:'live',character:{backpack:[{name:'Healing Potion',count:1}]},section:{title:'Kai',text:['Action Chart'],choices:[{key:'c0',text:'Continue',target:'3'},{key:'kai:potion',text:'Drink Healing Potion',kind:'item',target:'2'},{key:'kai:equip:Axe',text:'Use Axe',kind:'equipment',target:'2'}]}})''')
        check('Kai potion and weapon separated',ids('#choices [data-choice]')==['c0'] and ids('#itemChoices [data-choice]')==['kai:potion','kai:equip:Axe'])
        check('Kai quantity shown', '残り 1' in page.locator('[data-choice="kai:potion"]').inner_text())
        check('no duplicate DOM action IDs',page.evaluate('''() => {const ids=[...document.querySelectorAll('[id^="action-"]')].map(n=>n.id);return new Set(ids).size===ids.length}'''))
        check('no JavaScript page errors',not errors)
        b.close()
    result={'scope':'real CSS/ReaderUI + RPGEngine integration fixture; not full HTTP app or paid model test','checks':checks,'errors':errors}
    (args.out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

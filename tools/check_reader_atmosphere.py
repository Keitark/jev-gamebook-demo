"""Isolated presentation checks. No paid model calls or fabricated API results.

Uses the repository HTML/CSS, actual PageTurn/PaperAudio base classes and the
new presentation layer. ReaderUI's orchestration is a small explicit test
fixture: this is NOT a full app/backend integration suite.
"""
from __future__ import annotations
import argparse, base64, json, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''() => {
  const $=id=>document.getElementById(id);
  document.body.classList.add('rpg-mode','in-combat');
  const labels={bookTitle:'灰鐘の港と、名前のない朝',passageTitle:'針金の歯',sectionNumber:'5',sectionStat:'05',movesStat:'4',visitedStat:'5',runStatus:'戦闘中',
    bookCaption:'灰鐘奇譚 · 活字とインクの校正',runningTitle:'灰鐘の港と、名前のない朝',bookTitle:'灰鐘の港と、名前のない朝',
    ledgerLabel:'READER’S PROOF · 演出確認',ledgerNote:'確率の数値は演出テスト用です。Jevの推論結果ではありません。',
    sourceNote:'校正画面 · 番号と紙の動きを確認する',choiceHeading:'次の一手を、どうする。',paginationLabel:'仮想頁 10–11 / 122 · §5',leftFolio:'— 10 —',rightFolio:'— 11 —',
    enemyName:'針金の猟犬',enemyHP:'13 / 13',enemyStats:'回避 7 · 装甲 0 · 技量 3',enemyIntent:'大振り',enemyHint:'次の一撃は重い。先にあなたが行動する。',combatRound:'ROUND 01',
    hpValue:'30 / 30',focusValue:'3 / 4',goldValue:'9',tideValue:'2 / 16',modeTitle:'PRESENTATION PROOF',modeDetail:'選択とページめくりの演出確認。',
    actionCount:'6 ACTIONS',backendNote:'演出テスト · モデルは呼びません',orderNote:'戦闘の配置は固定',actionExplanation:'操作ボタンの位置は変えず、赤インクだけを重ねる。'};
  for(const [id,value] of Object.entries(labels))if($(id))$(id).textContent=value;
  for(const id of ['battlePanel','characterPanel','journalButtons'])$(id).hidden=false;
  $('combatBanner').hidden=false;$('combatBanner').textContent='⚔　針金の猟犬　／　第 1 手';
  $('storyText').replaceChildren();
  for(const t of ['犬の歯は一本の針金を何度も折り返したものだった。街の誰かが、歯でなく道具を作ろうとした名残にも見える。','少女が低く叫ぶ。「跳ぶ前に腰が落ちる。そのときだけは、ちゃんと見て！」大振りに備えるか、溜めている間に攻めるか。判断するのはあなただ。']){const p=document.createElement('p');p.textContent=t;$('storyText').append(p);}
  const actions=[['combat:attack','攻撃','通常攻撃'],['combat:precision','精密攻撃','集中2 · 必中'],['combat:guard','防御','集中を回復'],['use:tonic','回復薬','体力を回復'],['use:bandage','清め布','体力を回復'],['use:saltbomb','鳴塩を投げる','固定ダメージ'],['use:smoke','煙玉','所持していない'],['combat:flee','撤退','成功判定あり']];
  $('actionShelf').dataset.combat='true';$('choices').replaceChildren();
  actions.forEach(([key,title,hint],i)=>{
    const b=document.createElement('button');b.className='choice-button';b.dataset.choice=key;
    b.dataset.actionId=key;b.id='action-'+encodeURIComponent(key);
    for(const [cls,value] of [['choice-roman',String(i+1)+'.'],['choice-label',title],['choice-target',hint]]){const span=document.createElement('span');span.className=cls;span.textContent=value;b.append(span);}
    if(i===6){b.classList.add('unavailable');b.disabled=true;delete b.dataset.choice;}
    $('choices').append(b);
  });
  // Only the orchestration seam is mocked; the new code runs unchanged.
  window.ReaderUI={init(){},phase(name){document.body.dataset.phase=name;},clearInk(){document.querySelectorAll('.ink-percent,.ink-numeric').forEach(n=>n.remove());document.querySelectorAll('.ink-picked').forEach(n=>n.classList.remove('ink-picked'));$('inkLegend').hidden=true;}};
  window.PROOF_DECISION={source:'browser',probability_source:'browser_self_report',choice:'combat:guard',latency_ms:0,
    probabilities:{'combat:attack':.08,'combat:precision':.105,'combat:guard':.78,'use:tonic':.005,'use:bandage':.005,'use:saltbomb':.02,'combat:flee':.005}};
}'''

def load(page):
    html=(ROOT/'web/index.html').read_text()
    html=re.sub(r'<link[^>]*>','',html)
    html=re.sub(r'<script[^>]*>.*?</script>','',html,flags=re.S)
    image=base64.b64encode((ROOT/'web/engraving.svg').read_bytes()).decode()
    page.set_content(html.replace('/static/engraving.svg','data:image/svg+xml;base64,'+image))
    for file in ['style.css','rpg.css','reader.css','reader-atmosphere.css']:
        page.add_style_tag(content=(ROOT/'web'/file).read_text())
    page.evaluate(FIXTURE)
    for file in ['sound.js','page-turn.js','reader-atmosphere.js']:
        page.add_script_tag(content=(ROOT/'web'/file).read_text())
    page.evaluate('''() => {
      window.gamebook={app:{ready:true,busy:false,run:{revision:4,current:'5',status:'live'}}, audio:new PaperAudio({enabled:false})};
      gamebook.turner=new PageTurn({book:document.getElementById('book'),spread:document.getElementById('spread'),stage:document.getElementById('turnStage'),audio:gamebook.audio,onRenderer:l=>document.getElementById('rendererStatus').textContent=l});
      gamebook.turner.engine='css3d';ReaderUI.init();ReaderUI.phase('ready');
    }''')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--out',type=Path,default=ROOT/'artifacts/atmosphere-components')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    result={'scope':'isolated presentation; orchestration fixture, no model/backend integration','checks':[],'errors':[]}
    def check(name, ok=True):
        assert ok,name;result['checks'].append(name)
    with sync_playwright() as pw:
        opts={'headless':True}
        if args.browser:opts['executable_path']=args.browser
        browser=pw.chromium.launch(**opts)
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.on('pageerror',lambda e:result['errors'].append(str(e)))
        load(page)
        check('installed in correct script order',page.evaluate("ReaderAtmosphere.version==='1.0'"))
        bounds=page.locator('[data-choice="combat:guard"]').bounding_box()
        page.evaluate("ReaderUI.phase('thinking')")
        page.wait_for_timeout(20)
        page.evaluate("window.proofDone=false; ReaderUI.annotate(PROOF_DECISION,{audio:gamebook.audio}).then(()=>{window.proofDone=true;ReaderUI.phase('ready');})")
        page.wait_for_function("document.querySelector('.ink-check')")
        page.wait_for_timeout(350)
        page.screenshot(path=str(args.out/'checkmark-screen.png'))
        page.locator('#actionShelf').screenshot(path=str(args.out/'checkmark-closeup.png'))
        check('checkmark replaces circle',page.locator('.ink-check').count()==1 and page.locator('.ink-circle').count()==0)
        check('seven reported percentages only',page.locator('.gothic-numerals').count()==7)
        check('original numeral paths have fill',page.evaluate("getComputedStyle(document.querySelector('.gothic-numerals path')).fill!=='none'"))
        check('overlay does not move button',page.locator('[data-choice="combat:guard"]').bounding_box()==bounds)
        check('mark ignores pointer hit testing',page.evaluate("getComputedStyle(document.querySelector('.ink-check')).pointerEvents==='none'"))
        page.wait_for_function('window.proofDone',timeout=3500)
        page.evaluate('ReaderUI.phase("ready")')
        timing=page.evaluate('ReaderAtmosphere.timing()');result['annotation']=timing['last']
        check('annotation is deliberate, not a 20s stall',1400 < timing['last']['presentation_ms'] < 3500)
        page.evaluate("ReaderUI.clearInk(); ReaderUI.phase('thinking')")
        page.evaluate("ReaderUI.annotate({source:'manual',choice:'combat:attack',probabilities:{}},{reduced:true})")
        check('plain clicks never invent scores',page.locator('.gothic-numerals').count()==0)
        check('reduced mode still has readable selected mark',page.locator('.ink-check').count()==1)
        page.evaluate('ReaderUI.phase("ready")')
        blocked=page.evaluate('''async () => {
          const a=new PaperAudio({enabled:true});let calls=0;
          a.ctx={state:'suspended',resume(){calls++;return new Promise(()=>{});}};
          const start=performance.now();
          const result=await Promise.race([a.unlock().then(()=>true),new Promise(resolve=>setTimeout(()=>resolve(false),120))]);
          return {returned:result,ms:performance.now()-start,calls};
        }''')
        result['blocked_audio']=blocked
        check('unresolved audio resume cannot block a step',blocked['returned'] and blocked['ms']<100)
        rejected=page.evaluate('''async () => {const a=new PaperAudio({enabled:true});a.ctx={state:'suspended',resume(){return Promise.reject(new Error('test denial'));}};return await a.unlock();}''')
        check('audio denial safely falls back to silence',rejected is False)
        page.evaluate('ReaderUI.clearInk()')
        for width,height in [(1280,720),(1366,768),(1920,1080)]:
            page.set_viewport_size({'width':width,'height':height})
            y=page.locator('#stepBtn').bounding_box()
            page.evaluate("document.getElementById('battleEvents').innerHTML='<li>log</li>'.repeat(50);document.getElementById('battleLogPanel').hidden=false")
            after=page.locator('#stepBtn').bounding_box()
            check(f'combat/long log fixed at {width}x{height}',y==after and after['y']+after['height']<=height)
        page.set_viewport_size({'width':1920,'height':1080})
        plans=page.evaluate('''() => [0,1,2,9,24,59].map(n=>GamebookPaper.travelPlan({spread:0,right:3},{spread:n,right:3+2*n,total:122}))''')
        check('no invented sheet for same folio',plans[0]['sheets']==0)
        check('distant jump shows >9 leaves with bounded duration',plans[-1]['sheets']==28 and plans[-1]['duration']<=4800)
        page.evaluate('''() => {
          window.turnDone=false;ReaderUI.phase('turning');gamebook.app.busy=true;
          gamebook.turner.turn(()=>{}, {from:{spread:1,right:5},to:{spread:25,right:53,total:122}}).then(()=>{window.turnDone=true;gamebook.app.busy=false;ReaderUI.phase('ready');});
        }''')
        page.wait_for_timeout(950)
        page.screenshot(path=str(args.out/'riffle.png'))
        pool=page.evaluate('gamebook.turner.lastRenderStats')
        check('distant CSS riffle uses a bounded leaf pool',pool['virtual_leaves']==24 and pool['active_renderers']<=6)
        page.wait_for_function('turnDone',timeout=7000)
        result['riffle']=page.evaluate('gamebook.turner.lastRenderStats')
        check('riffle cleans all temporary layers',page.locator('.pooled-leaf,.riffle-counter').count()==0)
        page.evaluate('''async () => {await gamebook.turner.turn(()=>{}, {from:{spread:3,right:9},to:{spread:1,right:5,total:122}});}''')
        check('backward turn preserves direction',page.evaluate('gamebook.turner.lastPlan.direction')==-1)
        # Reduced motion must never pay canvas capture setup cost.
        page.evaluate('''async () => {const original=GamebookPaper.capturePaper;GamebookPaper.capturePaper=()=>{throw new Error('should not capture');};gamebook.turner.reduced=true;try{await gamebook.turner.turn(()=>{}, {from:{spread:0},to:{spread:3}});}finally{GamebookPaper.capturePaper=original;gamebook.turner.reduced=false;}}''')
        check('reduced motion bypasses canvas snapshotting')
        failure=page.evaluate("""async () => {let committed=0;const capture=GamebookPaper.capturePaper;GamebookPaper.capturePaper=()=>{throw new Error('synthetic texture failure');};try{await gamebook.turner.turn(()=>committed++,{from:{spread:0},to:{spread:1}});return {committed,busy:gamebook.turner.busy};}finally{GamebookPaper.capturePaper=capture;}}""")
        check('texture failure commits destination and releases lock',failure['committed']==1 and not failure['busy'])
        stalled=page.evaluate("""async () => {const raf=window.requestAnimationFrame;window.requestAnimationFrame=()=>0;const started=performance.now();try{await gamebook.turner.turn(()=>{}, {from:{spread:0},to:{spread:1}});return {ms:performance.now()-started,busy:gamebook.turner.busy};}finally{window.requestAnimationFrame=raf;}}""")
        result['stalled_raf']=stalled
        check('stalled animation frame cannot hold lock for 20s',not stalled['busy'] and stalled['ms']<5000)
        page.set_viewport_size({'width':390,'height':844})
        check('mobile has no horizontal overflow',page.evaluate('document.body.scrollWidth<=innerWidth+1'))
        page.screenshot(path=str(args.out/'mobile.png'),full_page=True)
        check('no browser errors',not result['errors'])
        browser.close()
    (args.out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()

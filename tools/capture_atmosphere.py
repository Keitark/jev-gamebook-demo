"""Capture the presentation component, not gameplay or a real AI decision.

Uses the same explicit orchestration fixture as check_reader_atmosphere.py.
The probability values are TEST DATA. No API/model/backend request is sent.
"""
from __future__ import annotations
import argparse, base64, json, subprocess, shutil
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
from check_reader_atmosphere import load


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--browser')
    p.add_argument('--out',type=Path,default=Path('artifacts/atmosphere-film'))
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    frames=a.out/'frames'; frames.mkdir(exist_ok=True)
    if not shutil.which('ffmpeg'): raise SystemExit('ffmpeg is required')
    errors=[];fps,seconds=24,14
    with sync_playwright() as pw:
        opts={'headless':True}
        if a.browser:opts['executable_path']=a.browser
        browser=pw.chromium.launch(**opts)
        page=browser.new_page(viewport={'width':1600,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.clock.install(time=datetime.now(timezone.utc))
        load(page)
        page.evaluate('''() => {
          document.getElementById('bookCaption').textContent='演出確認用 · 確率は固定テスト値 · Jev推論ではありません';
          document.querySelector('#connection span').textContent='PRESENTATION TEST';
          document.getElementById('soundBtn').onclick=()=>{gamebook.audio.enabled=true;gamebook.audio.unlock();document.querySelector('#soundBtn span').textContent='音 ON';};
          window.proofTurn=(from,to)=>{
            ReaderUI.clearInk();ReaderUI.phase('turning');gamebook.app.busy=true;
            gamebook.turner.turn(()=>{
              document.getElementById('leftFolio').textContent='— '+(to.right-1)+' —';
              document.getElementById('rightFolio').textContent='— '+to.right+' —';
              document.getElementById('paginationLabel').textContent='演出サンプル · 仮想頁 '+(to.right-1)+'–'+to.right+' / 122';
            },{from,to}).then(()=>{gamebook.app.busy=false;ReaderUI.phase('ready');});
          };
        }''')
        page.locator('#soundBtn').click()
        page.wait_for_function("gamebook.audio.ctx?.state==='running'")
        now=page.evaluate('Date.now()')
        page.clock.pause_at(datetime.fromtimestamp((now+100)/1000,timezone.utc))
        start=page.evaluate('performance.now()')
        for n in range(fps*seconds):
            if n==24:
                page.evaluate("()=>{ReaderUI.phase('thinking');gamebook.app.busy=true;ReaderUI.annotate(PROOF_DECISION,{audio:gamebook.audio}).then(()=>{gamebook.app.busy=false;ReaderUI.phase('ready');});}")
            if n==102:
                page.evaluate("()=>{proofTurn({spread:1,right:5},{spread:25,right:53,total:122});}")
            if n==252:
                page.evaluate("()=>{proofTurn({spread:25,right:53},{spread:17,right:37,total:122});}")
            page.clock.run_for(round((n+1)*1000/fps)-round(n*1000/fps))
            page.screenshot(path=str(frames/f'{n:04d}.jpg'),type='jpeg',quality=91)
            if n%96==0:print('Captured',n,'/',fps*seconds,flush=True)
        events=page.evaluate('(start)=>gamebook.audio.events.filter(e=>e.time>=start).map(e=>({...e,time:e.time-start}))',start)
        wav=page.evaluate('''async ({events,seconds})=>{
          const blob=await PaperAudio.renderWav(events,seconds);
          return await new Promise(resolve=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.readAsDataURL(blob);});
        }''',{'events':events,'seconds':seconds})
        (a.out/'effects.wav').write_bytes(base64.b64decode(wav))
        report={'scope':'isolated presentation fixture; not full gameplay or real Jev inference','test_probabilities':True,'renderer':'css3d','seconds':seconds,'fps':fps,'resolution':[1600,900],'errors':errors,'audio_events':events}
        (a.out/'capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
        if errors:raise RuntimeError(errors)
    subprocess.run(['ffmpeg','-y','-loglevel','warning','-framerate',str(fps),'-i',str(frames/'%04d.jpg'),'-i',str(a.out/'effects.wav'),'-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',str(seconds),'-movflags','+faststart',str(a.out/'checkmark-riffle.mp4')],check=True)
    print(a.out/'checkmark-riffle.mp4',flush=True)
if __name__=='__main__':main()

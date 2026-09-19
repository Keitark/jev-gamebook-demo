"""Capture the actual browser UI at 24 fps and encode its procedural effects.

Requires Playwright (Chromium) and ffmpeg on PATH. No real model calls are made.
The first choice uses the seeded random baseline, followed by manual choices.
This is a UI demonstration, not evidence that Jev solved the book.

python tools/capture_demo.py --out artifacts/preview
Add --memory only in restricted rendering environments (see browser_check.py).
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from web_app import LocalServer
from browser_check import memory_page


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--memory',action='store_true')
    parser.add_argument('--browser')
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/preview')
    args=parser.parse_args()
    if not shutil.which('ffmpeg'): raise SystemExit('Install ffmpeg and put it on PATH.')
    output=args.out.resolve(); frames=output/'frames-jpeg'; frames.mkdir(parents=True,exist_ok=True)
    fps=24; seconds=15; total=fps*seconds
    server=LocalServer(0);threading.Thread(target=server.serve_forever,daemon=True).start()
    errors=[]
    try:
        with sync_playwright() as p:
            options={'headless':True}
            if args.browser: options['executable_path']=args.browser
            browser=p.chromium.launch(**options)
            page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            # Install before the page creates any timers. Frame stepping makes the
            # paper geometry and its sound events reproducible, not prerecorded.
            page.clock.install(time=datetime.now(timezone.utc))
            if args.memory: memory_page(page,server)
            else:
                page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='domcontentloaded')
                page.wait_for_function('window.gamebook?.app.ready')
                page.evaluate('document.fonts.ready')
            page.evaluate("gamebook.newRun({book:'demo',seed:1})")
            page.locator('#backend').select_option('random')
            if not page.evaluate('gamebook.audio.enabled'): page.locator('#soundBtn').click()
            assert page.evaluate('gamebook.audio.ctx.state')=='running'
            when=(page.evaluate('Date.now()')+100)/1000
            page.clock.pause_at(datetime.fromtimestamp(when,timezone.utc))
            start=page.evaluate('performance.now()')
            actions={36:'random',108:'manual',180:'manual',252:'manual'}
            last_frame=None; last_signature=None
            for frame in range(total):
                if frame in actions:
                    if actions[frame]=='random': page.evaluate("document.getElementById('stepBtn').click()")
                    else: page.evaluate("document.querySelector('[data-choice=c0]').click()")
                # Every screenshot is the actual app; never draw a replacement UI.
                page.clock.run_for(round((frame+1)*1000/fps)-round(frame*1000/fps))
                signature=page.evaluate('JSON.stringify([gamebook.app.run.revision,gamebook.app.busy,gamebook.app.auto,document.getElementById("events").textContent])')
                destination=frames/f'{frame:04d}.jpg'
                destination.unlink(missing_ok=True)
                if last_frame and signature==last_signature and not page.evaluate('gamebook.app.busy'):
                    os.link(last_frame,destination)
                else:
                    page.screenshot(path=str(destination),type='jpeg',quality=95)
                last_frame=destination; last_signature=signature
                if frame==20: page.screenshot(path=str(output/'screen.png'))
                if frame==55: page.screenshot(path=str(output/'page-turn.png'))
                if frame==91: page.screenshot(path=str(output/'random-decision.png'))
                if frame%72==0: print(f'Captured {frame}/{total}',flush=True)
            assert page.evaluate('gamebook.app.run.status')=='success'
            assert page.evaluate('gamebook.app.run.path')==['1','7','9','8','12']
            events=page.evaluate('(start)=>gamebook.audio.events.filter(e=>e.time>=start).map(e=>({...e,time:e.time-start}))',start)
            wav=page.evaluate('''async ({events,seconds}) => {
              const blob=await PaperAudio.renderWav(events,seconds);
              return await new Promise(resolve=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.readAsDataURL(blob);});
            }''',{'events':events,'seconds':seconds})
            (output/'effects.wav').write_bytes(base64.b64decode(wav))
            manifest={'fps':fps,'seconds':seconds,'resolution':[1920,1080],
                      'renderer':page.evaluate('gamebook.turner.engine'),
                      'capture':'real UI frame-stepped in Chromium; same Web Audio synth at recorded event times',
                      'navigation':'API bridge' if args.memory else 'HTTP',
                      'path':page.evaluate('gamebook.app.run.path'),
                      'controllers':['random','manual','manual','manual'],
                      'live_jev_tested':False,'browser_errors':errors,'audio_events':events}
            (output/'capture.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
            browser.close()
        assert not errors, errors
    finally:
        server.shutdown();server.server_close()
    subprocess.run(['ffmpeg','-y','-loglevel','warning','-framerate',str(fps),'-i',str(frames/'%04d.jpg'),
                    '-i',str(output/'effects.wav'),'-c:v','libx264','-preset','medium','-crf','17',
                    '-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',str(seconds),
                    '-movflags','+faststart',str(output/'gamebook-with-sound.mp4')],check=True)
    print(output/'gamebook-with-sound.mp4')

if __name__=='__main__': main()

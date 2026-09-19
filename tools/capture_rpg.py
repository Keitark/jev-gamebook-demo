"""Record the actual Japanese RPG UI and its procedural audio (manual inputs).

Requires playwright + ffmpeg. --memory uses the same real local API bridge as
rpg_browser.py; it is not a substitute UI or a fabricated Jev result.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from web_app import LocalServer
from browser_check import memory_page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--memory', action='store_true')
    parser.add_argument('--browser')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/ashbell-film')
    args = parser.parse_args()
    if not shutil.which('ffmpeg'):
        raise SystemExit('Install ffmpeg and put it on PATH.')
    output = args.out.resolve(); frames = output/'frames'; frames.mkdir(parents=True, exist_ok=True)
    fps, seconds = 24, 16
    server = LocalServer(0); threading.Thread(target=server.serve_forever, daemon=True).start()
    errors = []
    try:
        with sync_playwright() as pw:
            options = {'headless': True}
            if args.browser: options['executable_path'] = args.browser
            browser = pw.chromium.launch(**options)
            page = browser.new_page(viewport={'width':1920, 'height':1080}, device_scale_factor=1)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.clock.install(time=datetime.now(timezone.utc))
            if args.memory: memory_page(page, server)
            else:
                page.goto(f'http://127.0.0.1:{server.server_port}', wait_until='domcontentloaded')
                page.wait_for_function('window.gamebook?.app.ready')
                page.evaluate('document.fonts.ready')
            page.evaluate("gamebook.newRun({book:'ashbell',seed:17})")
            page.evaluate('gamebook.turner.reduced=true')
            for key in ['gate', 'harbor', 'alley']:
                page.evaluate('(key)=>gamebook.step(key)', key)
            page.evaluate('gamebook.turner.reduced=false')
            if not page.evaluate('gamebook.audio.enabled'): page.locator('#soundBtn').click()
            assert page.evaluate('gamebook.audio.ctx.state') == 'running'
            when = (page.evaluate('Date.now()') + 100) / 1000
            page.clock.pause_at(datetime.fromtimestamp(when, timezone.utc))
            start = page.evaluate('performance.now()')
            actions = {36:'save', 108:'combat:attack', 168:'combat:attack', 228:'use:tonic', 288:'combat:precision'}
            previous = None; previous_signature = None; last_action = -999
            for frame in range(fps*seconds):
                if frame in actions:
                    page.evaluate('key=>document.querySelector(`[data-choice="${key}"]`).click()', actions[frame])
                    last_action = frame
                page.clock.run_for(round((frame+1)*1000/fps) - round(frame*1000/fps))
                signature = page.evaluate('JSON.stringify([gamebook.app.run.revision,gamebook.app.busy,document.getElementById("events").textContent])')
                destination = frames/f'{frame:04d}.jpg'; destination.unlink(missing_ok=True)
                # Do not freeze settling HP bars or page geometry after state changes.
                if previous and signature == previous_signature and frame-last_action > 42 and not page.evaluate('gamebook.app.busy'):
                    os.link(previous, destination)
                else:
                    page.screenshot(path=str(destination), type='jpeg', quality=95)
                previous, previous_signature = destination, signature
                if frame == 55: page.screenshot(path=str(output/'page-turn.png'))
                if frame == 204: page.screenshot(path=str(output/'combat.png'))
                if frame == 365: page.screenshot(path=str(output/'victory.png'))
                if frame % 96 == 0: print(f'Captured {frame}/{fps*seconds}', flush=True)
            assert page.evaluate('gamebook.app.run.current') == '6'
            assert page.evaluate('gamebook.app.run.character.hp') == 30
            events = page.evaluate('(start)=>gamebook.audio.events.filter(e=>e.time>=start).map(e=>({...e,time:e.time-start}))', start)
            assert {'clash','heal','victory'}.issubset({e['kind'] for e in events})
            wav = page.evaluate('''async ({events,seconds}) => {
              const blob=await PaperAudio.renderWav(events,seconds);
              return await new Promise(resolve=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.readAsDataURL(blob);});
            }''', {'events':events, 'seconds':seconds})
            (output/'effects.wav').write_bytes(base64.b64decode(wav))
            report = {'fps':fps, 'seconds':seconds, 'resolution':[1920,1080],
                      'renderer':page.evaluate('gamebook.turner.engine'), 'capture':'actual UI + recorded Web Audio event synthesis',
                      'navigation':'API bridge' if args.memory else 'HTTP', 'seed':17,
                      'path':page.evaluate('gamebook.app.run.path'), 'actions':list(actions.values()),
                      'controllers':['manual'], 'live_jev_tested':False, 'browser_errors':errors, 'audio_events':events}
            (output/'capture.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown(); server.server_close()
    subprocess.run(['ffmpeg','-y','-loglevel','warning','-framerate',str(fps),'-i',str(frames/'%04d.jpg'),
                    '-i',str(output/'effects.wav'),'-c:v','libx264','-preset','medium','-crf','17',
                    '-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',str(seconds),
                    '-movflags','+faststart',str(output/'ashbell-combat.mp4')], check=True)
    print(output/'ashbell-combat.mp4')


if __name__ == '__main__': main()

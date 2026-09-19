# Reader polish verification — 2026-09-19

Scope: stable browser-use controls, virtual pagination, forward/backward multi-leaf turns, handwritten probability overlays, animated decision circles, sharp selection audio, and measurable option ordering. Game rules were not changed.

## Executed checks

- `python -m pytest -q`: **111 passed** (86 existing + 25 presentation tests). Tests verify stable/sparse virtual folios, independently ordered choices, unchanged game RNG, unchanged outcomes for an identical action sequence, strict external probability validation, atomic rejected reports, manual clicks without fabricated probabilities, and consistent provider/observation action IDs and ordering.
- `python tools/reader_browser.py --memory --browser /usr/bin/chromium`: **15 groups passed, no JavaScript page errors**. Actual UI and local HTTP server; includes Japanese RPG and Kai compatibility mode switching, real combat, fixed disabled slots, keyboard slot mapping, long sidebar stress, 1920×1080 / 1366×768 / 1280×720 desktop viewports, 390px mobile, explicit browser-agent reports and stale revisions, forward multi-leaf and backward turns, actual Random percentages, and Web Audio events.
- `python tools/rpg_browser.py --memory --browser /usr/bin/chromium`: **17 existing Japanese RPG groups passed, no JavaScript page errors**.
- `python tools/smoke_browser.py --memory --browser /usr/bin/chromium`: **13 existing navigation groups passed, no JavaScript page errors**. The paper-event assertion accepts either the old single-page `paper` effect or the new multi-leaf `flutter` effect.
- `node --check` for every `web/*.js`: passed.

Desktop regression tests compare the book, action shelf, and next-step button bounds before and after entering combat (less than 1 CSS pixel change). They also check that all eight combat slots and the next-step button remain inside 720p, 768p, and 1080p viewports. Focus depletion disables the precision-attack slot in place. Long text retains its own scrolling region; this is not a test that an external agent actually reads every paragraph.

## Reproducible video

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tools/reader_browser.py
python tools/capture_reader.py
```

The capture requires ffmpeg on PATH. Add `--browser PATH` to use an installed Chromium. The `--memory` flag is only for the explicit managed-browser fallback described below.

The generated film is **27 seconds, 1920×1080, 24 fps, H.264/AAC**. It captures the actual application, not an artist's mockup. One seeded Random decision chooses the market; the rest are explicit manual test inputs. The route includes forward and backward page travel, attack, healing, and victory. Audio is rendered with the application's own Web Audio synthesizer at the recorded event times. The WAV has nonzero samples. Percentages shown for Random are its actual uniform distribution, not fabricated Jev scores.

The three-mode browser test also submits clearly identified synthetic **browser self-report** scores to verify their mapping and rejection rules. Those are test inputs, not measurements of a live model.

## Limits

The managed Chromium environment blocks localhost page navigation and does not provide WebGL2. Its policy was not modified. The in-memory harness installs the actual HTML/CSS/JavaScript and bridges only `/api/...` calls to the actual local HTTP server. It does not fabricate state transitions, dice, inventory or provider replies for the interactive scenarios.

Screenshots/video verify **CSS 3D**, not GPU rendering. Both the Three.js mesh and CSS strip implementations support the new multi-leaf travel interface, but live Three.js GPU rendering and CDN/font loading were not verified here. External fonts are omitted in the harness; no font binaries are included in the repository or artifacts.

No real paid TypeSafe/OpenRouter call was made. Provider-order tests use a stub response. We do not claim that the external browser agent's first-option preference has been cured, that its intelligence improved, or that a win-rate difference was measured. The new logs and controlled ordering make that experiment possible.

Kai mode retains its previously documented core-rules limitations; this UI update does not make it a fully automated implementation of every Project Aon prose instruction. API keys remain server-side. The server is for local single-user use, not public hosting.

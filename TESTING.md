# Verification notes — Japanese RPG edition

Verified during implementation, 2026-09-19.

## Current results

- `python -m pytest -q`: **78 passed** (28 existing tests + 50 RPG tests). Covers real local HTTP requests, Host/Origin/token and secret-file protection, revisions, provider response validation, book validation, inventory/equipment, costs, dice, recovery, enemy intents, fleeing, atomic rejected actions, loot-once, repeated hazards, exclusive story choices, endings and JSON export.
- `python tools/rpg_browser.py --memory --browser /usr/bin/chromium`: **17 groups passed, no JavaScript page errors**. Real Japanese passages, HP/focus, bag/clue/rule dialogs, manual combat, duplicate-click rejection, damage and actual dice, same-page rounds, consumed healing potion, victory, equipment changing stats, combat/recovery/victory audio, keyboard guard, mobile layout, and v2 export.
- `python tools/smoke_browser.py --memory --browser /usr/bin/chromium`: **13 legacy groups passed, no JavaScript page errors**. Original English navigation, page turns, sound, mute, auto-stop, settings, endings and long text remain functional.
- `python tools/rpg_scenarios.py`: **100/100 seeds (0–99) reached the names-returned ending with a supplied known route**. Seed 17: HP26, tide10, 44 actions. Uses real actions, purchases, equipment, combat and prerequisites. This checks solvability across dice sequences, **not Jev intelligence or win rate**.
- `python run_rpg.py --backend random --runs 3 --seed 17`: three real runs exported; endings `departed`, `too_late`, `fallen`. This is a CLI smoke test, not a meaningful model comparison.
- `python tools/capture_rpg.py --memory --browser /usr/bin/chromium`: **1920×1080, 24fps, 16 seconds, H.264/AAC**. Real manual inputs save the girl, enter combat, attack twice, consume a healing potion, and finish with precision attack. Seed17: HP30→21→30, enemy HP13→2→0. Effects use the app's own Web Audio synth at recorded event times. No model results are substituted.

The original story has **60 sections, 8 enemy types/encounters, 17 item types, 9 clues and 7 endings**. The graph check includes global HP/tide terminal edges. Not every playthrough visits all encounters.

## Environment limitations

The managed Chromium environment blocks local URL navigation and does not provide WebGL2. Its policy was not modified. The harness loads the **actual HTML/CSS/JavaScript** in memory and forwards only `/api/...` requests to the **actual local HTTP server**. No transition, dice result, inventory state or model response is fabricated by this bridge.

Preview images/video verify the **curved CSS 3D renderer**, not Three.js GPU rendering. External font links are omitted in this harness; Japanese uses an installed serif fallback. No font binaries are included in the repository or archives.

Normal full-HTTP browser navigation, Google Fonts/CDN loading, live TypeSafe/OpenRouter inference and a fresh Project Aon download were **not verified here**. On an ordinary desktop, omit `--memory` for full-HTTP browser checks.

Provider tests use stubs to verify that only currently available actions and observed state are sent. No real API key or paid provider is used in testing. The screenshot/video controls are explicitly manual, not Jev output.

## Scope

Combat and mutable inventory are implemented for **the original Japanese story**, not for Project Aon's Lone Wolf rules. The original English demonstration and imported Project Aon books continue to use navigation-only mode. JSON export is an audit record, not a restore/save-game feature. Sessions remain in server memory. This local single-user server is not intended for public hosting.

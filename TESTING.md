# Verification notes

Verified during implementation, 2026-09-19.

## Completed

- `python -m pytest -q`: **28 passed**. Includes real local HTTP requests, JSON validation, Host/Origin/token checks, secret-file exclusion, missing-key behaviour, deterministic random runs, stale/duplicate step rejection, terminal conditions, exports, parser handling of dead-end text and CLI step limits.
- `python tools/smoke_browser.py --memory --browser /usr/bin/chromium`: **13 groups of browser checks passed; no JavaScript page errors**. Covers real manual/random transitions, rapid repeated clicks, curved page animation, Web Audio unlock, paper/victory effects, mute, settings, auto-stop, endings, long passage scrolling and a 390-pixel mobile viewport without horizontal overflow.
- `python tools/capture_demo.py --memory --browser /usr/bin/chromium`: real UI captured at **1920×1080, 24 fps, 15 seconds**, encoded to H.264/AAC. The effects track uses the app's own Web Audio synthesizer at its recorded event times. The WAV contains non-zero audio. The recorded path is `1 → 7 → 9 → 8 → 12`.

The first recorded choice is from **seeded Random**, and the following choices are **manual test inputs**. The UI labels those sources explicitly. This is not a Jev success-rate test.

## Environment limitations

The managed Chromium environment blocked navigation to local URLs and did not provide WebGL2. Its policy was not modified. The rendering harness installs the **actual HTML/CSS/JavaScript** into an in-memory page, and forwards only `/api/...` requests to the **actual local HTTP server**. No story transition or model result is fabricated by this bridge. External font links are omitted in this harness, so screenshots use the local serif fallback.

The preview therefore verifies the **curved CSS 3D renderer**, not Three.js GPU rendering. The normal full-HTTP browser path, Google Fonts/CDN loading, live TypeSafe/OpenRouter requests and a fresh Project Aon download were **not verified in this environment**. A normal desktop can run `python tools/smoke_browser.py` without `--memory` to check the full-HTTP path.

Provider tests use stub responses to check adapters and failure handling. No real API key is present in the repository or test fixtures. No real paid provider was called during this verification.

## Scope

The existing navigation engine does not execute combat, mutate inventory, enforce choice prerequisites or roll the random-number table. Reaching the configured end section must not be reported as completing the original gamebook under its full rules.

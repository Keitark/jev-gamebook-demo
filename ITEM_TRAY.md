# Item tray — separate story actions from inventory operations

Implemented 2026-09-19. This is an item-separation update, not the pending page-layout, fast-riffle, illustration or sequential-percentage update.

## Visible behavior

- Narrative choices remain in the main action area.
- Japanese combat has four fixed main positions: attack, precision, guard, flee. Number keys 1–4 refer only to these positions.
- Consumables and equipment changes move into a labeled `道具を使う / 装備` tray below the main choices, inside the existing fixed-height shelf. Only the inside of each group scrolls.
- Combat consumables keep four fixed positions: tonic, bandage, saltbomb, smoke. Unavailable items stay disabled, with remaining quantities and a reason. They do not squeeze the other buttons into new positions.
- Item buttons retain the original action IDs and click listeners. They receive their actual supplied probability and checkmark; plain clicks still have no invented probability.
- The full legal action list is still passed to the controller. Splitting the UI does not hide item actions from Jev or browser agents.
- Equipment changes use the same tray. Scene-specific purchases and item-dependent story branches remain narrative choices.
- Kai potion and weapon-switch actions are separated too. Navigation-only books have no item tray.
- Ending a run or switching books clears the old buttons. Redecorating the same snapshot does not discard its item actions.

The visual audit order is partitioned to match the main area followed by the item tray. Game rules, current folio mapping, API secrets and actual effects are unchanged.

## Update

Stop the server, run `git pull --ff-only`, restart with `python web_app.py --open`, and hard-refresh the browser. Existing `.env` is unchanged. No manual patch is needed.

## Verification

`python -m pytest -q tests/test_item_tray_order.py`: **8 passed**.

`python tools/check_item_tray.py --browser /usr/bin/chromium`: **31 checks passed, no JavaScript page errors**. The reader integration fixture loads the real CSS, ReaderUI and atmosphere layer and connects button clicks to the actual Japanese RPGEngine. It verified combat damage, potion consumption/healing/turn cost, equipment changes, stable slots, keyboard positions, annotations, navigation/Kai grouping, and cleanup. Slot visibility was checked at 1280×720, 1366×768, 1920×1080 and 390×844.

The fixture implements the existing app's render/button contract; this is **not** a claim of a complete web_app.py HTTP/browser test or live Jev inference. Full-app regression, GPU rendering and paid API tests were not run for this update. No new demonstration video was produced.

JavaScript syntax and Python compilation also passed. The uploaded production source blob hashes match the tested local bytes.

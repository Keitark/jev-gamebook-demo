# Project Aon / Kai Rules compatibility mode

`Flight from the Dark（Project Aon・Kai互換戦闘）` adds a server-side Action Chart and the generic **Kai-series** combat/equipment rules to a Project Aon XML book.

This is intentionally separate from the tactical rules used by the original Japanese adventure. It exists so the same reader can compare a classic gamebook whose combats are mostly table-driven with a gamebook that exposes many tactical decisions to Jev.

## Implemented core rules

- New-character COMBAT SKILL: 10–19.
- New-character ENDURANCE: 20–29; it can never be healed above its starting maximum.
- Exactly five Kai Disciplines in the starting configuration.
- Standard Kai Combat Ratio: `Lone Wolf COMBAT SKILL - enemy COMBAT SKILL`.
- Standard 13-column Kai Combat Results Table, driven by a random number 0–9.
- `K` results are instant kills.
- Weaponskill: +2 COMBAT SKILL while using the selected Weaponskill weapon.
- Mindblast: +2 COMBAT SKILL unless the passage states that the opponent is immune.
- No weapon carried: −4 COMBAT SKILL.
- Healing: +1 ENDURANCE when entering a numbered section that has no combat, capped at starting ENDURANCE.
- Weapon limit: 2.
- Backpack capacity: 8 items.
- Gold Crowns range: 0–50.
- Healing Potion: one dose restores up to 4 ENDURANCE in the compatibility engine.
- Evasion uses a normal combat round, discards damage dealt to the enemy, applies only Lone Wolf's loss, then follows the detected evasion branch.
- Multiple `<combat>` elements in a section are resolved sequentially.

The Action Chart starter can be configured in the browser settings. The default is a legal sample character with COMBAT SKILL 15, ENDURANCE 25, five Disciplines, a Sword, two Meals, one Healing Potion and 10 Gold Crowns.

## What is parsed from Project Aon XML

The existing Project Aon reader now preserves structured combat data from `<combat>`:

- enemy name
- enemy `combatskill`
- enemy `endurance`

The compatibility engine blocks the normal passage choices until marked combats in that section are resolved. It also looks for an explicit evasion/escape/flee branch in the visible choice text before exposing the Evasion action.

## Deliberate limits

Project Aon XML does not turn every instruction in the prose into authoritative machine-readable state. This version therefore **does not guess** all of the following:

- item pickups and discards described only in prose
- payments and Gold Crown changes described only in prose
- Meal instructions / wasteland exceptions for Hunting
- arbitrary Special Item effects
- every temporary COMBAT SKILL modifier
- every conditional branch based on Disciplines or possessions
- all book-specific errata and later-series Magnakai / Grand Master mechanics

One conservative exception is an explicit phrase of the form `deduct N point(s) from your COMBAT SKILL`, which is recognized as a temporary combat modifier for that passage. Mindblast immunity is detected only when the passage explicitly says `immune to Mindblast`.

So `lonewolf_kai` should be read as **Kai core-rules compatibility**, not “fully automated Lone Wolf book 1”. The ordinary `aon` mode remains available if you only want the original Project Aon text and links without rule automation.

## Official rule references

- Project Aon Readers' Handbook — Kai rules: https://www.projectaon.org/en/ReadersHandbook/Kai
- Kai Disciplines: https://www.projectaon.org/en/ReadersHandbook/KaiDisciplines
- Kai Equipment: https://www.projectaon.org/en/ReadersHandbook/KaiEquipment
- Kai Combat: https://www.projectaon.org/en/ReadersHandbook/KaiCombat
- Example Combat Results Table: https://www.projectaon.org/en/ReadersHandbook/ExampleCombatResultsTable
- Example Combat: https://www.projectaon.org/en/ReadersHandbook/ExampleCombat

Project Aon's own handbook notes that generic rules can differ from the exact rules printed in a particular book. Always follow the book text where it overrides the generic rules.

"""Kai-series compatibility rules for Project Aon gamebooks.

This module implements the *generic Kai rules* used by early Lone Wolf books:
COMBAT SKILL / ENDURANCE, the standard Combat Results Table, Weaponskill,
Mindblast, Healing, weapon/backpack limits, Gold Crowns and evasion.

Project Aon's XML marks combat opponents and passage links, but not every
book-specific item pickup, temporary modifier or conditional rule in a
machine-readable way. Those remain visible in the prose and are deliberately
not guessed here. This engine therefore provides a strict core-rules layer,
not a claim of fully automating every printed instruction.
"""
from __future__ import annotations

import copy
import json
import random
import re
from dataclasses import dataclass, field

from gamebook_jev import ProjectAonBook


class KaiRuleError(ValueError):
    pass


# Standard Kai Combat Results Table. Each cell is (enemy ENDURANCE loss,
# Lone Wolf ENDURANCE loss). None represents an instant kill (K).
# Columns group Combat Ratios exactly as the printed table does.
_RATIO_GROUPS = [
    (-10_000, -11), (-10, -9), (-8, -7), (-6, -5), (-4, -3),
    (-2, -1), (0, 0), (1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 10_000),
]
_ROWS = {
    1: [(0,None),(0,None),(0,8),(0,6),(1,6),(2,5),(3,5),(4,5),(5,4),(6,4),(7,4),(8,3),(9,3)],
    2: [(0,None),(0,8),(0,7),(1,6),(2,5),(3,5),(4,4),(5,4),(6,4),(7,4),(8,3),(9,3),(10,2)],
    3: [(0,8),(0,7),(1,6),(2,5),(3,5),(4,4),(5,4),(6,3),(7,3),(8,2),(9,2),(10,2),(11,2)],
    4: [(0,8),(1,7),(2,6),(3,5),(4,4),(5,4),(6,3),(7,3),(8,2),(9,2),(10,2),(11,2),(12,2)],
    5: [(1,7),(2,6),(3,5),(4,4),(5,4),(6,3),(7,2),(8,2),(9,2),(10,2),(11,1),(12,1),(14,1)],
    6: [(2,6),(3,6),(4,5),(5,4),(6,3),(7,2),(8,2),(9,2),(10,2),(11,1),(12,1),(14,1),(16,1)],
    7: [(3,5),(4,5),(5,4),(6,3),(7,2),(8,2),(9,1),(10,1),(11,1),(12,0),(14,0),(16,0),(18,0)],
    8: [(4,4),(5,4),(6,3),(7,2),(8,1),(9,1),(10,0),(11,0),(12,0),(14,0),(16,0),(18,0),(None,0)],
    9: [(5,3),(6,3),(7,2),(8,0),(9,0),(10,0),(11,0),(12,0),(14,0),(16,0),(18,0),(None,0),(None,0)],
    0: [(6,0),(7,0),(8,0),(9,0),(10,0),(11,0),(12,0),(14,0),(16,0),(18,0),(None,0),(None,0),(None,0)],
}

KAI_DISCIPLINES = [
    'Camouflage', 'Hunting', 'Sixth Sense', 'Tracking', 'Healing',
    'Weaponskill', 'Mindshield', 'Mindblast', 'Animal Kinship', 'Mind Over Matter',
]
WEAPONS = ['Dagger', 'Spear', 'Mace', 'Short Sword', 'Warhammer', 'Sword', 'Axe', 'Quarterstaff', 'Broadsword']


def combat_result(combat_ratio: int, random_number: int) -> tuple[int | None, int | None]:
    if random_number not in _ROWS:
        raise KaiRuleError('Random Number must be 0–9.')
    for i, (low, high) in enumerate(_RATIO_GROUPS):
        if low <= combat_ratio <= high:
            return _ROWS[random_number][i]
    raise AssertionError(combat_ratio)


@dataclass
class KaiCharacter:
    base_combat_skill: int
    endurance: int
    max_endurance: int
    disciplines: set[str] = field(default_factory=set)
    weaponskill_weapon: str = 'Sword'
    weapons: list[str] = field(default_factory=list)
    active_weapon: str | None = None
    backpack: dict[str, int] = field(default_factory=dict)
    special_items: list[str] = field(default_factory=list)
    gold: int = 10


DEFAULT_CONFIG = {
    'combat_skill': 15,
    'endurance': 25,
    'disciplines': ['Hunting', 'Healing', 'Weaponskill', 'Mindblast', 'Sixth Sense'],
    'weaponskill_weapon': 'Sword',
    'weapons': ['Sword'],
    'active_weapon': 'Sword',
    'backpack': {'Meal': 2, 'Healing Potion': 1},
    'special_items': [],
    'gold': 10,
}


def normalize_config(config: dict | None, seed: int = 17) -> dict:
    """Validate a starting Action Chart.

    Passing ``None`` uses a deterministic, legal sample chart. Passing
    ``{"generate": True}`` generates official-range CS/ENDURANCE from 0–9
    random numbers while keeping the default disciplines/equipment.
    """
    data = copy.deepcopy(DEFAULT_CONFIG)
    if config:
        if not isinstance(config, dict):
            raise KaiRuleError('Kai setup must be an object.')
        if config.get('generate') is True:
            rng = random.Random(seed ^ 0x4B4149)
            data['combat_skill'] = 10 + rng.randrange(10)
            data['endurance'] = 20 + rng.randrange(10)
        for key in ('combat_skill','endurance','disciplines','weaponskill_weapon','weapons','active_weapon','backpack','special_items','gold'):
            if key in config:
                data[key] = copy.deepcopy(config[key])
    cs, end = data['combat_skill'], data['endurance']
    if type(cs) is not int or not 10 <= cs <= 19:
        raise KaiRuleError('COMBAT SKILL must be 10–19 for a new Kai character.')
    if type(end) is not int or not 20 <= end <= 29:
        raise KaiRuleError('ENDURANCE must be 20–29 for a new Kai character.')
    disciplines = data['disciplines']
    if not isinstance(disciplines, list) or len(disciplines) != 5 or len(set(disciplines)) != 5 or any(x not in KAI_DISCIPLINES for x in disciplines):
        raise KaiRuleError('Choose exactly five valid Kai Disciplines.')
    weapons = data['weapons']
    if not isinstance(weapons, list) or len(weapons) > 2 or len(set(weapons)) != len(weapons) or any(x not in WEAPONS for x in weapons):
        raise KaiRuleError('You may carry at most two valid Weapons.')
    if data['active_weapon'] is not None and data['active_weapon'] not in weapons:
        raise KaiRuleError('Active Weapon must be one of the carried Weapons.')
    if data['weaponskill_weapon'] not in WEAPONS:
        raise KaiRuleError('Weaponskill weapon is invalid.')
    bp = data['backpack']
    if not isinstance(bp, dict) or any(not isinstance(k,str) or type(v) is not int or v < 1 for k,v in bp.items()) or sum(bp.values()) > 8:
        raise KaiRuleError('Backpack may contain at most eight items.')
    if not isinstance(data['special_items'], list) or any(not isinstance(x,str) for x in data['special_items']):
        raise KaiRuleError('Special Items must be text labels.')
    if type(data['gold']) is not int or not 0 <= data['gold'] <= 50:
        raise KaiRuleError('Gold Crowns must be 0–50.')
    return data


class KaiEngine:
    """Core Kai rules layered over a parsed Project Aon book."""
    mode = 'lonewolf_kai'

    def __init__(self, book: ProjectAonBook, seed: int = 17, goal: str = '350', config: dict | None = None):
        self.book = book
        cfg = normalize_config(config, seed)
        self.hero = KaiCharacter(
            base_combat_skill=cfg['combat_skill'], endurance=cfg['endurance'], max_endurance=cfg['endurance'],
            disciplines=set(cfg['disciplines']), weaponskill_weapon=cfg['weaponskill_weapon'],
            weapons=cfg['weapons'][:], active_weapon=cfg['active_weapon'], backpack=cfg['backpack'].copy(),
            special_items=cfg['special_items'][:], gold=cfg['gold'],
        )
        self.rng = random.Random(seed ^ 0x4C4F4E45)
        self.goal = goal
        self.current = '1'
        self.steps = 0
        self.events: list[dict] = []
        self.battle: dict | None = None
        self.defeated: set[tuple[str,int]] = set()
        self.last_combat_section: str | None = None
        self.enter(self.current, initial=True)

    @property
    def section(self):
        return self.book.sections.get(self.current)

    @property
    def status(self) -> str:
        if self.hero.endurance <= 0:
            return 'deadend'
        if self.section is None:
            return 'missing_section'
        if self.section.deadend:
            return 'deadend'
        if self.current == self.goal:
            return 'success'
        if self.steps >= 200:
            return 'max_steps'
        if self.battle is None and not self.section.choices:
            return 'no_choice_terminal'
        return 'live'

    def event(self, kind: str, text: str, **detail):
        self.events.append({'kind': kind, 'text': text, **detail})

    def _combat_modifier_from_text(self) -> int:
        """Conservative parser for explicit, unconditional printed CS modifiers."""
        text = self.section.text if self.section else ''
        mod = 0
        for m in re.finditer(r'deduct\s+(\d+)\s+points?\s+from\s+your\s+COMBAT\s+SKILL', text, re.I):
            mod -= int(m.group(1))
        return mod

    def effective_combat_skill(self, enemy: dict | None = None) -> tuple[int, list[str]]:
        h = self.hero
        value = h.base_combat_skill
        notes = [f'Base {h.base_combat_skill}']
        if not h.weapons:
            value -= 4; notes.append('Unarmed −4')
        elif 'Weaponskill' in h.disciplines and h.active_weapon == h.weaponskill_weapon:
            value += 2; notes.append(f'Weaponskill ({h.weaponskill_weapon}) +2')
        immune = bool(enemy and enemy.get('mindblast_immune'))
        if 'Mindblast' in h.disciplines and not immune:
            value += 2; notes.append('Mindblast +2')
        section_mod = self._combat_modifier_from_text()
        if section_mod:
            value += section_mod; notes.append(f'Passage modifier {section_mod:+d}')
        return value, notes

    def _combat_specs(self):
        return self.section.combat_data if self.section else []

    def _evasion_target(self) -> str | None:
        if not self.section:
            return None
        keywords = re.compile(r'\b(evade|escape|flee|run away|withdraw|avoid (?:the )?combat)\b', re.I)
        for choice in self.section.choices:
            if keywords.search(choice.text):
                return choice.target
        return None

    def _begin_next_combat(self):
        for idx, spec in enumerate(self._combat_specs()):
            key = (self.current, idx)
            if key in self.defeated:
                continue
            enemy = {
                'name': spec.get('enemy') or 'Enemy',
                'combat_skill': int(spec['combat_skill']),
                'endurance': int(spec['endurance']),
                'max_endurance': int(spec['endurance']),
                'mindblast_immune': bool(re.search(r'immune to Mindblast', self.section.text, re.I)),
            }
            cs, notes = self.effective_combat_skill(enemy)
            self.battle = {
                'index': idx, 'enemy': enemy, 'round': 1, 'combat_skill': cs,
                'ratio': cs - enemy['combat_skill'], 'notes': notes,
                'evade_target': self._evasion_target(),
            }
            self.event('encounter', f"{enemy['name']}：COMBAT SKILL {enemy['combat_skill']} / ENDURANCE {enemy['endurance']}")
            return
        self.battle = None

    def enter(self, sid: str, initial: bool = False):
        if sid not in self.book.sections:
            raise KaiRuleError('Destination section is missing.')
        self.current = sid
        self.battle = None
        if not initial and 'Healing' in self.hero.disciplines and not self.book.sections[sid].combat_data and self.hero.endurance < self.hero.max_endurance:
            self.hero.endurance += 1
            self.event('heal', f'Healing：ENDURANCE +1 → {self.hero.endurance}')
        self._begin_next_combat()

    def actions(self) -> list[dict]:
        if self.status != 'live':
            return []
        if self.battle:
            result = [{'key':'kai:combat','text':'Combat Results Tableで1ラウンド戦う','target':self.current,'kind':'kai_combat'}]
            if self.battle.get('evade_target'):
                result.append({'key':'kai:evade','text':'このラウンドの敵へのダメージを捨てて回避する','target':self.battle['evade_target'],'kind':'kai_evade'})
            return result
        result = [{'key':c.key,'text':c.text,'target':c.target,'kind':'story'} for c in self.section.choices]
        if self.hero.endurance < self.hero.max_endurance and self.hero.backpack.get('Healing Potion', 0):
            result.append({'key':'kai:potion','text':'Healing Potionを飲む（ENDURANCE +4）','target':self.current,'kind':'item'})
        for weapon in self.hero.weapons:
            if weapon != self.hero.active_weapon:
                result.append({'key':'kai:equip:'+weapon,'text':weapon+'を使用する武器にする','target':self.current,'kind':'equipment'})
        return result

    def _resolve_round(self, evade: bool = False):
        b = self.battle
        if not b:
            raise KaiRuleError('No combat is active.')
        rn = self.rng.randrange(10)
        enemy_loss, hero_loss = combat_result(b['ratio'], rn)
        enemy = b['enemy']
        if hero_loss is None:
            self.hero.endurance = 0
            hero_text = 'K'
        else:
            self.hero.endurance = max(0, self.hero.endurance - hero_loss)
            hero_text = str(hero_loss)
        if not evade:
            if enemy_loss is None:
                enemy['endurance'] = 0
                enemy_text = 'K'
            else:
                enemy['endurance'] = max(0, enemy['endurance'] - enemy_loss)
                enemy_text = str(enemy_loss)
        else:
            enemy_text = 'ignored'
        self.event('dice', f'Random Number → {rn}', random_number=rn)
        self.event('combat', f"Combat Ratio {b['ratio']:+d}：敵 {enemy_text} / Lone Wolf {hero_text} ENDURANCE loss",
                   combat_ratio=b['ratio'], enemy_loss=enemy_loss, hero_loss=hero_loss, evasion=evade)
        if self.hero.endurance <= 0:
            self.event('hurt', 'ENDURANCEが0になった。冒険はここで終わる。')
            self.battle = None
            return
        if evade:
            target = b['evade_target']
            if not target:
                raise KaiRuleError('This combat cannot be evaded.')
            self.event('flee', f'戦闘を回避し §{target} へ。')
            self.enter(target)
            return
        if enemy['endurance'] <= 0:
            self.event('victory', enemy['name'] + 'を倒した。')
            self.defeated.add((self.current, b['index']))
            self.last_combat_section = self.current
            self.battle = None
            self._begin_next_combat()
            return
        b['round'] += 1

    def apply(self, key: str) -> dict:
        if key not in {a['key'] for a in self.actions()}:
            raise KaiRuleError('現在は選べない行動です。')
        before = copy.deepcopy((self.hero, self.current, self.battle, self.defeated, self.last_combat_section, self.steps, self.events, self.rng.getstate()))
        self.events = []
        try:
            if key == 'kai:combat':
                self._resolve_round(False)
            elif key == 'kai:evade':
                self._resolve_round(True)
            elif key == 'kai:potion':
                count = self.hero.backpack.get('Healing Potion', 0)
                if count < 1 or self.battle:
                    raise KaiRuleError('Healing Potionは今は使えません。')
                if count == 1: self.hero.backpack.pop('Healing Potion')
                else: self.hero.backpack['Healing Potion'] = count - 1
                old = self.hero.endurance
                self.hero.endurance = min(self.hero.max_endurance, self.hero.endurance + 4)
                self.event('heal', f'Healing Potion：ENDURANCE +{self.hero.endurance-old} → {self.hero.endurance}')
            elif key.startswith('kai:equip:'):
                weapon = key.split(':',2)[2]
                if self.battle or weapon not in self.hero.weapons:
                    raise KaiRuleError('その武器には変更できません。')
                self.hero.active_weapon = weapon
                self.event('equip', weapon + 'を使用武器にした。')
            else:
                choice = next(c for c in self.section.choices if c.key == key)
                self.enter(choice.target)
            self.steps += 1
            return {'events': copy.deepcopy(self.events), 'character': self.character(), 'combat': self.combat_view()}
        except Exception:
            hero, current, battle, defeated, last_combat, steps, events, rng_state = before
            self.hero, self.current, self.battle, self.defeated = hero, current, battle, defeated
            self.last_combat_section, self.steps, self.events = last_combat, steps, events
            self.rng.setstate(rng_state)
            raise

    def character(self) -> dict:
        cs, notes = self.effective_combat_skill(self.battle['enemy'] if self.battle else None)
        return {
            'endurance': self.hero.endurance, 'max_endurance': self.hero.max_endurance,
            'combat_skill': cs, 'base_combat_skill': self.hero.base_combat_skill,
            'combat_skill_notes': notes, 'gold': self.hero.gold,
            'disciplines': sorted(self.hero.disciplines), 'weaponskill_weapon': self.hero.weaponskill_weapon,
            'weapons': self.hero.weapons[:], 'active_weapon': self.hero.active_weapon,
            'backpack': [{'name':k,'count':v} for k,v in sorted(self.hero.backpack.items())],
            'special_items': self.hero.special_items[:],
            'limits': {'weapons':2,'backpack':8,'gold':50},
        }

    def combat_view(self) -> dict | None:
        if not self.battle:
            return None
        e = self.battle['enemy']
        return {
            'name': e['name'], 'endurance': e['endurance'], 'max_endurance': e['max_endurance'],
            'combat_skill': e['combat_skill'], 'round': self.battle['round'],
            'combat_ratio': self.battle['ratio'], 'can_evade': bool(self.battle.get('evade_target')),
            'mindblast_immune': e.get('mindblast_immune', False), 'notes': self.battle['notes'],
        }

    def observation(self) -> dict:
        return {
            'current': self.current,
            'section': {'title': self.section.title or f'Section {self.current}', 'text': self.section.paragraphs or [self.section.text]},
            'character': self.character(), 'combat': self.combat_view(), 'actions': self.actions(),
            'blocked': [], 'status': self.status,
            'ending': ({'status': self.status, 'title':'Lone Wolf has fallen'} if self.hero.endurance <= 0 else None),
        }

    def model_state(self, history: list[dict]) -> str:
        return (
            'Lone Wolf / Project Aon Kai-rules compatibility mode.\n'
            'The engine applies the standard Kai Combat Results Table. Combat is normally stochastic, not a tactical action menu. '
            'Only choose from the currently available passage/combat/evasion actions. Do not invent items, disciplines or modifiers.\n'
            + json.dumps(self.observation(), ensure_ascii=False)
            + '\nObserved actions/results only: ' + json.dumps(history[-12:], ensure_ascii=False)
        )

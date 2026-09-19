"""Authoritative, seeded rules for the original Japanese gamebook.

The reader selects only an action ID. Inventory, conditions, dice and endings
are resolved here, never by a model or browser. Not a Lone Wolf rules engine.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import asdict, dataclass, field

from gamebook_jev import Choice, ProjectAonBook, Section


class RuleError(ValueError):
    pass


@dataclass
class Hero:
    hp: int = 30
    max_hp: int = 30
    skill: int = 4
    agility: int = 3
    focus: int = 3
    max_focus: int = 4
    gold: int = 9
    tide: int = 0
    inventory: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)
    flags: set[str] = field(default_factory=set)
    clues: set[str] = field(default_factory=set)


class RPGBook(ProjectAonBook):
    def __init__(self, spec: dict):
        self.spec = copy.deepcopy(spec)
        self.validate()
        self.fingerprint = hashlib.sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        sections = {
            sid: Section(sid, '\n\n'.join(n['text']), [], paragraphs=n['text'][:], title=n['title'])
            for sid, n in self.spec['sections'].items()
        }
        super().__init__(sections)

    def validate(self):
        s = self.spec
        if s.get('format') != 'decision-gamebook/v1':
            raise RuleError('Unknown story format')
        nodes, items, clues, enemies = (s[k] for k in ('sections', 'items', 'clues', 'enemies'))
        if not nodes or any(not isinstance(k, str) for k in nodes):
            raise RuleError('Sections require string IDs')
        for key in ('start', 'death', 'deadline'):
            if s[key] not in nodes:
                raise RuleError(f'Missing {key} section')
        if not 1 <= s['tide_limit'] <= 100:
            raise RuleError('Invalid tide limit')

        def condition(c):
            if not isinstance(c, dict):
                raise RuleError('Condition must be an object')
            allowed = {'all', 'any', 'not', 'flag', 'clue', 'item', 'gold', 'tide_max', 'tide_min'}
            if set(c) - allowed:
                raise RuleError('Unknown condition')
            for op in ('all', 'any'):
                if op in c:
                    if not c[op]:
                        raise RuleError('Empty condition list')
                    for part in c[op]:
                        condition(part)
            if 'not' in c:
                condition(c['not'])
            if 'clue' in c and c['clue'] not in clues:
                raise RuleError('Unknown clue')
            if 'item' in c and c['item'] not in items:
                raise RuleError('Unknown item')

        def effects(e):
            if set(e) - {'hp', 'focus', 'gold', 'tide', 'items', 'flags', 'clues'}:
                raise RuleError('Unknown effect')
            for key in ('hp', 'focus', 'gold', 'tide'):
                if key in e and type(e[key]) is not int:
                    raise RuleError('Effects must use integers')
            for key, amount in e.get('items', {}).items():
                if key not in items or type(amount) is not int:
                    raise RuleError('Unknown item or invalid quantity')
            if any(c not in clues for c in e.get('clues', [])):
                raise RuleError('Unknown clue effect')

        for sid, node in nodes.items():
            if not node.get('title') or not node.get('text') or not all(isinstance(p, str) for p in node['text']):
                raise RuleError(f'Invalid narrative: {sid}')
            effects(node.get('enter', {})); effects(node.get('repeat', {}))
            for variant in node.get('variants', []):
                condition(variant['requires'])
                if not variant.get('text') or not all(isinstance(p, str) for p in variant['text']):
                    raise RuleError('Invalid narrative variant')
            ids = set()
            for choice in node.get('choices', []):
                key = choice['id']
                if not key or ':' in key or key in ids:
                    raise RuleError(f'Duplicate/reserved choice ID in {sid}')
                ids.add(key)
                if choice['to'] not in nodes:
                    raise RuleError(f'Dangling choice in {sid}')
                condition(choice.get('requires', {})); effects(choice.get('effects', {}))
                if 'test' in choice:
                    test = choice['test']
                    if test['stat'] not in ('skill', 'agility') or type(test['dc']) is not int:
                        raise RuleError('Invalid check')
                    if test['success'] not in nodes or test['failure'] not in nodes:
                        raise RuleError('Dangling test destination')
            if 'combat' in node:
                battle = node['combat']
                if battle['enemy'] not in enemies or battle['win'] not in nodes or (battle.get('flee') and battle['flee'] not in nodes):
                    raise RuleError('Invalid encounter')
                for mod in battle.get('modifiers', []):
                    condition(mod['requires'])
                    if set(mod.get('stats', {})) - {'hp', 'armor', 'skill', 'guard', 'power'}:
                        raise RuleError('Invalid enemy modifier')
            if 'ending' in node and node['ending']['status'] not in ('success', 'deadend', 'ending'):
                raise RuleError('Unknown ending status')
            if not node.get('choices') and 'combat' not in node and 'ending' not in node:
                raise RuleError(f'Unintended softlock at {sid}')
        for enemy in enemies.values():
            if not enemy.get('pattern') or set(enemy['pattern']) - {'attack', 'charge', 'heavy', 'guard', 'recover'}:
                raise RuleError('Unknown enemy intent')
            effects(enemy.get('loot', {}))
        for item in items.values():
            if item['kind'] not in ('weapon', 'armor', 'heal', 'bomb', 'smoke', 'quest'):
                raise RuleError('Unknown item kind')
        for item, count in s['initial']['inventory'].items():
            if item not in items or type(count) is not int or count < 1:
                raise RuleError('Invalid initial inventory')
        for slot, item in s['initial']['equipment'].items():
            if slot not in ('weapon', 'armor') or items[item]['kind'] != slot or item not in s['initial']['inventory']:
                raise RuleError('Invalid initial equipment')

    def new_engine(self, seed: int = 17) -> 'RPGEngine':
        return RPGEngine(self, seed)


INTENTS = {
    'attack': ('斬り込み', '通常攻撃。'),
    'charge': ('大振りの予備動作', 'この手では攻撃しない。次の構えに注意。'),
    'heavy': ('大振り', '命中するとダメージ＋3。防御で軽減できる。'),
    'guard': ('身を固める', 'この手の回避値＋2。攻撃もしてくる。'),
    'recover': ('体勢を立て直す', 'この手では攻撃しない。'),
}


class RPGEngine:
    def __init__(self, book: RPGBook, seed: int):
        self.book = book
        self.hero = Hero(**copy.deepcopy(book.spec['initial']))
        self.rng = random.Random(seed ^ 0xB311)
        self.current = book.spec['start']
        self.visited: set[str] = set()
        self.used: set[str] = set()
        self.battle: dict | None = None
        self.ready = False
        self.steps = 0
        self.events: list[dict] = []
        self.enter(self.current)

    @property
    def node(self):
        return self.book.spec['sections'][self.current]

    @property
    def status(self):
        ending = self.node.get('ending')
        if ending:
            return ending['status']
        return 'max_steps' if self.steps >= 200 else 'live'

    def event(self, kind: str, text: str, **detail):
        self.events.append({'kind': kind, 'text': text, **detail})

    def matches(self, c: dict) -> bool:
        h = self.hero
        for op, value in c.items():
            ok = {
                'all': lambda: all(self.matches(x) for x in value),
                'any': lambda: any(self.matches(x) for x in value),
                'not': lambda: not self.matches(value),
                'flag': lambda: value in h.flags,
                'clue': lambda: value in h.clues,
                'item': lambda: h.inventory.get(value, 0) > 0,
                'gold': lambda: h.gold >= value,
                'tide_max': lambda: h.tide <= value,
                'tide_min': lambda: h.tide >= value,
            }.get(op)
            if ok is None:
                raise RuleError(f'Unknown condition: {op}')
            if not ok():
                return False
        return True

    def affordable(self, e: dict) -> bool:
        return (self.hero.gold + e.get('gold', 0) >= 0 and
                all(self.hero.inventory.get(k, 0) + v >= 0 for k, v in e.get('items', {}).items()))

    def effect(self, e: dict):
        if not self.affordable(e):
            raise RuleError('所持金か道具が足りません。')
        h = self.hero
        for key, ceiling in [('hp', h.max_hp), ('focus', h.max_focus), ('tide', self.book.spec['tide_limit'])]:
            amount = e.get(key, 0)
            if amount:
                old = getattr(h, key)
                value = max(0, min(ceiling, old + amount)); setattr(h, key, value)
                name = {'hp': '体力', 'focus': '集中', 'tide': '潮位'}[key]
                self.event('heal' if key == 'hp' and value > old else 'effect', f'{name} {value-old:+d} → {value}', stat=key, delta=value-old)
        if e.get('gold'):
            h.gold += e['gold']; self.event('item', f"銀貨 {e['gold']:+d} → {h.gold}")
        for key, amount in e.get('items', {}).items():
            value = h.inventory.get(key, 0) + amount
            if value:
                h.inventory[key] = value
            else:
                h.inventory.pop(key, None)
                h.equipment = {s: i for s, i in h.equipment.items() if i != key}
            self.event('item', f"{self.book.spec['items'][key]['name']} {amount:+d}")
        h.flags.update(e.get('flags', []))
        for clue in e.get('clues', []):
            if clue not in h.clues:
                h.clues.add(clue)
                self.event('clue', '手がかり：' + self.book.spec['clues'][clue]['title'])

    def enter(self, sid: str):
        self.current = sid
        self.battle = None
        self.ready = False
        first = sid not in self.visited
        self.visited.add(sid)
        if first:
            self.effect(self.node.get('enter', {}))
        self.effect(self.node.get('repeat', {}))
        if self.check_end():
            return
        spec = self.node.get('combat')
        if spec:
            # A won encounter never re-spawns. Fleeing forfeits loot and resets it.
            if 'won:' + sid in self.hero.flags:
                self.enter(spec['win']); return
            enemy = copy.deepcopy(self.book.spec['enemies'][spec['enemy']])
            for mod in spec.get('modifiers', []):
                if self.matches(mod['requires']):
                    for stat, delta in mod['stats'].items():
                        enemy[stat] = max(0, enemy[stat] + delta)
                    self.event('clue', mod['text'])
            enemy['hp'] = max(1, enemy['hp'])
            self.battle = {'enemy': enemy, 'max_hp': enemy['hp'], 'round': 1,
                           'win': spec['win'], 'flee': spec.get('flee')}
            self.event('battle_start', f"{enemy['name']}が立ちはだかった。")

    def check_end(self):
        target = None
        if self.hero.hp <= 0:
            target = self.book.spec['death']
        elif self.hero.tide >= self.book.spec['tide_limit']:
            target = self.book.spec['deadline']
        if target:
            self.current = target; self.battle = None
            self.visited.add(target)
            return True
        return bool(self.node.get('ending'))

    def weapon(self):
        return self.book.spec['items'].get(self.hero.equipment.get('weapon'), {'power': 0, 'accuracy': 0, 'name': '素手'})

    def armor(self):
        return self.book.spec['items'].get(self.hero.equipment.get('armor'), {}).get('armor', 0)

    def intent(self):
        b = self.battle
        return b['enemy']['pattern'][(b['round'] - 1) % len(b['enemy']['pattern'])] if b else None

    def actions(self) -> list[dict]:
        if self.status != 'live':
            return []
        result = []
        def add(key, text, kind='story', target=None):
            result.append({'key': key, 'text': text, 'target': target or self.current, 'kind': kind})
        if self.battle:
            add('combat:attack', '攻撃する — d6＋技量＋武器命中。命中時 d6＋威力−敵装甲。', 'combat')
            if self.hero.focus >= 2:
                add('combat:precision', '精密攻撃 — 集中2。必中、装甲を無視して威力＋5。', 'combat')
            add('combat:guard', '防御する — 今回の回避＋2／被害−4、集中＋2。次の通常攻撃の命中＋2。', 'combat')
            if self.battle['flee']:
                add('combat:flee', '撤退を試みる — d6＋敏捷≧8。失敗すると反撃を受ける。', 'combat', self.battle['flee'])
        else:
            for ch in self.node.get('choices', []):
                if self.available(ch):
                    label = ch['text']
                    cost = ch.get('effects', {}).get('tide', 0)
                    if cost > 0:
                        label += f'〔潮位＋{cost}〕'
                    if 'test' in ch:
                        test = ch['test']; stat = '技量' if test['stat'] == 'skill' else '敏捷'
                        label += f"〔d6＋{stat}≧{test['dc']}〕"
                    add(ch['id'], label, target=ch['to'])
        for key, count in self.hero.inventory.items():
            item = self.book.spec['items'][key]; kind = item['kind']
            if kind in ('weapon', 'armor') and not self.battle and self.hero.equipment.get(kind) != key:
                add('equip:' + key, item['name'] + 'を装備する', 'equipment')
            elif kind == 'heal' and (not self.battle or item.get('combat', True)) and (
                self.hero.hp < self.hero.max_hp or (item.get('focus', 0) and self.hero.focus < self.hero.max_focus)):
                add('use:' + key, f"{item['name']}を使う（残{count}）— 体力＋{item['heal']}" + (f"／集中＋{item['focus']}" if item.get('focus') else '') + ('。敵の手番が進む。' if self.battle else ''), 'item')
            elif kind == 'bomb' and self.battle:
                add('use:' + key, f"{item['name']}を投げる（残{count}）— 敵に固定{item['damage']}ダメージ。", 'item')
            elif kind == 'smoke' and self.battle and self.battle['flee']:
                add('use:' + key, f"{item['name']}を使い確実に撤退する（残{count}）", 'item', self.battle['flee'])
        return result

    def available(self, ch: dict) -> bool:
        return (not (ch.get('once') and f"{self.current}:{ch['id']}" in self.used)
                and self.matches(ch.get('requires', {})) and self.affordable(ch.get('effects', {})))

    def blocked(self):
        if self.battle or self.status != 'live':
            return []
        result = []
        for ch in self.node.get('choices', []):
            if self.available(ch) or ch.get('hidden') or (ch.get('once') and f"{self.current}:{ch['id']}" in self.used):
                continue
            result.append({'text': ch['text'], 'reason': ch.get('locked', '必要な道具・所持金・手がかりが揃っていない。')})
        return result

    def roll(self, label: str) -> int:
        value = self.rng.randint(1, 6)
        self.event('dice', f'{label}：d6 → {value}', die=value, label=label)
        return value

    def apply(self, key: str) -> dict:
        if key not in {a['key'] for a in self.actions()}:
            raise RuleError('現在は選べない行動です。')
        # Transactional effects and RNG: failed writes consume neither items nor rolls.
        before = (copy.deepcopy(self.hero), copy.deepcopy(self.battle), self.current,
                  self.visited.copy(), self.used.copy(), self.ready, self.steps, self.rng.getstate(), self.events[:])
        self.events = []
        try:
            self._apply(key); self.steps += 1
            self.check_end()
            assert 0 <= self.hero.hp <= self.hero.max_hp and self.hero.gold >= 0
            assert all(v > 0 for v in self.hero.inventory.values())
            return {'events': copy.deepcopy(self.events), 'character': self.character(), 'combat': self.combat_view()}
        except Exception:
            self.hero, self.battle, self.current, self.visited, self.used, self.ready, self.steps, rng, self.events = before
            self.rng.setstate(rng)
            raise

    def _apply(self, key: str):
        fighting = self.battle is not None
        guarded = False
        if key.startswith('equip:'):
            item_id = key.split(':', 1)[1]; item = self.book.spec['items'][item_id]
            self.hero.equipment[item['kind']] = item_id
            self.event('equip', item['name'] + 'を装備した。'); return
        if key.startswith('use:'):
            item_id = key.split(':', 1)[1]; item = self.book.spec['items'][item_id]
            self.effect({'items': {item_id: -1}})
            if item['kind'] == 'heal':
                self.effect({'hp': item['heal'], 'focus': item.get('focus', 0)})
            elif item['kind'] == 'bomb':
                self.battle['enemy']['hp'] = max(0, self.battle['enemy']['hp'] - item['damage'])
                self.event('hit', f"{item['name']}：敵に{item['damage']}ダメージ。", damage=item['damage'])
            elif item['kind'] == 'smoke':
                target = self.battle['flee']; self.event('flee', '煙にまぎれて撤退した。'); self.enter(target); return
        elif fighting:
            b = self.battle; e = b['enemy']; w = self.weapon()
            if key == 'combat:guard':
                guarded = True; self.ready = True
                self.effect({'focus': 2}); self.event('guard', '身を低くして次の一撃に備える。')
            elif key == 'combat:precision':
                self.effect({'focus': -2}); self.ready = False
                damage = w.get('power', 0) + 5
                e['hp'] = max(0, e['hp'] - damage)
                self.event('hit', f'精密攻撃：{damage}ダメージ。装甲を貫いた。', damage=damage)
            elif key == 'combat:attack':
                die = self.roll('あなたの命中')
                total = die + self.hero.skill + w.get('accuracy', 0) + (2 if self.ready else 0)
                self.ready = False
                defense = e['guard'] + (2 if self.intent() == 'guard' else 0)
                if total >= defense:
                    damage = max(1, self.roll('あなたの威力') + w.get('power', 0) - e['armor'])
                    e['hp'] = max(0, e['hp'] - damage)
                    self.event('hit', f'命中 {total}≧{defense}。{damage}ダメージ。', damage=damage)
                else:
                    self.event('miss', f'命中 {total}＜{defense}。刃は届かない。')
            elif key == 'combat:flee':
                if self.roll('撤退') + self.hero.agility >= 8:
                    target = b['flee']; self.event('flee', '間合いを切って撤退した。'); self.enter(target); return
                self.event('miss', '退路を塞がれた。')
        else:
            ch = next(c for c in self.node['choices'] if c['id'] == key)
            self.used.add(f'{self.current}:{key}')
            self.effect(ch.get('effects', {}))
            target = ch['to']
            if 'test' in ch:
                test = ch['test']; total = self.roll('探索判定') + getattr(self.hero, test['stat'])
                passed = total >= test['dc']; target = test['success' if passed else 'failure']
                self.event('check', f"判定 {total} / 目標{test['dc']}：{'成功' if passed else '失敗'}。", passed=passed)
            if not self.check_end():
                self.enter(target)
            return
        if not fighting:
            return
        b = self.battle; e = b['enemy']
        if e['hp'] <= 0:
            target = b['win']; self.hero.flags.add('won:' + self.current)
            self.event('victory', e['name'] + 'との戦いを制した。')
            self.effect(e.get('loot', {})); self.enter(target); return
        intent = self.intent()
        if intent in ('charge', 'recover'):
            self.event('enemy', f"{e['name']}は{INTENTS[intent][0]}。攻撃は来ない。")
        else:
            die = self.roll('敵の命中')
            defense = 7 + self.hero.agility // 2 + (2 if guarded else 0)
            if die + e['skill'] >= defense:
                amount = self.roll('敵の威力') + e['power'] + (3 if intent == 'heavy' else 0)
                damage = max(0, amount - self.armor() - (4 if guarded else 0))
                self.hero.hp = max(0, self.hero.hp - damage)
                self.event('hurt', f'敵の攻撃：{damage}ダメージ。体力{self.hero.hp}。', damage=damage)
            else:
                self.event('evade', f"敵の命中 {die+e['skill']}＜{defense}。攻撃をかわした。")
        if not self.check_end():
            b['round'] += 1

    def character(self):
        h = self.hero
        return {'hp': h.hp, 'max_hp': h.max_hp, 'focus': h.focus, 'max_focus': h.max_focus,
                'skill': h.skill, 'agility': h.agility, 'gold': h.gold, 'tide': h.tide,
                'tide_limit': self.book.spec['tide_limit'], 'power': self.weapon().get('power', 0),
                'accuracy': self.weapon().get('accuracy', 0), 'armor': self.armor(),
                'allies': [name for key, name in [('helped_child', '灯（調律の助手）'), ('helped_maki', '槙（舟の渡し）'), ('helped_ringer', '老鐘打ち')] if key in h.flags],
                'sluice_open': 'sluice_open' in h.flags,
                'inventory': [{'id': k, 'count': v, **self.book.spec['items'][k],
                               'equipped': k in h.equipment.values()} for k, v in h.inventory.items()],
                'clues': [{'id': k, **self.book.spec['clues'][k]} for k in sorted(h.clues)]}

    def combat_view(self):
        if not self.battle:
            return None
        e = self.battle['enemy']; code = self.intent()
        return {'name': e['name'], 'hp': e['hp'], 'max_hp': self.battle['max_hp'],
                'skill': e['skill'], 'guard': e['guard'], 'armor': e['armor'], 'power': e['power'],
                'round': self.battle['round'], 'intent': code, 'intent_name': INTENTS[code][0],
                'intent_hint': INTENTS[code][1], 'can_flee': bool(self.battle['flee']),
                'prepared': self.ready}

    def paragraphs(self) -> list[str]:
        for variant in self.node.get('variants', []):
            if self.matches(variant['requires']):
                return variant['text'][:]
        return self.node['text'][:]

    def observation(self) -> dict:
        return {'current': self.current, 'section': {'title': self.node['title'], 'text': self.paragraphs()},
                'character': self.character(), 'combat': self.combat_view(), 'actions': self.actions(),
                'blocked': self.blocked(), 'status': self.status, 'ending': self.node.get('ending')}

    def model_state(self, history: list[dict]) -> str:
        # Only the present passage, owned items and clues actually acquired.
        # No entire book, target ending ID, hidden flags, RNG state or future pages.
        return ('日本語ゲームブック。目的：' + self.book.spec['objective'] + '\n'
                '現在選べる行動だけから1つ選ぶ。記載された効果とコストを比較する。'
                '戦闘の「溜め」「立て直し」は回復の機会。「大振り」には防御が有効。'
                '精密攻撃は集中2。防御は集中2回復。回復薬使用時も敵は行動する。'
                '潮位が16になると終了する。数値はエンジンだけが更新する。\n'
                + json.dumps(self.observation(), ensure_ascii=False)
                + '\n直近の行動と実際の結果：' + json.dumps(history[-12:], ensure_ascii=False))

"""Known-route regression policies, NOT Jev output or an intelligence benchmark."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from story_ja import make_story

TRUE_ROUTE = [
 ('1','gate'),('2','harbor'),('3','alley'),('4','save'),
 ('6','return'),('3','market'),('7','blade'),('7','back'),
 ('3','archive'),('16','reading'),('17','child'),('18','sao'),('20','ledger'),
 ('21','take'),('22','keep'),('23','letter'),('24','go'),('25','pump'),('26','signal'),
 ('28','panel'),('29','sea'),('30','drain'),('31','chapel'),('35','inside'),
 ('36','clean'),('37','score'),('38','bridge'),('41','dry'),('43','child'),('60','back'),
 ('43','window'),('44','focus'),('45','speak'),('46','contract'),('47','unmake'),('50','restore'),
]


def battle_action(e):
    actions = {a['key'] for a in e.actions()}; enemy = e.battle['enemy']
    if 'combat:precision' in actions and enemy['hp'] <= e.weapon().get('power', 0) + 5:
        return 'combat:precision'
    if enemy['hp'] <= 8 and 'use:saltbomb' in actions:
        return 'use:saltbomb'
    if e.hero.hp <= 12 and 'use:tonic' in actions:
        return 'use:tonic'
    if e.intent() == 'heavy':
        return 'combat:guard'
    return 'combat:precision' if 'combat:precision' in actions else 'combat:guard'


def prepare(e):
    # Uses only acquired equipment/items and public stats; no state injection.
    for slot in ('weapon', 'armor'):
        candidates = [i for i in e.hero.inventory if e.book.spec['items'][i]['kind'] == slot]
        best = max(candidates, key=lambda i: e.book.spec['items'][i].get('power', 0)*10 + e.book.spec['items'][i].get('accuracy', 0) + e.book.spec['items'][i].get('armor', 0))
        key = 'equip:' + best
        if key in {a['key'] for a in e.actions()}:
            e.apply(key)
    if e.hero.hp <= 20 and e.hero.inventory.get('tonic'):
        e.apply('use:tonic')


def walk(route=TRUE_ROUTE, seed=17, final=None):
    e = make_story().new_engine(seed)
    actions = []
    for sid, key in route:
        while e.battle and e.status == 'live':
            k = battle_action(e); actions.append(k); e.apply(k)
        if e.status != 'live':
            return e
        prepare(e)
        assert e.current == sid, (seed, sid, e.current, e.status)
        e.apply(key); actions.append(key)
    return e


if __name__ == '__main__':
    from collections import Counter
    results = Counter()
    for seed in range(100):
        e = walk(seed=seed)
        results[e.node.get('ending', {}).get('id', e.status)] += 1
    print(dict(results))
    e = walk(); print('Seed 17:', e.status, 'HP', e.hero.hp, 'tide', e.hero.tide, 'steps', e.steps)

"""Engine invariants + complete original-story routes. No paid model calls."""
import copy
import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rpg_engine import RPGBook, RuleError
from story_ja import build_spec, make_story
from tools.rpg_scenarios import TRUE_ROUTE, battle_action, walk
from web_app import AppError, GamebookService
from gamebook_jev import Decision


@pytest.fixture
def engine():
    return make_story().new_engine(17)


def keys(e): return {a['key'] for a in e.actions()}


def test_story_graph_complete_and_original_counts():
    b = make_story(); s = b.spec
    assert len(s['sections']) == 60
    assert len(s['items']) == 17
    assert len(s['enemies']) == 8
    assert sum('ending' in n for n in s['sections'].values()) == 7
    visited = {s['death'], s['deadline']}; stack = [s['start']]
    while stack:
        sid = stack.pop()
        if sid in visited: continue
        visited.add(sid); node = s['sections'][sid]
        stack += [c['to'] for c in node['choices']]
        for c in node['choices']:
            if 'test' in c: stack.extend([c['test']['success'], c['test']['failure']])
        if 'combat' in node:
            stack.append(node['combat']['win'])
            if node['combat']['flee']: stack.append(node['combat']['flee'])
    assert visited == set(s['sections'])


@pytest.mark.parametrize('fault', ['condition', 'destination', 'effect', 'duplicate', 'enemy'])
def test_validation_fails_closed(fault):
    s = build_spec()
    c = s['sections']['1']['choices'][0]
    if fault == 'condition': c['requires'] = {'arbitrary': 'eval'}
    elif fault == 'destination': c['to'] = '999'
    elif fault == 'effect': c['effects'] = {'exec': 'bad'}
    elif fault == 'duplicate': s['sections']['1']['choices'].append(copy.deepcopy(c))
    elif fault == 'enemy': s['sections']['5']['combat']['enemy'] = 'missing'
    with pytest.raises(RuleError): RPGBook(s)


def test_invalid_action_does_not_mutate_or_consume_rng(engine):
    before = engine.observation(); rng = engine.rng.getstate()
    with pytest.raises(RuleError): engine.apply('restore')
    assert engine.observation() == before
    assert engine.rng.getstate() == rng
    assert engine.steps == 0


def test_healing_bounds_and_consumption(engine):
    assert 'use:tonic' not in keys(engine)
    engine.hero.hp = 28
    engine.apply('use:tonic')
    assert engine.hero.hp == 30 and engine.hero.inventory['tonic'] == 1
    with pytest.raises(RuleError): engine.apply('use:tonic')
    assert engine.hero.inventory['tonic'] == 1


def test_equipment_requires_ownership_and_out_of_combat(engine):
    with pytest.raises(RuleError): engine.apply('equip:guardcoat')
    engine.effect({'items': {'guardcoat': 1, 'silverblade': 1}})
    engine.apply('equip:guardcoat'); engine.apply('equip:silverblade')
    assert engine.armor() == 3 and engine.weapon()['power'] == 4
    engine.enter('5')
    assert not any(k.startswith('equip:') for k in keys(engine))
    assert 'use:ration' not in keys(engine)


def test_combat_guard_and_precision_real_rules(engine):
    engine.enter('5'); old = engine.battle['enemy']['hp']
    engine.apply('combat:guard')
    assert engine.hero.focus == 4 and engine.ready
    assert engine.battle['round'] == 2
    result = engine.apply('combat:precision')
    assert engine.hero.focus == 2 and not engine.ready
    assert engine.battle['enemy']['hp'] == old - 7
    assert any(e['kind'] == 'hit' and e['damage'] == 7 for e in result['events'])
    # Restore an ongoing encounter for the explicit resource-gating check.
    engine.hero.focus = 1
    assert 'combat:precision' not in keys(engine)
    with pytest.raises(RuleError): engine.apply('combat:precision')


def test_regular_attack_rolls_are_reproducible():
    a, b = make_story().new_engine(98), make_story().new_engine(98)
    a.enter('5'); b.enter('5')
    assert a.apply('combat:attack') == b.apply('combat:attack')
    assert any(e['kind'] == 'dice' for e in a.events)


def test_use_potion_still_advances_enemy_turn(engine):
    engine.enter('5'); engine.hero.hp = 12
    result = engine.apply('use:tonic')
    assert engine.battle['round'] == 2
    assert engine.hero.inventory['tonic'] == 1
    assert any(e['kind'] == 'enemy' for e in result['events'])


def test_bomb_kill_has_no_posthumous_counterattack(engine):
    engine.enter('5'); engine.battle['enemy']['hp'] = 5
    hp = engine.hero.hp
    result = engine.apply('use:saltbomb')
    assert engine.current == '6' and engine.battle is None
    assert engine.hero.hp == hp
    assert any(e['kind'] == 'victory' for e in result['events'])
    assert 'saltbomb' not in engine.hero.inventory
    assert not any(e['kind'] == 'hurt' for e in result['events'])


def test_flee_no_loot_and_enemy_resets(engine):
    engine.effect({'items': {'smoke': 1}})
    engine.enter('5'); engine.battle['enemy']['hp'] = 1
    gold = engine.hero.gold
    engine.apply('use:smoke')
    assert engine.current == '3' and engine.hero.gold == gold
    assert 'smoke' not in engine.hero.inventory
    engine.enter('5'); assert engine.battle['enemy']['hp'] == 13
    engine.enter('48'); engine.effect({'items': {'smoke': 1}})
    assert 'combat:flee' not in keys(engine) and 'use:smoke' not in keys(engine)


def test_victory_and_discovery_rewards_never_farm(engine):
    engine.enter('5')
    while engine.battle: engine.apply(battle_action(engine))
    gold = engine.hero.gold; items = engine.hero.inventory.copy()
    engine.enter('5')
    assert engine.current == '6' and engine.battle is None
    assert engine.hero.gold == gold and engine.hero.inventory == items
    engine.enter('14'); gold = engine.hero.gold; items = engine.hero.inventory.copy()
    engine.enter('3'); engine.enter('14')
    assert engine.hero.gold == gold and engine.hero.inventory == items


def test_money_and_once_purchase(engine):
    engine.enter('7'); engine.apply('blade')
    assert engine.hero.gold == 1 and engine.hero.inventory['silverblade'] == 1
    assert 'blade' not in keys(engine) and 'coat' not in keys(engine)
    before = engine.observation()
    with pytest.raises(RuleError): engine.apply('coat')
    assert engine.observation() == before


def test_ledger_or_coins_exclusive_on_revisit(engine):
    engine.enter('22'); gold = engine.hero.gold
    engine.apply('keep'); engine.enter('22')
    assert 'money' not in keys(engine) and 'keep' not in keys(engine)
    assert 'continue' in keys(engine)
    assert engine.hero.gold == gold and engine.hero.inventory['ledger'] == 1


def test_conditions_and_clue_journal(engine):
    engine.enter('17')
    assert 'child' not in keys(engine) and 'seal' not in keys(engine)
    assert len(engine.blocked()) == 2
    engine.effect({'flags': ['helped_child'], 'clues': ['gears']})
    assert 'child' in keys(engine)
    assert engine.character()['clues'][0]['title'] == '整備屋の合図'
    assert engine.character()['allies'] == ['灯（調律の助手）']


def test_sluice_puzzle_wrong_damage_repeats_correct_reward_once(engine):
    engine.enter('29'); hp = engine.hero.hp
    engine.apply('city_wrong')
    assert engine.hero.hp == hp - 4 and engine.hero.tide == 2
    engine.apply('return'); engine.apply('city_wrong')
    assert engine.hero.hp == hp - 8 and engine.hero.tide == 4
    engine.apply('return'); engine.apply('sea'); engine.apply('drain')
    assert engine.current == '31' and engine.hero.tide == 2
    assert 'sluice_open' in engine.hero.flags
    engine.hero.tide = 8; engine.enter('31')
    assert engine.hero.tide == 8


def test_stat_test_logs_actual_success_or_failure(engine):
    engine.enter('17'); engine.apply('pick')
    assert engine.current in ('18', '19')
    event = next(e for e in engine.events if e['kind'] == 'check')
    assert (engine.current == '18') == event['passed']


def test_deadline_death_and_terminal_actions(engine):
    engine.hero.tide = 15; engine.enter('2'); engine.apply('harbor')
    assert engine.current == '55' and engine.status == 'deadend' and not engine.actions()
    e = make_story().new_engine(); e.hero.hp = 1; e.enter('42')
    assert e.current == '56' and e.status == 'deadend'
    assert e.battle is None and not e.actions()


@pytest.mark.parametrize('seed', list(range(20)))
def test_true_ending_via_real_choices_no_state_injection(seed):
    e = walk(seed=seed)
    assert e.current == '51' and e.status == 'success'
    assert e.hero.hp > 0 and e.hero.tide == 10
    assert e.node['ending']['id'] == 'names_returned'


@pytest.mark.parametrize('choice,destination', [('sacrifice','52'), ('break','53'), ('repeat','54')])
def test_alternate_endings_via_full_route(choice, destination):
    route = TRUE_ROUTE[:-1] + [('50', choice)]
    e = walk(route, seed=17)
    assert e.current == destination
    assert e.node['ending']


def test_departure_ending_no_combat(engine):
    engine.apply('gate'); engine.apply('leave')
    assert engine.current == '57' and engine.status == 'ending'


def test_story_variants_follow_world_state(engine):
    engine.enter('53'); assert '止まったまま' in ''.join(engine.paragraphs())
    engine.hero.flags.add('sluice_open')
    assert '揚水場の歯車が回り' in ''.join(engine.paragraphs())


def test_seeded_random_fuzz_invariants():
    b = make_story()
    for seed in range(80):
        e = b.new_engine(seed); chooser = random.Random(seed)
        for _ in range(201):
            assert 0 <= e.hero.hp <= e.hero.max_hp
            assert 0 <= e.hero.focus <= e.hero.max_focus
            assert 0 <= e.hero.tide <= 16 and e.hero.gold >= 0
            assert all(v > 0 for v in e.hero.inventory.values())
            if e.status != 'live': break
            actions = e.actions(); assert actions, e.current
            e.apply(chooser.choice(actions)['key'])
        assert e.status != 'live'


def test_service_authoritative_state_and_revision(tmp_path):
    svc = GamebookService(tmp_path)
    a = svc.new_run({'book':'ashbell','seed':17, 'profile':'HP 999 / unlimited potions'})
    assert a['mode'] == 'story_rpg' and a['character']['hp'] == 30
    b = svc.step(a['run_id'], {'revision':0,'choice':'gate', 'hp':999,'gold':999})
    assert b['character']['hp'] == 30 and b['character']['gold'] == 9
    with pytest.raises(AppError): svc.step(a['run_id'], {'revision':0,'choice':'harbor'})
    assert len(svc.get_run(a['run_id']).trace) == 1
    exported = svc.export(a['run_id'])
    assert exported['format'].endswith('/v2')
    assert 'HP 999' not in json.dumps(exported)
    assert len(exported['story_sha256']) == 64
    assert 'before' in exported['trace'][0] and 'after' in exported['trace'][0]


def test_provider_gets_only_legal_rpg_actions_and_public_state(tmp_path, monkeypatch):
    from web_app import JevController
    svc = GamebookService(tmp_path); monkeypatch.setenv('JEV_API_KEY','test-key-not-real')
    run = svc.new_run({'book':'ashbell'})
    seen = []
    def choose(self, state, choices):
        seen.append(state)
        assert '終幕 I · 誰も' not in state
        assert 'current' in state and 'character' in state
        assert 'combat:precision' not in {c.key for c in choices}
        assert 'test-key-not-real' not in state
        n = len(choices)
        return Decision('gate', 1/n, {c.key:1/n for c in choices}, 1)
    monkeypatch.setattr(JevController,'choose',choose)
    state = svc.step(run['run_id'], {'revision':0,'backend':'jev'})
    assert state['current'] == '2' and seen
    assert state['last_decision']['source'] == 'jev'


def test_rpg_combat_does_not_trigger_page_revisit_loop(tmp_path):
    svc = GamebookService(tmp_path); snap = svc.new_run({'book':'ashbell'})
    run = svc.get_run(snap['run_id']); run.engine.enter('5'); run.current = '5'; run.path = ['1','5']
    for revision in range(8):
        snap = svc.step(snap['run_id'], {'revision':revision,'choice':'combat:guard'})
    assert snap['status'] == 'live' and snap['path'] == ['1','5']
    assert snap['steps'] == 8 and snap['combat_state']['round'] == 9

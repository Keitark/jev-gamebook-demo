"""Presentation changes must not become game rules or fictional model results."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamebook_jev import Decision
from reader_presentation import binding, browser_assessment, ordered, reorder_observation, COMBAT_SLOTS
from web_app import GamebookService, AppError


def test_virtual_folios_are_stable_not_turn_counts(tmp_path):
    s = GamebookService(tmp_path)
    a = s.new_run({'book': 'ashbell'})
    first = a['pagination']
    assert first == {'edition':'virtual-one-section-per-spread/v1', 'spread':0, 'left':2,'right':3,'total':122,'section_count':60}
    run = s.get_run(a['run_id'])
    run.engine.steps = 82
    assert run.snapshot()['pagination'] == first
    assert binding(run.book, '60')['right'] == 121
    assert binding(run.book, '5')['left'] == 10


def test_sparse_ids_use_ordinals_not_missing_print_pages(tmp_path):
    s = GamebookService(tmp_path); a = s.new_run({'book':'demo'})
    run = s.get_run(a['run_id'])
    assert binding(run.book, '12')['right'] == 19
    assert a['pagination']['total'] == 20


@pytest.mark.parametrize('mode', ['original', 'balanced'])
def test_order_does_not_consume_game_rng_and_repeat_is_stable(tmp_path, mode):
    s = GamebookService(tmp_path); a = s.new_run({'book':'ashbell', 'choice_order':mode, 'seed':17})
    run = s.get_run(a['run_id']); e = run.engine
    before = (copy.deepcopy(e.observation()), e.rng.getstate(), run.rng.rng.getstate())
    actions = e.actions()
    vis = ordered(run, actions)
    for _ in range(10):
        assert ordered(run, actions) == vis
        ordered(run, actions, provider=True)
        run.snapshot()
    assert before == (e.observation(), e.rng.getstate(), run.rng.rng.getstate())
    remaining = actions[1:]
    assert [x for x in vis if x['key'] in {a['key'] for a in remaining}] == ordered(run, remaining)


def test_balanced_provider_order_rotates_without_policy_override(tmp_path):
    s=GamebookService(tmp_path); a=s.new_run({'book':'demo','choice_order':'balanced'})
    r=s.get_run(a['run_id']); actions=r.book.sections['1'].choices
    orders=set()
    for i in range(20):
        r.revision=i
        orders.add(tuple(x.key for x in ordered(r,actions,provider=True)))
    assert len(orders)>1
    assert {frozenset(x) for x in orders} == {frozenset(c.key for c in actions)}


def test_same_manual_actions_have_same_dice_across_order_modes(tmp_path):
    states=[]
    for mode in ['original','balanced']:
        s=GamebookService(tmp_path); a=s.new_run({'book':'ashbell','choice_order':mode,'seed':17})
        for key in ['gate','harbor','alley','save','combat:attack','combat:attack']:
            a=s.step(a['run_id'],{'revision':a['revision'],'choice':key})
        states.append((a['character'],a['combat_state'],a['path'],a['last_decision']['events']))
    assert states[0] == states[1]


def test_combat_legal_order_uses_fixed_semantic_slots(tmp_path):
    s=GamebookService(tmp_path); a=s.new_run({'book':'ashbell','choice_order':'balanced'})
    for key in ['gate','harbor','alley','save']:
        a=s.step(a['run_id'],{'revision':a['revision'],'choice':key})
    ks=[c['key'] for c in a['section']['choices']]
    assert ks == [x for x in COMBAT_SLOTS if x in ks]
    assert ks[0]=='combat:attack'
    r=s.get_run(a['run_id']); r.engine.hero.focus=0
    b=r.snapshot(); assert 'combat:precision' not in {x['key'] for x in b['section']['choices']}
    assert b['pagination']==a['pagination']


@pytest.mark.parametrize('bad', [None,'shuffle', {}, True, 12])
def test_invalid_order_mode_rejected(tmp_path, bad):
    with pytest.raises(AppError): GamebookService(tmp_path).new_run({'choice_order':bad})


@pytest.mark.parametrize('scores', [
    {}, {'a':1}, {'a':.2,'b':.2}, {'a':True,'b':0},
    {'a':float('nan'),'b':.5}, {'a':float('inf'),'b':0},
    {'a':-.1,'b':1.1}, {'a':1,'b':0,'extra':0},
])
def test_bad_browser_probabilities_are_rejected(scores):
    with pytest.raises(ValueError): browser_assessment({'probabilities':scores},{'a','b'})


def test_manual_click_has_no_invented_probability(tmp_path):
    s=GamebookService(tmp_path); a=s.new_run({'book':'demo','choice_order':'balanced'})
    key=a['section']['choices'][1]['key']
    b=s.step(a['run_id'],{'revision':0,'choice':key})
    d=b['last_decision']
    assert d['source']=='manual' and d['probabilities']=={} and d['confidence'] is None
    assert d['probability_source']=='not_provided'
    assert d['presentation']['display_index']==1 and d['presentation']['provider_index'] is None
    assert b['position_stats']['first_display']==0


def test_browser_report_is_explicit_not_jev(tmp_path):
    s=GamebookService(tmp_path); a=s.new_run({'book':'demo','choice_order':'balanced'})
    keys=[c['key'] for c in a['section']['choices']]
    probs={k:(.8 if i==1 else .1) for i,k in enumerate(keys)}
    b=s.step(a['run_id'],{'revision':0,'choice':keys[1],'assessment':{'probabilities':probs}})
    assert b['last_decision']['source']=='browser'
    assert b['last_decision']['probability_source']=='browser_self_report'
    assert b['last_decision']['confidence'] is None
    assert b['last_decision']['probabilities']==probs
    assert s.export(a['run_id'])['choice_order']=='balanced'
    with pytest.raises(AppError): s.step(a['run_id'],{'revision':0,'choice':keys[1]})


def test_rejected_report_leaves_state_and_rng_untouched(tmp_path):
    s=GamebookService(tmp_path); a=s.new_run({'book':'ashbell'})
    r=s.get_run(a['run_id']); before=copy.deepcopy(r.snapshot()); rng=r.engine.rng.getstate()
    with pytest.raises(AppError):
        s.step(a['run_id'],{'revision':0,'choice':'gate','assessment':{'probabilities':{'gate':.1}}})
    assert before==r.snapshot() and rng==r.engine.rng.getstate()


def test_random_distribution_maps_by_ids_not_positions(tmp_path):
    s=GamebookService(tmp_path); a=s.new_run({'book':'demo','choice_order':'balanced'})
    b=s.step(a['run_id'],{'revision':0,'backend':'random'})
    d=b['last_decision']; keys=[c['key'] for c in a['section']['choices']]
    assert d['probabilities']=={k:1/3 for k in keys}
    assert d['presentation']['display_order']==keys
    assert d['presentation']['display_order'][d['presentation']['display_index']]==d['choice']
    assert d['presentation']['provider_order'][d['presentation']['provider_index']]==d['choice']


def test_provider_prompt_and_api_order_agree(tmp_path, monkeypatch):
    monkeypatch.setenv('JEV_API_KEY','fake-test-key')
    captured={}
    def choose(_self,state,choices):
        captured['state']=state;captured['keys']=[c.key for c in choices]
        return Decision(choices[-1].key,.8,{c.key:(.8 if i==len(choices)-1 else .2/(len(choices)-1)) for i,c in enumerate(choices)},1.0)
    monkeypatch.setattr('web_app.JevController.choose',choose)
    s=GamebookService(tmp_path);a=s.new_run({'book':'ashbell','choice_order':'balanced'})
    r=s.get_run(a['run_id']); original=r.engine.observation()
    b=s.step(a['run_id'],{'revision':0,'backend':'jev'})
    state=captured['state']; start=state.index('{'); observation=json.JSONDecoder().raw_decode(state[start:])[0]
    assert [x['key'] for x in observation['actions']]==captured['keys']
    original.pop('actions'); observation.pop('actions'); assert observation==original
    assert b['last_decision']['choice']==captured['keys'][-1]
    assert 'fake-test-key' not in json.dumps(s.export(a['run_id']))

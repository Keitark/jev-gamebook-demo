"""Separate visual groups without changing legal actions, effects, RNG or folios."""
from __future__ import annotations
from types import SimpleNamespace
from pathlib import Path
import copy
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reader_presentation import ordered, order_trace, binding, COMBAT_SLOTS
from story_ja import make_story


def run(mode='original'):
    book=make_story(); engine=book.new_engine(17)
    return SimpleNamespace(book=book,engine=engine,book_id='ashbell',current='1',revision=0,seed=17,choice_order=mode)


@pytest.mark.parametrize('mode',['original','balanced'])
def test_groups_preserve_actions_rng_and_original_folios(mode):
    r=run(mode); a=r.engine.actions(); state=copy.deepcopy(r.engine.observation()); rng=r.engine.rng.getstate()
    shown=ordered(r,a)
    main=[x for x in shown if not x['key'].startswith(('use:','equip:'))]
    items=[x for x in shown if x['key'].startswith(('use:','equip:'))]
    assert shown==main+items
    assert {x['key'] for x in shown}=={x['key'] for x in a}
    assert all(any(x is original for original in a) for x in shown)
    assert r.engine.observation()==state and r.engine.rng.getstate()==rng
    assert binding(r.book,'1')['right']==3 and binding(r.book,'5')['right']==11


@pytest.mark.parametrize('mode',['original','balanced'])
def test_combat_order_matches_four_main_and_four_item_slots(mode):
    r=run(mode)
    for k in ['gate','harbor','alley','save','combat:attack']:
        r.engine.apply(k)
    r.current=r.engine.current; r.revision=r.engine.steps
    a=r.engine.actions(); keys=[x['key'] for x in ordered(r,a)]
    assert keys==[key for key in COMBAT_SLOTS if key in keys]
    assert keys[:4]==['combat:attack','combat:precision','combat:guard','combat:flee']
    for key in keys:
        trace=order_trace(r,a,ordered(r,a,provider=True),key)
        assert trace['display_order'][trace['display_index']]==key


def test_provider_retains_all_items_without_visual_partition():
    r=run('original'); actions=[{'key':'use:tonic'},{'key':'go'},{'key':'equip:sword'},{'key':'leave'}]
    assert ordered(r,actions,provider=True)==actions
    assert [x['key'] for x in ordered(r,actions)]==['go','leave','use:tonic','equip:sword']


def test_kai_item_ids_are_separated_too():
    r=run(); r.engine=None; r.book_id='aon_kai'
    actions=[{'key':'kai:potion'},{'key':'c0'},{'key':'kai:equip:Axe'},{'key':'c1'}]
    assert [x['key'] for x in ordered(r,actions)]==['c0','c1','kai:potion','kai:equip:Axe']


def test_scene_specific_purchase_is_still_narrative():
    r=run(); a=[{'key':'buy','kind':'story'},{'key':'use:tonic','kind':'item'},{'key':'use_rope','kind':'story'}]
    assert [x['key'] for x in ordered(r,a)]==['buy','use_rope','use:tonic']


def test_remaining_relative_order_stays_stable():
    r=run('balanced'); actions=[{'key':key} for key in ['go','left','right','use:tonic','use:bandage','equip:sword']]
    before=ordered(r,actions)
    for remove in actions:
        rest=[a for a in actions if a is not remove]
        assert ordered(r,rest)==[a for a in before if a is not remove]

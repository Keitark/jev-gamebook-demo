from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamebook_jev import ProjectAonBook
from lonewolf_rules import KaiEngine, KaiRuleError, combat_result, normalize_config
from web_app import GamebookService

FIXTURE = Path(__file__).with_name('kai_fixture.xml')


def test_project_aon_parser_extracts_structured_combat():
    book = ProjectAonBook.from_file(FIXTURE)
    assert book.sections['1'].combat_data == [{'enemy':'Pass Raider','combat_skill':16,'endurance':10}]
    assert 'Pass Raider' in book.sections['1'].combat[0]


def test_standard_kai_combat_table_official_examples():
    # Project Aon Kai examples: CR -3 / RN 6 => enemy -6, Lone Wolf -3.
    assert combat_result(-3, 6) == (6, 3)
    # Appendix C example: CR 0 / RN 6 => enemy -8, Lone Wolf -2.
    assert combat_result(0, 6) == (8, 2)
    # Extreme positive ratio can produce an instant enemy kill.
    assert combat_result(11, 8) == (None, 0)
    # Extreme negative ratio can produce an instant Lone Wolf kill.
    assert combat_result(-11, 1) == (0, None)


def test_action_chart_validation_and_limits():
    cfg = normalize_config(None)
    assert len(cfg['disciplines']) == 5 and len(cfg['weapons']) <= 2
    with pytest.raises(KaiRuleError): normalize_config({'disciplines':['Healing']})
    with pytest.raises(KaiRuleError): normalize_config({'combat_skill':20})
    with pytest.raises(KaiRuleError): normalize_config({'backpack':{'Meal':9}})


def test_weaponskill_mindblast_and_unarmed_adjust_combat_skill():
    book = ProjectAonBook.from_file(FIXTURE)
    e = KaiEngine(book, config=None)
    cs, notes = e.effective_combat_skill({'mindblast_immune':False})
    assert cs == 19  # base15 + Weaponskill2 + Mindblast2
    assert any('Weaponskill' in x for x in notes) and any('Mindblast' in x for x in notes)
    e.hero.weapons = []; e.hero.active_weapon = None
    cs, _ = e.effective_combat_skill({'mindblast_immune':False})
    assert cs == 13  # base15 -4 unarmed +2 Mindblast


def test_combat_round_and_evasion_use_same_table_but_ignore_enemy_damage():
    book = ProjectAonBook.from_file(FIXTURE)
    e = KaiEngine(book, seed=17)
    assert e.battle and e.battle['evade_target'] == '3'
    # Replace RNG with a deterministic RN=6 provider.
    class R:
        def randrange(self, n): return 6
        def getstate(self): return ('fake',)
        def setstate(self, state): pass
    e.rng = R()
    ratio = e.battle['ratio']
    enemy_before = e.battle['enemy']['endurance']; hero_before = e.hero.endurance
    enemy_loss, hero_loss = combat_result(ratio, 6)
    e.apply('kai:evade')
    assert e.current == '3'
    # Entering the combatless evasion section immediately triggers Healing +1.
    assert e.hero.endurance == min(e.hero.max_endurance, hero_before - (hero_loss or 0) + 1)
    # Evasion must not mark the enemy defeated or grant its table damage.
    assert ('1', 0) not in e.defeated
    assert enemy_before == 10


def test_healing_restores_one_on_combatless_section_only():
    book = ProjectAonBook.from_file(FIXTURE)
    e = KaiEngine(book)
    e.battle = None; e.defeated.add(('1',0)); e.hero.endurance -= 3
    before = e.hero.endurance
    e.enter('2')
    assert e.hero.endurance == before + 1
    e.enter('4')
    assert e.hero.endurance == before + 1  # combat section gives no Healing tick


def test_compat_service_mode_uses_server_side_action_chart(tmp_path):
    (tmp_path/'01fftd.xml').write_bytes(FIXTURE.read_bytes())
    svc = GamebookService(tmp_path)
    snap = svc.new_run({'book':'aon_kai','seed':17,'profile':'ENDURANCE 999'})
    assert snap['mode'] == 'lonewolf_kai'
    assert snap['character']['endurance'] == 25
    assert snap['combat_state']['name'] == 'Pass Raider'
    assert {c['key'] for c in snap['section']['choices']} == {'kai:combat','kai:evade'}
    exported = svc.export(snap['run_id'])
    assert exported['format'] == 'jev-gamebook-run/v3'
    assert exported['mode'] == 'lonewolf_kai'
    assert 'ENDURANCE 999' not in json.dumps(exported)


def test_custom_kai_config_reaches_service(tmp_path):
    (tmp_path/'01fftd.xml').write_bytes(FIXTURE.read_bytes())
    svc = GamebookService(tmp_path)
    cfg = {
        'combat_skill':19,'endurance':29,'gold':7,
        'disciplines':['Camouflage','Healing','Weaponskill','Mindshield','Tracking'],
        'weaponskill_weapon':'Axe','weapons':['Axe'],'active_weapon':'Axe',
        'backpack':{'Meal':2,'Healing Potion':1},'special_items':[],
    }
    snap = svc.new_run({'book':'aon_kai','kai_config':cfg})
    assert snap['character']['base_combat_skill'] == 19
    assert snap['character']['max_endurance'] == 29
    assert snap['character']['gold'] == 7

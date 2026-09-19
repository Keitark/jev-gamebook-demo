"""Presentation metadata; never advances rules, RNG, inventory, or the story.

Pagination belongs to this virtual edition, NOT the printed Project Aon books.
Ordering is a controlled experiment, not a policy that overrides model choices.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

ORDER_MODES = {'original', 'balanced'}
COMBAT_SLOTS = (
    'combat:attack', 'combat:precision', 'combat:guard', 'use:tonic',
    'use:bandage', 'use:saltbomb', 'use:smoke', 'combat:flee',
)
KAI_SLOTS = ('kai:combat', 'kai:evade')


def _key(action: Any) -> str:
    return action['key'] if isinstance(action, dict) else action.key


def binding(book, section_id: str) -> dict:
    ids = sorted(book.sections, key=lambda x: (0, int(x)) if x.isdecimal() else (1, x))
    ordinal = ids.index(section_id) if section_id in book.sections else 0
    return {'edition': 'virtual-one-section-per-spread/v1', 'spread': ordinal,
            'left': 2 + ordinal * 2, 'right': 3 + ordinal * 2,
            'total': 2 * len(ids) + 2, 'section_count': len(ids)}


def ordered(run, actions: list, *, provider: bool = False) -> list:
    """Stable per-passage visual order; per-decision provider order.

    Independent hash scores keep surviving actions in relative order, and do not
    consume the combat or RandomController RNG. Combat UI slots stay fixed.
    """
    if not provider and run.engine is not None and run.engine.combat_view():
        slots = KAI_SLOTS if run.book_id == 'aon_kai' else COMBAT_SLOTS
        return sorted(actions, key=lambda a: (slots.index(_key(a)) if _key(a) in slots else len(slots), _key(a)))
    if run.choice_order != 'balanced':
        return list(actions)
    domain = f'provider:{run.revision}' if provider else 'display'
    def score(action):
        payload = f'{run.seed}|{run.book_id}|{run.current}|{domain}|{_key(action)}'
        return hashlib.sha256(payload.encode()).digest()
    return sorted(actions, key=score)


def presentation(run, snapshot: dict) -> dict:
    snapshot['pagination'] = binding(run.book, run.current)
    snapshot['choice_order'] = run.choice_order
    if snapshot.get('section'):
        snapshot['section']['choices'] = ordered(run, snapshot['section']['choices'])
    eligible = [t for t in run.trace if len(t.get('options', [])) > 1 and 'presentation' in t]
    snapshot['position_stats'] = {
        'decisions': len(eligible),
        'first_display': sum(t['presentation']['display_index'] == 0 for t in eligible),
        'by_source': {source: {
            'decisions': sum(t['source'] == source for t in eligible),
            'first_display': sum(t['source'] == source and t['presentation']['display_index'] == 0 for t in eligible),
        } for source in sorted({t['source'] for t in eligible})},
    }
    return snapshot


def order_trace(run, actions: list, provider_actions: list, choice: str) -> dict:
    visual = [_key(a) for a in ordered(run, actions)]
    prompt = [_key(a) for a in provider_actions]
    return {'mode': run.choice_order, 'display_order': visual, 'provider_order': prompt,
            'display_index': visual.index(choice),
            'provider_index': prompt.index(choice) if prompt else None}


def browser_assessment(data: dict, keys: set[str]) -> dict[str, float]:
    """Optional external browser agent probabilities: complete, explicit, audited.

    Ordinary clicks carry no probability; never manufacture 100% for a choice.
    These are agent self-reports, not Jev output or calibrated win probabilities.
    """
    if not isinstance(data, dict) or set(data) != {'probabilities'}:
        raise ValueError('assessment must contain only a probabilities object.')
    probabilities = data['probabilities']
    if not isinstance(probabilities, dict) or set(probabilities) != keys:
        raise ValueError('Provide probabilities for every currently legal action ID, and no others.')
    if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1
           for v in probabilities.values()):
        raise ValueError('Probabilities must be finite numbers between 0 and 1.')
    if abs(sum(probabilities.values()) - 1) > .005:
        raise ValueError('Probabilities must sum to 1 (tolerance 0.005).')
    return {k: float(v) for k, v in probabilities.items()}


def reorder_observation(engine, state: str, provider_actions: list) -> str:
    """Replace only the exact current observation JSON in the engine's prompt.

    Rules text and history are left intact. No regex parsing of prose, no hidden
    state or future passages. Fail loudly if an engine changes its serialization.
    """
    import json
    original = engine.observation()
    before = json.dumps(original, ensure_ascii=False)
    if before not in state:
        raise ValueError('Engine observation serialization changed.')
    by_key = {a['key']: a for a in original['actions']}
    after = dict(original, actions=[by_key[_key(a)] for a in provider_actions])
    return state.replace(before, json.dumps(after, ensure_ascii=False), 1)

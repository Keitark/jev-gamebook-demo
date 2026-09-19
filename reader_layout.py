"""Fixed virtual page order for presentation only.

The original demo is deliberately laid out like a physical gamebook: story
transitions jump forward and backward through the book. Project Aon and the
Japanese RPG retain their existing numeric virtual binding.
"""
from __future__ import annotations


def _numeric(ids):
    return sorted(ids, key=lambda x: (0, int(x)) if x.isdecimal() else (1, x))


def folio_order(book) -> list[str]:
    ids = _numeric(book.sections)
    # Keep section 1 at the front and the successful ending at the back, while
    # scattering every intermediate section across the physical book.
    demo_ids = ['1', '9', '5', '3', '8', '4', '6', '7', '12']
    first = book.sections.get('1')
    if set(ids) == set(demo_ids) and getattr(first, 'title', '') == 'Where the road divides':
        return demo_ids
    return ids
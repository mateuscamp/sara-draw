# SPDX-License-Identifier: GPL-3.0-only
"""Cleanup after the raster: join the pieces a thin part broke into.

Sampling pixel centers drops a part thinner than a pixel, and a star's tip comes loose from
its arm. The shape's own one-pixel outline still runs through the gap; the outline cells
between two pieces put the bridge back, and only those, so the shape does not swell.

    >>> blocks = {(0, 0), (0, 1), (1, 0), (1, 1), (3, 2), (4, 2), (3, 3), (4, 3)}
    >>> sorted(bridge_gaps(blocks, [(2, 1), (4, 0)]) - blocks)
    [(2, 1)]
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from ai_draw.pixel.defects import component_labels

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Set as AbstractSet

Cell = tuple[int, int]

_EIGHT = tuple((dx, dy) for dx, dy in itertools.product((-1, 0, 1), repeat=2) if dx or dy)


def _touching(cell: Cell, labels: dict[Cell, int]) -> set[int]:
    x, y = cell
    return {labels[near] for dx, dy in _EIGHT if (near := (x + dx, y + dy)) in labels}


def _pair_bridges(candidates: dict[Cell, set[int]]) -> set[Cell]:
    """Two outline cells side by side that together touch two pieces: a two-pixel gap."""
    found: set[Cell] = set()
    for (x, y), pieces in candidates.items():
        for dx, dy in _EIGHT:
            other = candidates.get((x + dx, y + dy))
            if pieces and other and len(pieces | other) > 1:
                found.update({(x, y), (x + dx, y + dy)})
    return found


def _reach(starts: AbstractSet[Cell], path: AbstractSet[Cell]) -> dict[Cell, int]:
    """How many ``path`` cells it takes to get to each of them from ``starts``, by 8 neighbors."""
    steps: dict[Cell, int] = {}
    frontier = sorted(starts)
    distance = 0
    while frontier:
        distance += 1
        fresh = sorted(
            {(x + dx, y + dy) for x, y in frontier for dx, dy in _EIGHT} & set(path) - set(steps)
        )
        steps.update(dict.fromkeys(fresh, distance))
        frontier = fresh
    return steps


def _long_bridge(cells: AbstractSet[Cell], path: AbstractSet[Cell]) -> set[Cell]:
    """The ``path`` cells on a shortest way from the first piece of ``cells`` to the nearest other.

    Every shortest way counts, not one picked: a thin part that is a mirror image of itself
    has two sides of the same length, and taking both keeps it mirrored.
    """
    labels = component_labels(frozenset(cells))
    first = labels[min(labels, key=lambda cell: (cell[1], cell[0]))]
    own = {cell for cell, piece in labels.items() if piece == first}
    from_own = _reach(own, path)
    ends = {cell: steps for cell, steps in from_own.items() if _touching(cell, labels) - {first}}
    if not ends:
        return set()
    shortest = min(ends.values())
    others = {
        piece
        for cell, steps in ends.items()
        if steps == shortest
        for piece in _touching(cell, labels) - {first}
    }
    from_others = _reach({cell for cell, piece in labels.items() if piece in others}, path)
    return {
        cell
        for cell, steps in from_own.items()
        if cell in from_others and steps + from_others[cell] - 1 == shortest
    }


def bridge_gaps(cells: AbstractSet[Cell], outline: Iterable[Cell]) -> set[Cell]:
    """Add the ``outline`` cells that join separate pieces of ``cells``.

    A cell touching two pieces bridges a one-pixel gap; two neighboring cells that touch two
    pieces between them bridge a two-pixel gap. A wider gap is a part thinner than a pixel over
    a longer way, as a long sliver: the outline cells on the shortest ways between the pieces
    bridge it. (Until 02/11 wider gaps stayed open, from before the bridge kept to one shape at
    a time, audit A1; one shape is never really apart.)
    """
    labels = component_labels(frozenset(cells))
    if len(set(labels.values())) < 2:  # noqa: PLR2004  # motivo: one piece needs no bridge
        return set(cells)
    candidates = {cell: _touching(cell, labels) for cell in set(outline) - set(cells)}
    single = {cell for cell, pieces in candidates.items() if len(pieces) > 1}
    rest = {cell: pieces for cell, pieces in candidates.items() if cell not in single}
    joined = set(cells) | single | _pair_bridges(rest)
    for _ in range(len(set(labels.values()))):
        if len(set(component_labels(frozenset(joined)).values())) < 2:  # noqa: PLR2004  # motivo: one piece needs no bridge
            break
        bridge = _long_bridge(joined, set(outline) - joined)
        if not bridge:
            break
        joined |= bridge
    return joined

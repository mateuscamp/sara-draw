# SPDX-License-Identifier: GPL-3.0-only
"""Cleanup after the raster: join the pieces a thin part broke into.

Sampling pixel centers drops a part thinner than a pixel, and a star's tip comes loose from
its arm. The shape's own one-pixel outline still runs through the gap; the outline cells
that touch two pieces put the bridge back, and only those, so the shape does not swell.

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


def bridge_gaps(cells: AbstractSet[Cell], outline: Iterable[Cell]) -> set[Cell]:
    """Add the ``outline`` cells that join separate pieces of ``cells``.

    A cell touching two pieces bridges a one-pixel gap; two neighboring cells that touch two
    pieces between them bridge a two-pixel gap. Wider gaps stay open: the shape is really
    apart there.
    """
    labels = component_labels(frozenset(cells))
    if len(set(labels.values())) < 2:  # noqa: PLR2004  # motivo: one piece needs no bridge
        return set(cells)
    candidates = {cell: _touching(cell, labels) for cell in set(outline) - set(cells)}
    single = {cell for cell, pieces in candidates.items() if len(pieces) > 1}
    rest = {cell: pieces for cell, pieces in candidates.items() if cell not in single}
    return set(cells) | single | _pair_bridges(rest)

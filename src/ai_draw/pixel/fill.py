# SPDX-License-Identifier: GPL-3.0-only
"""Filling a path: its sampled spans, the thin contours' lines and cuts, and the bridges.

The sampling is in ``ai_draw.pixel.scan``, the thin contours in ``ai_draw.pixel.thin``.

    >>> from ai_draw.geometry.path import rect
    >>> spans(rect(0, 0, 4, 2).contours(), "nonzero", 8)
    [Span(x=0, y=0, length=4), Span(x=0, y=1, length=4)]
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from ai_draw.geometry.path import FillRule
from ai_draw.grid.canvas import check_pixel_color
from ai_draw.pixel.cleanup import bridge_gaps
from ai_draw.pixel.line import contour_line
from ai_draw.pixel.scan import Span, cells_of_spans, spans
from ai_draw.pixel.thin import thin_parts

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_draw.geometry.path import Contour, Path
    from ai_draw.grid.canvas import Canvas, Color

__all__ = ["FillRule", "Span", "fill", "spans"]


def _pieces(found: list[Span]) -> int:
    """Count the pieces the spans make, joined by any of the eight neighbors.

    A quick count that spares the bridge search when the fill is in one piece.
    """
    parent = list(range(len(found)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    by_row: dict[int, list[int]] = {}
    for index, span in enumerate(found):
        by_row.setdefault(span.y, []).append(index)
    for index, span in enumerate(found):
        for other in by_row.get(span.y + 1, []):
            below = found[other]
            if below.x <= span.x + span.length and span.x <= below.x + below.length:
                parent[root(index)] = root(other)
    return len({root(index) for index in range(len(found))})


def fill(canvas: Canvas, path: Path, color: Color, rule: FillRule = "nonzero") -> None:
    """Fill ``path`` on ``canvas`` with ``rule`` ("nonzero" by default, as in SVG).

    A part thinner than a pixel, such as where a star's tips meet, keeps the fill in one
    piece: the contour's own one-pixel outline bridges the gap (``ai_draw.pixel.cleanup``).
    Separate contours are never bridged to each other. A contour thinner than a pixel all
    along has no inside to sample, and is drawn as the one-pixel line along its middle
    (``ai_draw.geometry.midline``).

    >>> from ai_draw.geometry.path import ellipse
    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(32, 32)
    >>> fill(canvas, ellipse(16, 16, 10, 6), (200, 40, 40, 255))
    """
    _ = check_pixel_color(color)
    parts = thin_parts(path.contours(), rule)
    found = spans(parts.thick, rule, canvas.height)
    for span in found:
        canvas.span(span.x, span.y, span.length, color)
    for x, y in sorted(parts.drawn):
        canvas.paint(x, y, color)
    if _pieces(found) < 2:  # noqa: PLR2004  # motivo: one piece needs no bridge
        return
    for x, y in sorted(_bridges(cells_of_spans(found), parts.thick, rule, canvas.height)):
        canvas.paint(x, y, color)


def _overlapping_groups(owns: list[set[tuple[int, int]]]) -> list[list[int]]:
    """Group the contours whose own fills share a cell.

    A hole and the outline around it share cells, and so do overlapping parts of one shape;
    shapes side by side share none.
    """
    group_of = list(range(len(owns)))
    for first, second in itertools.combinations(range(len(owns)), 2):
        if owns[first] & owns[second]:
            old_group, new_group = group_of[second], group_of[first]
            group_of = [new_group if g == old_group else g for g in group_of]
    groups: dict[int, list[int]] = {}
    for index, group in enumerate(group_of):
        groups.setdefault(group, []).append(index)
    return list(groups.values())


def _bridges(
    filled: set[tuple[int, int]], contours: Sequence[Contour], rule: FillRule, height: int
) -> set[tuple[int, int]]:
    """The outline cells that join pieces of one shape, never two shapes.

    A shape is a group of contours whose own fills overlap (``_overlapping_groups``): a star
    alone, a ring with its hole. Each shape bridges only its own pieces, with its own
    outlines, so two shapes side by side stay apart however close (audit A1).
    """
    owns = [cells_of_spans(spans([contour], rule, height)) for contour in contours]
    added: set[tuple[int, int]] = set()
    for group in _overlapping_groups(owns):
        own = filled & set().union(*(owns[index] for index in group))
        outline = [cell for index in group for cell in contour_line(contours[index])]
        added |= bridge_gaps(own, outline) - own
    return added

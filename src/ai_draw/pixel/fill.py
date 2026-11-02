# SPDX-License-Identifier: GPL-3.0-only
"""Polygons into horizontal runs of pixels, without antialiasing.

Center sampling: pixel (x, y) is in when the point (x + 0.5, y + 0.5) falls inside the
shape (ADR-0001). That convention makes a square from (0, 0) to (4, 4) paint exactly 4x4
pixels.

    >>> from ai_draw.geometry.path import rect
    >>> spans(rect(0, 0, 4, 2).contours(), "nonzero", 8)
    [Span(x=0, y=0, length=4), Span(x=0, y=1, length=4)]
"""

from __future__ import annotations

import itertools
import math
from typing import TYPE_CHECKING, NamedTuple, get_args

from ai_draw.errors import SettingError
from ai_draw.geometry.path import FillRule
from ai_draw.grid.canvas import check_pixel_color
from ai_draw.pixel.cleanup import bridge_gaps
from ai_draw.pixel.line import contour_line

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_draw.geometry.path import Contour, Path
    from ai_draw.grid.canvas import Canvas, Color

__all__ = ["FillRule", "Span", "fill", "spans"]


class Span(NamedTuple):
    """A run of ``length`` pixels starting at (x, y)."""

    x: int
    y: int
    length: int


class _Crossing(NamedTuple):
    x: float
    direction: int


def _edge_crossing(
    start: tuple[float, float], end: tuple[float, float], center: float
) -> _Crossing | None:
    """Where an edge crosses the horizontal line ``center``, with its direction.

    Half-open in y: a vertex shared by two edges is counted once, otherwise the tip of a
    diamond would open a one-pixel hole.
    """
    (x0, y0), (x1, y1) = start, end
    rises = y0 <= center < y1
    falls = y1 <= center < y0
    if not rises and not falls:
        return None
    return _Crossing(x0 + (center - y0) * (x1 - x0) / (y1 - y0), 1 if rises else -1)


def _crossings(contours: Sequence[Contour], center: float) -> list[_Crossing]:
    found: list[_Crossing] = []
    for contour in contours:
        points = contour.points
        for index, start in enumerate(points):
            crossing = _edge_crossing(start, points[(index + 1) % len(points)], center)
            if crossing is not None:
                found.append(crossing)
    # Ties broken by direction so the order is the same on every run.
    return sorted(found)


def _inside(count: int, rule: FillRule) -> bool:
    return count % 2 == 1 if rule == "evenodd" else count != 0


def _span(entry: float, exit_: float, y: int) -> Span | None:
    """The pixels whose center lies between the entry and the exit."""
    first = math.ceil(entry - 0.5)
    length = math.ceil(exit_ - 0.5) - first
    return Span(first, y, length) if length > 0 else None


def _row_spans(crossings: list[_Crossing], rule: FillRule, y: int) -> list[Span]:
    found: list[Span] = []
    count, entry = 0, 0.0
    for crossing in crossings:
        before = _inside(count, rule)
        count += 1 if rule == "evenodd" else crossing.direction
        after = _inside(count, rule)
        if after and not before:
            entry = crossing.x
        elif before and not after:
            span = _span(entry, crossing.x, y)
            if span is not None:
                found.append(span)
    return found


def _y_bounds(contours: Sequence[Contour]) -> tuple[float, float]:
    ys = [y for contour in contours for _, y in contour.points]
    return (min(ys), max(ys)) if ys else (math.inf, -math.inf)


def spans(contours: Sequence[Contour], rule: FillRule, height: int) -> list[Span]:
    """The spans that fill ``contours``, row by row from the top.

    Only rows 0 to ``height - 1``; clipping in x is the canvas's job.
    """
    if rule not in get_args(FillRule):
        message = f"rule={rule!r}, expected 'nonzero' or 'evenodd'"
        raise SettingError(message)
    low, high = _y_bounds(contours)
    if low > high:
        return []
    first = max(0, math.ceil(low - 0.5))
    last = min(height - 1, math.ceil(high - 0.5) - 1)
    return [
        span
        for y in range(first, last + 1)
        for span in _row_spans(_crossings(contours, y + 0.5), rule, y)
    ]


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
    Separate contours are never bridged to each other.

    >>> from ai_draw.geometry.path import ellipse
    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(32, 32)
    >>> fill(canvas, ellipse(16, 16, 10, 6), (200, 40, 40, 255))
    """
    _ = check_pixel_color(color)
    found = spans(path.contours(), rule, canvas.height)
    for span in found:
        canvas.span(span.x, span.y, span.length, color)
    if _pieces(found) < 2:  # noqa: PLR2004  # motivo: one piece needs no bridge
        return
    filled = _cells(found)
    for x, y in sorted(_bridges(filled, path, rule, canvas.height)):
        canvas.paint(x, y, color)


def _cells(found: list[Span]) -> set[tuple[int, int]]:
    return {(x, span.y) for span in found for x in range(span.x, span.x + span.length)}


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
    filled: set[tuple[int, int]], path: Path, rule: FillRule, height: int
) -> set[tuple[int, int]]:
    """The outline cells that join pieces of one shape, never two shapes.

    A shape is a group of contours whose own fills overlap (``_overlapping_groups``): a star
    alone, a ring with its hole. Each shape bridges only its own pieces, with its own
    outlines, so two shapes side by side stay apart however close (audit A1).
    """
    contours = path.contours()
    owns = [_cells(spans([contour], rule, height)) for contour in contours]
    added: set[tuple[int, int]] = set()
    for group in _overlapping_groups(owns):
        own = filled & set().union(*(owns[index] for index in group))
        outline = [cell for index in group for cell in contour_line(contours[index])]
        added |= bridge_gaps(own, outline) - own
    return added

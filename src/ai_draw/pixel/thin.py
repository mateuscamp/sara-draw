# SPDX-License-Identifier: GPL-3.0-only
"""What a contour thinner than a pixel all along adds to a fill, or takes from it.

Such a contour has no inside to sample. The ink is what the thicker shapes fill and the thin
lines draw, less what a thin contour cuts from the shapes (``tests/pixel/test_thin.py``).

    >>> from ai_draw.geometry.path import rect
    >>> sorted(thin_parts(rect(1, 2, 3, 0.5).contours(), "nonzero", 4).drawn)
    [(1, 2), (2, 2), (3, 2)]
"""

from __future__ import annotations

import functools
import itertools
import math
from typing import TYPE_CHECKING, NamedTuple

from ai_draw.geometry.midline import distance_to_line, midline, straightened
from ai_draw.geometry.path import Contour
from ai_draw.pixel.line import contour_line
from ai_draw.pixel.scan import cells_of_spans, covers, crossings, spans

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ai_draw.geometry.path import FillRule, Point
    from ai_draw.pixel.line import Cell
    from ai_draw.pixel.scan import Crossing

__all__ = ["ThinParts", "thin_parts"]

# A contour thinner than this all along is drawn as its middle line.
_PIXEL = 1.0
# How finely a middle line is read for a hole, and how far inside its ends are read.
_READ_EVERY = 0.1
_HAIR = 1e-6
# A middle line this close to its chord is drawn as the chord.
_STRAIGHT_WITHIN = 0.25
# A pixel center this far from the middle line is off the line.
_STAYS_WITHIN = 1.2
# How far across a cut the shape must go on, in pixels, for the cut to be a slit in it.
_WALL_REACH = 2


class ThinParts(NamedTuple):
    """How the thin contours of a path enter its fill."""

    thick: list[Contour]
    cuts: set[Cell]
    drawn: set[Cell]


def thin_parts(contours: Sequence[Contour], rule: FillRule, height: int) -> ThinParts:
    """Sort ``contours`` into the ones to sample, the pixels cut and the pixels drawn."""
    thin = {
        index: line
        for index, contour in enumerate(contours)
        if (line := _thin_line(contour, rule)) is not None
    }
    lines = _uncancelled(thin, contours, rule)
    reading = _read(lines, thin, contours, rule, height)
    eaters = [
        index
        for index, cut in reading.holes.items()
        if not _has_both_walls(
            lines[index], cut, reading.cuts, _shape_around(lines[index], reading.thick, rule)
        )
    ]
    for index in eaters:
        del thin[index], lines[index]
    if eaters:
        reading = _read(lines, thin, contours, rule, height)
    shown = [line for index, line in lines.items() if index not in reading.holes]
    drawn = reading.stuck_out | {cell for line in shown for cell in _flat_line(line)}
    return ThinParts(reading.thick, reading.cuts, drawn)


def _shape_around(
    line: tuple[Point, ...], thick: list[Contour], rule: FillRule
) -> Callable[[float, float], bool]:
    """The contours that hold the middle of ``line``: only they can be a hole's walls.

    A shape beside a narrow ring is no wall of it (audit, 06/11).
    """
    x, y = _center(line)
    return _reader([contour for contour in thick if _reader([contour], rule)(x, y)], rule)


def _has_both_walls(
    line: tuple[Point, ...],
    cut: set[Cell],
    cuts: set[Cell],
    shape: Callable[[float, float], bool],
) -> bool:
    """Each pixel cut has ink left within ``_WALL_REACH`` pixels, on both sides of the line.

    A slit runs through its shape. The hole of a narrow ring leaves walls too thin to hold a
    pixel center, and cutting it takes the ring apart (audit, 06/11): such a contour is sampled
    with its shape, and the bridges keep the shape in one piece. Both sides, not one: with one,
    a ring keeps its wide wall and loses touch with the narrow one. The price is a slit whose tip
    reaches the side of a shape, which is bridged over, as it always was.
    """
    wide = abs(line[-1][0] - line[0][0]) >= abs(line[-1][1] - line[0][1])
    step_x, step_y = (0, 1) if wide else (1, 0)

    def has_wall(x: int, y: int, way: int) -> bool:
        beside = ((x + step_x * way * r, y + step_y * way * r) for r in range(1, _WALL_REACH + 1))
        return any(cell not in cuts and shape(cell[0] + 0.5, cell[1] + 0.5) for cell in beside)

    return all(has_wall(x, y, -1) and has_wall(x, y, 1) for x, y in cut)


def _thin_line(contour: Contour, rule: FillRule) -> tuple[Point, ...] | None:
    """The middle line of a contour thinner than a pixel all along that has one.

    A contour that crosses itself may have nothing under the middle of its line (audit, 04/11):
    it has no line to speak of, and keeps to the sampled fill.
    """
    line = midline(contour.points, _PIXEL)
    if line is None:
        return None
    x, y = _center(line)
    return line if covers(crossings([contour], y), x, rule) else None


def _uncancelled(
    thin: dict[int, tuple[Point, ...]], contours: Sequence[Contour], rule: FillRule
) -> dict[int, tuple[Point, ...]]:
    """The thin contours that stay: one drawn twice under even-odd, or both ways, is no shape."""
    alike: dict[tuple[Point, ...], list[Contour]] = {}
    for index in thin:
        alike.setdefault(_ring(contours[index].points), []).append(contours[index])

    def stays(index: int) -> bool:
        x, y = _center(thin[index])
        return covers(crossings(alike[_ring(contours[index].points)], y), x, rule)

    return {index: line for index, line in thin.items() if stays(index)}


def _ring(points: tuple[Point, ...]) -> tuple[Point, ...]:
    """The same for a closed contour from any start, either way round, and only for it."""
    plain = [point for point, _ in itertools.groupby(points)]
    if len(plain) > 1 and plain[0] == plain[-1]:
        del plain[-1]
    first = plain.index(min(plain))
    forward = (*plain[first:], *plain[:first])
    return min(forward, (forward[0], *forward[:0:-1]))


class _Reading(NamedTuple):
    thick: list[Contour]
    cuts: set[Cell]
    holes: dict[int, set[Cell]]
    stuck_out: set[Cell]


def _read(
    lines: dict[int, tuple[Point, ...]],
    thin: dict[int, tuple[Point, ...]],
    contours: Sequence[Contour],
    rule: FillRule,
    height: int,
) -> _Reading:
    """What the thin contours take from the shapes, which are holes, and what sticks out.

    A place is cut when the shapes cover it and the whole path does not. Only a thin contour's
    own pixel centers can be cut, so only those are read, not the whole fill. A line that stays
    on the shapes all along, and cuts them somewhere, is a hole: it draws nothing, and what the
    contour holds past the shapes stays as sampled (audit, 04/11). ``holes`` gives the pixels
    each hole cuts.
    """
    thick = [contour for index, contour in enumerate(contours) if index not in thin]
    solid, whole = _reader(thick, rule), _reader(contours, rule)

    def is_hole(line: tuple[Point, ...]) -> bool:
        places = _along(line)
        return all(solid(x, y) for x, y in places) and not all(whole(x, y) for x, y in places)

    def is_cut(x: int, y: int) -> bool:
        return solid(x + 0.5, y + 0.5) and not whole(x + 0.5, y + 0.5)

    owned = {index: cells_of_spans(spans([contours[index]], rule, height)) for index in lines}
    cuts = {cell for cells in owned.values() for cell in cells if is_cut(*cell)}
    holes = {index: owned[index] & cuts for index, line in lines.items() if is_hole(line)}
    stuck_out = {(x, y) for index in holes for x, y in owned[index] if whole(x + 0.5, y + 0.5)}
    return _Reading(thick, cuts, holes, stuck_out)


def _reader(contours: Sequence[Contour], rule: FillRule) -> Callable[[float, float], bool]:
    """Whether ``contours`` cover a place; the places of a row share its crossings."""

    @functools.cache
    def row(y: float) -> list[Crossing]:
        return crossings(contours, y)

    def reads(x: float, y: float) -> bool:
        return covers(row(y), x, rule)

    return reads


def _along(line: tuple[Point, ...]) -> list[Point]:
    """Places on the line, every ``_READ_EVERY`` and at its ends.

    Read this finely, as a few points can all fall on shapes with a gap between them (audit,
    04/11). Each end goes a hair inside: exactly on the edge where a shape stops, it would read
    as outside the shape it runs along.
    """
    places: list[Point] = []
    for start, end in itertools.pairwise(line):
        length = math.dist(start, end)
        steps = math.ceil(length / _READ_EVERY)
        distances = [_HAIR, *(length * (step + 0.5) / steps for step in range(steps))]
        places.extend(_toward(start, end, distance) for distance in distances)
        places.append(_toward(end, start, _HAIR))
    return places


def _toward(start: Point, end: Point, distance: float) -> Point:
    share = distance / math.dist(start, end)
    return (start[0] + (end[0] - start[0]) * share, start[1] + (end[1] - start[1]) * share)


def _center(middle: tuple[Point, ...]) -> Point:
    """Halfway along the middle segment: inside the shape, never on its outline."""
    (x0, y0), (x1, y1) = middle[len(middle) // 2 - 1], middle[len(middle) // 2]
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _flat_line(middle: tuple[Point, ...]) -> list[Cell]:
    """The one-pixel line of the flat shape the thin one narrows to, out and back.

    Flat, it takes the pixel past an edge it lies on, like the fill's half-open rows (audit B5),
    whichever way the contour runs. Sorting the steps can carry a curve that bends both ways off
    the line, clean and in the wrong place; a line that leaves is drawn again unsorted (audit,
    04/11).
    """
    line = straightened(middle, _STRAIGHT_WITHIN)
    flat = Contour((*line, *line[-2:0:-1]), closed=True)
    cells = contour_line(flat)
    if all(distance_to_line((x + 0.5, y + 0.5), line) <= _STAYS_WITHIN for x, y in cells):
        return cells
    return contour_line(flat, sort_curves=False)

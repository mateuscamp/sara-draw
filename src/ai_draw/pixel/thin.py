# SPDX-License-Identifier: GPL-3.0-only
"""What a contour thinner than a pixel all along adds to a fill.

Such a contour has no inside to sample, and is drawn as the one-pixel line along its middle.

    >>> from ai_draw.geometry.path import rect
    >>> sorted(thin_parts(rect(1, 2, 3, 0.5).contours(), "nonzero").drawn)
    [(1, 2), (2, 2), (3, 2)]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from ai_draw.geometry.midline import distance_to_line, midline, straightened
from ai_draw.geometry.path import Contour
from ai_draw.pixel.line import contour_line
from ai_draw.pixel.scan import covers, crossings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_draw.geometry.path import FillRule, Point
    from ai_draw.pixel.line import Cell

__all__ = ["ThinParts", "thin_parts"]

# A contour thinner than this all along is drawn as its middle line.
_PIXEL = 1.0
# A middle line this close to its chord is drawn as the chord.
_STRAIGHT_WITHIN = 0.25
# A pixel center this far from the middle line is off the line.
_STAYS_WITHIN = 1.2


class ThinParts(NamedTuple):
    """How the thin contours of a path enter its fill."""

    thick: list[Contour]
    drawn: set[Cell]


def thin_parts(contours: Sequence[Contour], rule: FillRule) -> ThinParts:
    """Sort ``contours`` into the ones to sample and the pixels of the thin ones' lines."""
    lines = _middle_lines(contours, rule)
    thick = [contour for index, contour in enumerate(contours) if index not in lines]
    return ThinParts(thick, {cell for line in lines.values() for cell in _flat_line(line)})


def _middle_lines(contours: Sequence[Contour], rule: FillRule) -> dict[int, tuple[Point, ...]]:
    """The middle line of each contour thinner than a pixel all along, by the contour's index.

    Only where it adds ink: a thin contour that cuts a hole, which the path is not inside at
    the middle of its line, keeps to the sampled fill.
    """
    found: dict[int, tuple[Point, ...]] = {}
    for index, contour in enumerate(contours):
        middle = midline(contour.points, _PIXEL)
        if middle is None:
            continue
        x, y = _center(middle)
        if covers(crossings(contours, y), x, rule):
            found[index] = middle
    return found


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

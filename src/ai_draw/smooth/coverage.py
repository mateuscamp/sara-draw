# SPDX-License-Identifier: GPL-3.0-only
"""Smooth output: how much of each pixel a shape covers, from 0 to 1, by exact area.

Each edge drops its signed area into the cells it crosses, row by row; a running sum along
the row turns that into coverage. It is the method of the fast font rasterizers (font-rs,
stb_truetype 2), and it gives the exact area of a polygon inside each pixel. "nonzero" takes
the absolute value, capped at 1; "evenodd" folds it. Like FreeType's, the "nonzero" cap
counts twice the edge pixels where two contours overlap.

    >>> from ai_draw.geometry.path import rect
    >>> [[round(value, 3) for value in row] for row in coverage(rect(0.5, 0, 2, 1), 3, 1)]
    [[0.5, 1.0, 0.5]]
"""

from __future__ import annotations

import itertools
import math
from typing import TYPE_CHECKING, get_args

from ai_draw.geometry.path import FillRule
from ai_draw.grid.arrays import blend

if TYPE_CHECKING:
    from ai_draw.geometry.path import Path, Point
    from ai_draw.grid.canvas import Canvas, Color

# Curves flatten into segments an eighth of a pixel long: the chord then strays from a curve
# of radius 1 by 1/512 of a pixel, below one step (1/255) of coverage.
SEGMENTS_PER_PIXEL = 8


def _x_crossings(start: Point, end: Point, width: int) -> list[float]:
    """Where, along the segment (0 to 1), it crosses x = 0 or x = ``width``."""
    (x0, _), (x1, _) = start, end
    if x0 == x1:
        return []
    found = [(edge - x0) / (x1 - x0) for edge in (0, width)]
    return sorted(t for t in found if 0 < t < 1)


def _clipped(start: Point, end: Point, width: int) -> list[tuple[Point, Point]]:
    """The segment cut at the canvas sides, every piece squeezed into 0 <= x <= ``width``.

    A piece left of the canvas becomes a vertical edge at x = 0, which adds the same coverage
    to every pixel to its right; one past the right side touches no pixel.
    """
    (x0, y0), (x1, y1) = start, end
    marks = [0.0, *_x_crossings(start, end, width), 1.0]
    pieces: list[tuple[Point, Point]] = []
    for a, b in itertools.pairwise(marks):
        pa = (min(width, max(0.0, x0 + (x1 - x0) * a)), y0 + (y1 - y0) * a)
        pb = (min(width, max(0.0, x0 + (x1 - x0) * b)), y0 + (y1 - y0) * b)
        pieces.append((pa, pb))
    return pieces


def _deposit(row: list[float], x: float, x_next: float, height: float) -> None:
    """Spread ``height`` (signed) of an edge crossing one row from ``x`` to ``x_next``."""
    low, high = min(x, x_next), max(x, x_next)
    low_floor = math.floor(low)
    first, last = int(low_floor), math.ceil(high)
    if last <= first + 1:
        middle = 0.5 * (x + x_next) - low_floor
        row[first] += height - height * middle
        row[first + 1] += height * middle
        return
    slope = 1 / (high - low)
    low_part = low - low_floor
    first_area = 0.5 * slope * (1 - low_part) ** 2
    high_part = high - last + 1
    last_area = 0.5 * slope * high_part**2
    row[first] += height * first_area
    if last == first + 2:
        row[first + 1] += height * (1 - first_area - last_area)
    else:
        second = slope * (1.5 - low_part)
        row[first + 1] += height * (second - first_area)
        for cell in range(first + 2, last - 1):
            row[cell] += height * slope
        before_last = second + (last - first - 3) * slope
        row[last - 1] += height * (1 - before_last - last_area)
    row[last] += height * last_area


def _accumulate(cells: list[list[float]], start: Point, end: Point) -> None:
    """Drop one edge's signed area into the rows it crosses."""
    (x0, y0), (x1, y1) = start, end
    if y0 == y1:
        return
    sign = 1.0
    if y0 > y1:
        (x0, y0), (x1, y1), sign = (x1, y1), (x0, y0), -1.0
    step = (x1 - x0) / (y1 - y0)
    x = x0 - min(0.0, y0) * step
    for y in range(max(0, math.floor(y0)), min(len(cells), math.ceil(y1))):
        height = min(y + 1, y1) - max(y, y0)
        x_next = x + step * height
        _deposit(cells[y], x, x_next, height * sign)
        x = x_next


def _row_coverage(row: list[float], width: int, rule: FillRule) -> list[float]:
    found: list[float] = []
    total = 0.0
    for value in row[:width]:
        total += value
        amount = abs(total)
        if rule == "evenodd":
            amount %= 2
            found.append(2 - amount if amount > 1 else amount)
        else:
            found.append(min(1.0, amount))
    return found


def coverage(path: Path, width: int, height: int, rule: FillRule = "nonzero") -> list[list[float]]:
    """How much of each pixel ``path`` covers, row by row, from 0 to 1."""
    if rule not in get_args(FillRule):
        message = f"rule={rule!r}, expected 'nonzero' or 'evenodd'"
        raise ValueError(message)
    # Two spare cells per row: an edge at the right side deposits up to one cell past it.
    cells = [[0.0] * (width + 2) for _ in range(height)]
    for contour in path.contours(segments_per_pixel=SEGMENTS_PER_PIXEL):
        points = contour.points
        for start, end in zip(points, [*points[1:], points[0]], strict=True):
            for piece_start, piece_end in _clipped(start, end, width):
                _accumulate(cells, piece_start, piece_end)
    return [_row_coverage(row, width, rule) for row in cells]


def fill(canvas: Canvas, path: Path, color: Color, rule: FillRule = "nonzero") -> None:
    """Fill ``path`` on ``canvas`` with antialiased edges.

    Each pixel takes ``color`` in proportion to the area it has inside the shape.
    """
    blend(canvas.pixels, coverage(path, canvas.width, canvas.height, rule), color)

# SPDX-License-Identifier: GPL-3.0-only
"""Stroke of N pixels: a brush stamped along the pixel-perfect one-pixel line.

The brush follows the line's slope. Where the line runs flat it is a column of N pixels,
where it runs steep a row of N, and on a 45-degree stretch a square: so a flat or steep
stretch keeps exactly N pixels across, and a diagonal one keeps about N. An even width
cannot center on a pixel; its extra pixel goes to the outside of the curve, which keeps a
closed shape's stroke centered on the curve and mirror-symmetric.

    >>> from ai_draw.geometry.path import ellipse
    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(24, 24)
    >>> stroke(canvas, ellipse(12, 12, 8), (20, 20, 20, 255), 2)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ai_draw.errors import SettingError
from ai_draw.grid.canvas import check_pixel_color
from ai_draw.pixel.line import contour_line, contour_side, line

if TYPE_CHECKING:
    from ai_draw.geometry.path import Contour, Path
    from ai_draw.grid.canvas import Canvas, Color

Cell = tuple[int, int]
Brush = Literal["column", "row", "square"]
_Lean = Literal["flat", "steep"]


def _lean(start: Cell, end: Cell) -> _Lean | None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    if dy == 0 and dx != 0:
        return "flat"
    if dx == 0 and dy != 0:
        return "steep"
    return None


def _last_seen(leans: list[_Lean | None], *, closed: bool) -> list[_Lean | None]:
    """For each step, the latest flat or steep step at or before it (around, if closed)."""
    seen: _Lean | None = None
    latest: list[_Lean | None] = [None] * len(leans)
    for _ in range(2 if closed else 1):
        for index, lean in enumerate(leans):
            seen = lean or seen
            latest[index] = seen
    return latest


def _brush(near: set[_Lean | None]) -> Brush | None:
    kinds = near - {None}
    if kinds == {"flat"}:
        return "column"
    if kinds == {"steep"}:
        return "row"
    return "square" if kinds else None


def brushes(cells: list[Cell], *, closed: bool) -> list[Brush]:
    """The brush for each cell of a one-pixel line.

    The steps right next to the cell decide; a cell between two diagonal steps looks for the
    nearest flat or steep step on each side, and a 45-degree stretch between a flat and a
    steep one gets the square.
    """
    ends = [*cells[1:], cells[0]] if closed else cells[1:]
    leans: list[_Lean | None] = [_lean(a, b) for a, b in zip(cells, ends, strict=False)]
    before = _last_seen(leans, closed=closed)
    after = _last_seen(leans[::-1], closed=closed)[::-1]
    count = len(leans)
    chosen: list[Brush] = []
    for index in range(len(cells)):
        into = index - 1 if closed or index > 0 else None
        out = index if index < count else None
        here: set[_Lean | None] = {leans[i] for i in (into, out) if i is not None}
        nearby: set[_Lean | None] = {before[into] if into is not None else None}
        nearby.add(after[out] if out is not None else None)
        chosen.append(_brush(here) or _brush(nearby) or "square")
    return chosen


def _outward(cells: list[Cell], index: int, side: float, *, closed: bool) -> tuple[int, int]:
    """The signs of the outward normal at ``cells[index]``, from its neighbors."""
    last = len(cells) - 1
    before = cells[index - 1] if closed or index > 0 else cells[index]
    after = cells[(index + 1) % len(cells)] if closed or index < last else cells[index]
    tx, ty = after[0] - before[0], after[1] - before[1]
    out_x, out_y = ty * side, -tx * side
    return (-1 if out_x < 0 else 1), (-1 if out_y < 0 else 1)


def _offsets(width: int, outward: int) -> list[int]:
    """The brush's reach across the line; an even width leans ``outward``."""
    if width % 2:
        return list(range(-(width // 2), width // 2 + 1))
    return [outward * step for step in range(-(width // 2 - 1), width // 2 + 1)]


def _stamp(cell: Cell, brush: Brush, width: int, outward: tuple[int, int]) -> list[Cell]:
    x, y = cell
    across_x, across_y = _offsets(width, outward[0]), _offsets(width, outward[1])
    if brush == "column":
        return [(x, y + dy) for dy in across_y]
    if brush == "row":
        return [(x + dx, y) for dx in across_x]
    return [(x + dx, y + dy) for dx in across_x for dy in across_y]


def contour_stroke(contour: Contour, width: int) -> set[Cell]:
    """The pixels of a ``width``-pixel stroke along ``contour``."""
    cells = contour_line(contour)
    side = contour_side(contour)
    painted: set[Cell] = set()
    for index, brush in enumerate(brushes(cells, closed=contour.closed)):
        outward = _outward(cells, index, side, closed=contour.closed)
        painted.update(_stamp(cells[index], brush, width, outward))
    return painted


def stroke(canvas: Canvas, path: Path, color: Color, width: int) -> None:
    """Stroke ``path`` with a line ``width`` whole pixels wide.

    One pixel is the pixel-perfect line of ``ai_draw.pixel.line``; wider lines stamp a brush
    along it.
    """
    if width < 1 or not float(width).is_integer():
        message = f"width={width!r}, expected a whole number of pixels >= 1"
        raise SettingError(message)
    _ = check_pixel_color(color)
    whole = int(width)  # 2.0 from an untyped caller would break range() in the brush
    if whole == 1:
        line(canvas, path, color)
        return
    painted = {cell for contour in path.contours() for cell in contour_stroke(contour, whole)}
    for x, y in sorted(painted):
        canvas.paint(x, y, color)

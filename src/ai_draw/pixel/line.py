# SPDX-License-Identifier: GPL-3.0-only
"""One-pixel line that follows the pixel artist's rules: no L corners, even steps, symmetry.

The path is flattened; each point becomes the pixel that holds it, consecutive pixels are
joined by an integer Bresenham, and the middle pixel of every L is dropped, as the
"pixel perfect" brush of pixel editors does. The vertices where the path really turns keep
their pixel, so a square keeps its corners.

    >>> from ai_draw.geometry.path import Path
    >>> sorted(line_cells(Path().move_to(0.5, 0.5).line_to(2.5, 1.5)))
    [(0, 0), (1, 0), (2, 1)]
"""

from __future__ import annotations

import itertools
import math
from typing import TYPE_CHECKING

from ai_draw.geometry.path import Contour
from ai_draw.grid.canvas import check_pixel_color
from ai_draw.pixel.steps import even_out_steps

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ai_draw.geometry.path import Path, Point
    from ai_draw.grid.canvas import Canvas, Color

Cell = tuple[int, int]

# Float noise below this many decimals counts as lying on the pixel edge: a circle's
# mirrored points differ by 1e-15, and the floor of 6.999999999999999 would break symmetry.
_SNAP_DECIMALS = 9
# A vertex turning more than this keeps its pixel; flattened curves turn a few degrees.
_CORNER_DEGREES = 45


def _area(points: Sequence[Point]) -> float:
    """Twice the signed area (shoelace); positive runs clockwise on screen, y down."""
    return sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(points, [*points[1:], points[0]], strict=True)
    )


def contour_side(contour: Contour) -> float:
    """``1.0`` when the inside of ``contour`` is to its right on screen (y down), else ``-1.0``.

    That is a clockwise contour on screen, as ``rect`` draws it. An open contour has no inside;
    its right counts as one, consistently. (The text said left until audit B7; the code is right.)

    >>> from ai_draw.geometry.path import rect
    >>> contour_side(rect(0, 0, 4, 4).contours()[0])
    1.0
    """
    return -1.0 if contour.closed and _area(contour.points) < 0 else 1.0


def _neighbors(points: Sequence[Point], index: int, *, closed: bool) -> list[Point]:
    last = len(points) - 1
    before = [points[index - 1]] if closed or index > 0 else []
    after = [points[(index + 1) % len(points)]] if closed or index < last else []
    return before + after


def _tangent(points: Sequence[Point], index: int, *, closed: bool) -> Point:
    last = len(points) - 1
    before = points[index - 1] if closed or index > 0 else points[index]
    after = points[(index + 1) % len(points)] if closed or index < last else points[index]
    return after[0] - before[0], after[1] - before[1]


def _touch(value: float, neighbors: list[float]) -> int:
    """Tell which side of a pixel edge the path's neighbors are on, when it only touches it.

    1 past the edge, -1 before it; 0 off an edge or when the path crosses it.
    """
    snapped = round(value, _SNAP_DECIMALS)
    edge = math.floor(snapped)
    sides = {
        (round(n, _SNAP_DECIMALS) > edge) - (round(n, _SNAP_DECIMALS) < edge) for n in neighbors
    }
    if snapped != edge or len(sides) != 1:
        return 0
    return sides.pop()


def _axis_cells(value: float, inward: float, forward: float, touch: int = 0) -> list[int]:
    """The pixel holding ``value``, or two of them on the tip of a symmetric shape.

    On a pixel edge it is the pixel on the ``inward`` side. When the path runs along the edge's
    normal there, inward decides nothing, and both pixels go in, in the order the path moves.
    """
    snapped = round(value, _SNAP_DECIMALS)
    edge = math.floor(snapped)
    if touch:
        return [edge if touch > 0 else edge - 1]
    if snapped != edge or inward > 0:
        return [edge]
    if inward < 0:
        return [edge - 1]
    return [edge - 1, edge] if forward >= 0 else [edge, edge - 1]


def _inward(value: float, *, flat: bool, turning: bool) -> float:
    """Which side of a pixel edge the point goes to: ``value``, unless the contour is flat.

    A closed contour of zero area has no inside and runs both ways over the same pixels, so its
    direction must not choose (audit B5): it takes the pixel past the edge, as the fill's
    half-open rows do, also where it turns back with a zero tangent. An open line keeps the side
    of its direction, which a wider stroke pairs its extra pixel with (audit B6, kept).
    """
    if not flat:
        return value
    return 1.0 if turning else abs(value)


def _cells_of_points(contour: Contour) -> list[list[Cell]]:
    """Per point, its pixels: one, or two on the tip of a symmetric shape."""
    points = contour.points
    side = contour_side(contour)
    flat = contour.closed and _area(points) == 0
    cells: list[list[Cell]] = []
    for index, (x, y) in enumerate(points):
        tx, ty = _tangent(points, index, closed=contour.closed)
        near = _neighbors(points, index, closed=contour.closed)
        turning = (tx, ty) == (0, 0)
        across_x = _inward(-ty * side, flat=flat, turning=turning)
        across_y = _inward(tx * side, flat=flat, turning=turning)
        columns = _axis_cells(x, across_x, tx, _touch(x, [p[0] for p in near]))
        rows = _axis_cells(y, across_y, ty, _touch(y, [p[1] for p in near]))
        cells.append(_own_end([(c, r) for c in columns for r in rows], index, contour))
    return cells


def _own_end(cells: list[Cell], index: int, contour: Contour) -> list[Cell]:
    """Keep only the pixel on the line's side at an open line's end on a pixel edge.

    That is the pixel ahead at the start and the one behind at the end.
    """
    if contour.closed or len(cells) == 1:
        return cells
    if index == 0:
        return cells[-1:]
    return cells[:1] if index == len(contour.points) - 1 else cells


def _offset(step: int, delta: int, steps: int) -> int:
    """``step * delta / steps`` rounded, ties toward 0, in integers."""
    magnitude = -((steps - 2 * step * abs(delta)) // (2 * steps))
    return magnitude if delta >= 0 else -magnitude


def _between(start: Cell, end: Cell) -> list[Cell]:
    """The cells after ``start`` up to ``end``, one step of the major axis at a time.

    Always worked from the smaller cell, so a segment gives the same pixels both ways.
    """
    if end < start:
        return [*[*reversed(_between(end, start))][1:], end]
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(abs(dx), abs(dy))
    return [
        (start[0] + _offset(step, dx, steps), start[1] + _offset(step, dy, steps))
        for step in range(1, steps + 1)
    ]


def _turn_degrees(before: Point, at: Point, after: Point) -> float:
    ax, ay = at[0] - before[0], at[1] - before[1]
    bx, by = after[0] - at[0], after[1] - at[1]
    if (ax, ay) == (0, 0) or (bx, by) == (0, 0):
        return 0.0
    return abs(math.degrees(math.atan2(ax * by - ay * bx, ax * bx + ay * by)))


def _corners(contour: Contour, cells: list[list[Cell]]) -> set[Cell]:
    points, count = contour.points, len(contour.points)
    indexes = range(count) if contour.closed else range(1, count - 1)
    return {
        cell
        for index in indexes
        if _turn_degrees(points[index - 1], points[index], points[(index + 1) % count])
        > _CORNER_DEGREES
        for cell in cells[index]
    }


def _is_l(first: Cell, middle: Cell, last: Cell) -> bool:
    """``first`` and ``last`` touch by a corner, and ``middle`` touches both by a side."""

    def by_side(a: Cell, b: Cell) -> bool:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1

    diagonal = abs(first[0] - last[0]) == 1 and abs(first[1] - last[1]) == 1
    return diagonal and by_side(first, middle) and by_side(middle, last)


def _deviation(cell: Cell, contour: Contour, side: float) -> tuple[float, bool]:
    """How far the cell's center lies from the path, and whether it lies outside.

    Rounded, so the mirror images of a cell, a few 1e-15 apart, compare equal.
    """
    cx, cy = cell[0] + 0.5, cell[1] + 0.5
    points = contour.points
    ends = [*points[1:], points[0]] if contour.closed else points[1:]
    best, outside = math.inf, False
    for (x0, y0), (x1, y1) in zip(points, ends or points, strict=False):
        dx, dy = x1 - x0, y1 - y0
        length = dx * dx + dy * dy
        along = 0.0 if length == 0 else ((cx - x0) * dx + (cy - y0) * dy) / length
        px, py = x0 + min(1.0, max(0.0, along)) * dx, y0 + min(1.0, max(0.0, along)) * dy
        distance = round(math.hypot(cx - px, cy - py), _SNAP_DECIMALS)
        if distance < best:
            best, outside = distance, ((cx - px) * dy - (cy - py) * dx) * side > 0
    return best, outside


def _l_corner_indexes(cells: list[Cell], kept_corners: set[Cell], *, closed: bool) -> list[int]:
    count = len(cells)
    middles = range(count) if closed and count > 3 else range(1, count - 1)  # noqa: PLR2004  # motivo: a triple
    return [
        index
        for index in middles
        if cells[index] not in kept_corners
        and _is_l(cells[index - 1], cells[index], cells[(index + 1) % count])
    ]


def _tip_twin(
    cells: list[Cell],
    corners: list[int],
    worst: int,
    key: Callable[[int], tuple[float, bool, Cell]],
) -> list[int]:
    """The other half of a two-pixel tip, when ``worst`` is one half and ties with it.

    A narrow shape turns back over two pixels side by side; each is the middle of an L and
    they lie at the same distance from the path, so dropping only one leaves the tip lopsided
    (audit M2). Dropping both keeps it mirrored and still joined: the pixels before and after
    the tip touch by a side, which only a turn back guarantees.
    """
    count = len(cells)
    for first in ((worst - 1) % count, worst):
        second = (first + 1) % count
        twin = second if first == worst else first
        if twin not in corners or key(twin)[:2] != key(worst)[:2]:
            continue
        before, after = cells[first - 1], cells[(second + 1) % count]
        if abs(before[0] - after[0]) + abs(before[1] - after[1]) == 1:
            return [twin]
    return []


def _drop_l_corners(cells: list[Cell], kept_corners: set[Cell], contour: Contour) -> list[Cell]:
    """Drop the middle pixel of every L, the one farthest from the path first.

    Deciding by geometry and not by the order the path runs keeps mirror images mirrored:
    two overlapping Ls share a pixel, and dropping the first one met would turn a circle
    drawn clockwise into a slightly twisted ring.
    """
    side = contour_side(contour)
    deviations: dict[Cell, tuple[float, bool]] = {}

    def worst_first(index: int) -> tuple[float, bool, Cell]:
        cell = result[index]
        if cell not in deviations:
            deviations[cell] = _deviation(cell, contour, side)
        return (*deviations[cell], cell)

    result = list(cells)
    while corners := _l_corner_indexes(result, kept_corners, closed=contour.closed):
        worst = max(corners, key=worst_first)
        for index in sorted({worst, *_tip_twin(result, corners, worst, worst_first)}, reverse=True):
            del result[index]
    return result


def _without_repeated_points(contour: Contour) -> Contour:
    """Drop every point equal to the one before it, and a closed contour's copy of its start.

    A repeated point has no tangent, so it picks pixels on both sides of an edge (audit M1);
    the copy of the start would walk the seam backwards and skew the tangent there.
    """
    points = [contour.points[0]]
    points.extend(p for before, p in itertools.pairwise(contour.points) if p != before)
    if contour.closed and len(points) > 1 and points[-1] == points[0]:
        del points[-1]
    return Contour(tuple(points), closed=contour.closed)


def contour_line(contour: Contour) -> list[Cell]:
    """The pixels of the one-pixel line along ``contour``, in the order the contour runs."""
    if not contour.points:
        return []
    contour = _without_repeated_points(contour)
    cells = _cells_of_points(contour)
    flat = [cell for point_cells in cells for cell in point_cells]
    joined = [flat[0]]
    for cell in [*flat[1:], *flat[:1]] if contour.closed else flat[1:]:
        joined.extend(_between(joined[-1], cell))
    if contour.closed and len(joined) > 1:
        del joined[-1]
    clean = _drop_l_corners(joined, _corners(contour, cells), contour)
    return even_out_steps(clean, closed=contour.closed)


def line_cells(path: Path) -> set[Cell]:
    """The pixels of a one-pixel line along ``path``."""
    return {cell for contour in path.contours() for cell in contour_line(contour)}


def line(canvas: Canvas, path: Path, color: Color) -> None:
    """Draw ``path`` as a one-pixel line, pixel-art clean.

    >>> from ai_draw.geometry.path import ellipse
    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(16, 16)
    >>> line(canvas, ellipse(8, 8, 6), (20, 20, 20, 255))
    """
    _ = check_pixel_color(color)
    for x, y in sorted(line_cells(path)):
        canvas.paint(x, y, color)

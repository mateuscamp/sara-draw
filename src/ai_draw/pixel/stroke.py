# SPDX-License-Identifier: GPL-3.0-only
"""Stroke as fillable pieces: a quad per segment and a disc on every vertex.

This is the baseline the pixel-art line of phase 4 has to beat: at low resolution the
width of a stroke drawn this way swells and thins, and its steps come out uneven.

Separate pieces, not one polygon: each is painted over the others in the same color, so
overlaps do not matter. One merged polygon would need every piece oriented alike, or
"nonzero" would open a hole where two segments cross.

    >>> from ai_draw.geometry.path import Path
    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(8, 8)
    >>> stroke(canvas, Path().move_to(1, 1).line_to(6, 6), (0, 0, 0, 255), 1)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ai_draw.geometry.path import Contour, Point
from ai_draw.pixel.fill import spans

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_draw.geometry.path import Path
    from ai_draw.grid.canvas import Canvas, Color

MIN_DISC_SIDES = 8


def disc(cx: float, cy: float, radius: float) -> Contour:
    """Disc as a polygon, with a side per pixel of perimeter and at least eight.

    The polygon sits inside the circle, and the error stays under half a pixel.
    """
    sides = max(MIN_DISC_SIDES, math.ceil(2 * math.pi * radius))
    points: list[Point] = []
    for side in range(sides):
        angle = 2 * math.pi * side / sides
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return Contour(tuple(points), closed=True)


def _quad(start: Point, end: Point, half: float) -> Contour | None:
    """The quad of a segment, ``half`` the width to each side; None for a zero-length one."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0:
        return None
    nx, ny = -dy / length * half, dx / length * half
    corners = ((x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny))
    return Contour(corners, closed=True)


def _contour_pieces(contour: Contour, half: float) -> list[Contour]:
    points = contour.points
    segment_count = len(points) if contour.closed else len(points) - 1
    quads = [
        _quad(points[index], points[(index + 1) % len(points)], half)
        for index in range(segment_count)
    ]
    discs = [disc(x, y, half) for x, y in points]
    return [quad for quad in quads if quad is not None] + discs


def stroke_pieces(contours: Sequence[Contour], width: float) -> list[Contour]:
    """The stroke of ``contours`` as pieces to fill one by one with "nonzero"."""
    if width <= 0:
        message = f"width={width!r}, expected a positive number"
        raise ValueError(message)
    return [piece for contour in contours for piece in _contour_pieces(contour, width / 2)]


def stroke(canvas: Canvas, path: Path, color: Color, width: float) -> None:
    """Stroke ``path`` with ``width`` pixels, round caps and round joins."""
    for piece in stroke_pieces(path.contours(), width):
        for span in spans([piece], "nonzero", canvas.height):
            canvas.span(span.x, span.y, span.length, color)

# SPDX-License-Identifier: GPL-3.0-only
"""Smooth stroke: the outline of a line of a given width, filled with exact coverage.

The path is flattened finely and each side is pushed out by half the width along the normal
at every vertex. An open line gets round caps; a closed one becomes a ring, its inner side
run backwards so the hole stays empty under "nonzero". Where the path turns sharply, the
outer side gets a round join; the inner side keeps the corner point, which is exact as long
as the turn is wider than the stroke.

    >>> from ai_draw.geometry.path import ellipse
    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(24, 24)
    >>> stroke(canvas, ellipse(12, 12, 8), (20, 20, 20, 255), 1.5)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ai_draw.errors import SettingError
from ai_draw.geometry.path import Path, polygon
from ai_draw.smooth.coverage import SEGMENTS_PER_PIXEL, fill

if TYPE_CHECKING:
    from ai_draw.geometry.path import Contour, Point
    from ai_draw.grid.canvas import Canvas, Color

# A vertex that turns more than this gets a round join instead of a bare corner.
_JOIN_DEGREES = 15
# A small outer turn keeps a mitered corner, never reaching past this many half-widths.
_MITER_LIMIT = 2.0


def _distinct(contour: Contour) -> list[Point]:
    """The points without repeats in a row, and without the closing copy of the first."""
    points: list[Point] = []
    for point in contour.points:
        if not points or point != points[-1]:
            points.append(point)
    if contour.closed and len(points) > 1 and points[-1] == points[0]:
        del points[-1]
    return points


def _normal(start: Point, end: Point) -> Point:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    return -dy / length, dx / length


def _arc(center: Point, half: float, start_angle: float, sweep: float) -> list[Point]:
    """Points strictly inside an arc of radius ``half``, from ``start_angle`` by ``sweep``."""
    steps = max(2, math.ceil(abs(sweep) * half * SEGMENTS_PER_PIXEL))
    return [
        (
            center[0] + half * math.cos(start_angle + sweep * k / steps),
            center[1] + half * math.sin(start_angle + sweep * k / steps),
        )
        for k in range(1, steps)
    ]


def _side(
    points: list[Point], normals: list[Point], half: float, *, closed: bool, outer_turn: int
) -> list[Point]:
    """One side of the stroke: each vertex pushed ``half`` along its normal.

    A sharp turn whose sign is ``outer_turn`` leaves this side outside the corner, and the
    side gets a round join there.
    """
    side: list[Point] = []
    count = len(points)
    for index, point in enumerate(points):
        if not closed and index in (0, count - 1):
            nx, ny = normals[0] if index == 0 else normals[-1]
            side.append((point[0] + nx * half, point[1] + ny * half))
            continue
        before, after = normals[index - 1], normals[index % len(normals)]
        room = min(
            math.dist(point, points[index - 1]), math.dist(point, points[(index + 1) % count])
        )
        side.extend(_join(point, (before, after), half, room=room, outer_turn=outer_turn))
    return side


def _join(
    point: Point, normals: tuple[Point, Point], half: float, *, room: float, outer_turn: int
) -> list[Point]:
    """The side's points at a vertex between two segments with these normals.

    Outside a sharp corner the side follows an arc. Inside, it takes the point where the two
    pushed-out edges cross, which is exact while that crossing lands on both segments
    (``room`` is the shorter one); the old cap of two half-widths cut a notch into turns past
    120 degrees (audit A2). Without room, the side goes through the vertex itself.
    """
    before, after = normals
    cross = before[0] * after[1] - before[1] * after[0]
    turn = math.atan2(cross, before[0] * after[0] + before[1] * after[1])
    first = (point[0] + before[0] * half, point[1] + before[1] * half)
    last = (point[0] + after[0] * half, point[1] + after[1] * half)
    if abs(math.degrees(turn)) > _JOIN_DEGREES and turn * outer_turn > 0:
        return [first, *_arc(point, half, math.atan2(before[1], before[0]), turn), last]
    mx, my = before[0] + after[0], before[1] + after[1]
    length = math.hypot(mx, my) or 1.0
    mx, my = mx / length, my / length
    cosine = mx * after[0] + my * after[1]
    inner = turn * outer_turn < 0
    if inner and cosine > 0 and half * math.sqrt(1 - cosine * cosine) / cosine <= room:
        return [(point[0] + mx * half / cosine, point[1] + my * half / cosine)]
    if inner:
        return [first, point, last]
    reach = half / max(cosine, 1 / _MITER_LIMIT)
    return [(point[0] + mx * reach, point[1] + my * reach)]


def _contour_outline(contour: Contour, half: float) -> list[list[Point]]:
    points = _distinct(contour)
    if len(points) < 2:  # noqa: PLR2004  # motivo: a segment needs two points
        return [[point, *_arc(point, half, 0.0, 2 * math.pi)] for point in points]
    ends = [*points[1:], points[0]] if contour.closed else points[1:]
    normals = [_normal(start, end) for start, end in zip(points, ends, strict=False)]
    # The pushed-out side (+normal) is outside a turn of negative sign, the other of positive.
    left = _side(points, normals, half, closed=contour.closed, outer_turn=-1)
    flipped = [(-x, -y) for x, y in normals]
    right = _side(points, flipped, half, closed=contour.closed, outer_turn=1)
    if contour.closed:
        return [left, right[::-1]]
    end_cap = _arc(points[-1], half, math.atan2(normals[-1][1], normals[-1][0]), -math.pi)
    start_angle = math.atan2(flipped[0][1], flipped[0][0])
    start_cap = _arc(points[0], half, start_angle, -math.pi)
    return [[*left, *end_cap, *right[::-1], *start_cap]]


def stroke_outline(path: Path, width: float) -> Path:
    """The outline of ``path`` stroked ``width`` pixels wide, round caps and joins."""
    if not math.isfinite(width) or width <= 0:
        message = f"width={width!r}, expected a positive finite number of pixels"
        raise SettingError(message)
    outline = Path()
    for contour in path.contours(segments_per_pixel=SEGMENTS_PER_PIXEL):
        for ring in _contour_outline(contour, width / 2):
            if len(ring) >= 3:  # noqa: PLR2004  # motivo: a polygon has three corners
                _ = outline.extend(polygon(ring))
    return outline


def stroke(canvas: Canvas, path: Path, color: Color, width: float) -> None:
    """Stroke ``path`` with an antialiased line ``width`` pixels wide (any positive number)."""
    fill(canvas, stroke_outline(path, width), color)

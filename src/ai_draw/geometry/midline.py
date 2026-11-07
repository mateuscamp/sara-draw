# SPDX-License-Identifier: GPL-3.0-only
"""The line along the middle of a shape thinner than a given width.

A shape thinner than a pixel all along has no inside to sample at one pixel: a long sliver
covers one pixel center, or none. Its middle line keeps its length and its place, and drawn
one pixel wide it is what the shape looks like at that size (``ai_draw.pixel.fill``).

The two sides run from one end of the shape to the other. The middle line joins the halfway
points between them, taken at the same share of each side's length, and ends at a tip or at
the middle of a blunt end.

    >>> midline(((0, 0), (8, 0), (8, 0.5), (0, 0.5)), 1)
    ((8.0, 0.25), (7.75, 0.25), (0.25, 0.25), (0.0, 0.25))
"""

from __future__ import annotations

import bisect
import itertools
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_draw.geometry.path import Point

__all__ = ["distance_to_line", "midline", "straightened"]


def midline(points: Sequence[Point], width: float) -> tuple[Point, ...] | None:
    """The middle line of the closed contour ``points``, if it is thinner than ``width``.

    None when the shape is ``width`` wide or more somewhere, or has no area.

    >>> midline(((0, 0), (1, 0), (1, 1), (0, 1)), 1) is None
    True
    """
    if not _could_be_thin(points, width):
        return None
    near, far = _sides(points)
    if _gap(near, far) >= width:
        return None
    middles = _middles(near, far) or [_halfway(near[0], near[-1])]
    start = _end(near, far, width, middles[0])
    finish = _end(near[::-1], far[::-1], width, middles[-1])
    return tuple(point for point, _ in itertools.groupby([start, *middles, finish]))


def straightened(line: tuple[Point, ...], tolerance: float) -> tuple[Point, ...]:
    """Only the ends of ``line``, if all of it lies within ``tolerance`` of the chord between them.

    A straight middle line comes in many short segments, and the pixel line takes those for a
    curve and sorts its steps, which bends it off the shape (audit, 04/11). All or nothing: a
    real curve keeps every point, or its smooth steps would turn into a polygon's.

    >>> straightened(((0, 0), (5, 0.2), (10, 0)), 0.25)
    ((0, 0), (10, 0))
    """
    start, end = line[0], line[-1]
    near = all(_to_segment(point, start, end) <= tolerance for point in line)
    return (start, end) if near else line


def distance_to_line(point: Point, line: tuple[Point, ...]) -> float:
    """How far ``point`` is from the open polyline ``line``.

    >>> distance_to_line((5, 3), ((0, 0), (10, 0)))
    3.0
    """
    return min(
        (_to_segment(point, start, end) for start, end in itertools.pairwise(line)),
        default=math.dist(point, line[0]),
    )


def _could_be_thin(points: Sequence[Point], width: float) -> bool:
    """Spares the slower test a shape too large for its way around to be thin.

    A shape thinner than ``width`` all along has less area than ``width`` times half its way
    around: each side is at least as long as the shape.
    """
    ends = [*points[1:], *points[:1]]
    pairs = list(zip(points, ends, strict=True))
    area = abs(math.fsum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2
    around = math.fsum(math.dist(start, end) for start, end in pairs)
    return 0 < area < width * around / 2


def _sides(points: Sequence[Point]) -> tuple[list[Point], list[Point]]:
    """The two sides from one end to the other; an end is the vertex farthest from the other."""
    first = _farthest(points, points[0])
    last = _farthest(points, points[first])
    count = len(points)
    forward = (last - first) % count
    near = [points[(first + step) % count] for step in range(forward + 1)]
    far = [points[(first - step) % count] for step in range(count - forward + 1)]
    return near, far


def _farthest(points: Sequence[Point], origin: Point) -> int:
    """The index of the point farthest from ``origin``; the first one on a tie."""
    return max(range(len(points)), key=lambda index: math.dist(points[index], origin))


def _gap(near: list[Point], far: list[Point]) -> float:
    """How far apart the sides get: the most a vertex of one is away from the other."""
    return max(
        itertools.chain(
            (_to_side(point, far) for point in near), (_to_side(point, near) for point in far)
        )
    )


def _to_side(point: Point, side: list[Point]) -> float:
    return min(_to_segment(point, start, end) for start, end in itertools.pairwise(side))


def _to_segment(point: Point, start: Point, end: Point) -> float:
    (px, py), (sx, sy), (ex, ey) = point, start, end
    dx, dy = ex - sx, ey - sy
    squared = dx * dx + dy * dy
    share = 0.0 if squared == 0 else ((px - sx) * dx + (py - sy) * dy) / squared
    share = min(max(share, 0.0), 1.0)
    return math.hypot(px - sx - share * dx, py - sy - share * dy)


def _middles(near: list[Point], far: list[Point]) -> list[Point]:
    """The halfway points between the sides, at each vertex's share of its side's length."""
    near_lengths, far_lengths = _lengths(near), _lengths(far)
    shares = {length / near_lengths[-1] for length in near_lengths}
    shares |= {length / far_lengths[-1] for length in far_lengths}
    return [
        _halfway(_at(near, near_lengths, share), _at(far, far_lengths, share))
        for share in sorted(shares - {0.0, 1.0})
    ]


def _lengths(side: list[Point]) -> list[float]:
    """How far along ``side`` each of its vertices is."""
    steps = (math.dist(start, end) for start, end in itertools.pairwise(side))
    return list(itertools.accumulate(steps, initial=0.0))


def _at(side: list[Point], lengths: list[float], share: float) -> Point:
    """The point ``share`` of the way along ``side``."""
    target = share * lengths[-1]
    index = min(max(bisect.bisect_left(lengths, target), 1), len(side) - 1)
    span = lengths[index] - lengths[index - 1]
    along = (target - lengths[index - 1]) / span if span else 0.0
    (sx, sy), (ex, ey) = side[index - 1], side[index]
    return (sx + along * (ex - sx), sy + along * (ey - sy))


def _halfway(first: Point, second: Point) -> Point:
    return ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)


def _end(near: list[Point], far: list[Point], width: float, inside: Point) -> Point:
    """Where the middle line ends, coming from ``inside`` on the way to the tip of both sides.

    A blunt end's middle lies halfway between the last vertices of each side within ``width``
    of the tip. On a pointed or round tip the line is already at least as close to the tip as
    that point: aimed at it, the line would turn back (audit, 04/11), so the tip is the end.
    """
    tip, aim = near[0], _halfway(_last_within(near, width), _last_within(far, width))
    return tip if math.dist(tip, inside) <= math.dist(tip, aim) else aim


def _last_within(side: list[Point], width: float) -> Point:
    tip = side[0]
    return list(itertools.takewhile(lambda point: math.dist(tip, point) <= width, side))[-1]

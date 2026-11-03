# SPDX-License-Identifier: GPL-3.0-only
"""The line along the middle of a shape thinner than a given width.

A shape thinner than a pixel all along has no inside to sample at one pixel: a long sliver
covers one pixel center, or none. Its middle line keeps its length and its place, and drawn
one pixel wide it is what the shape looks like at that size (``ai_draw.pixel.fill``).

The two sides run from one end of the shape to the other. The middle line joins the halfway
points between them, taken at the same share of each side's length, and goes on to where it
leaves the shape: at a tip, or at the middle of a blunt end.

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

__all__ = ["midline"]


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
    start = _end(near, far, width, middles[0], points)
    finish = _end(near[::-1], far[::-1], width, middles[-1], points)
    return tuple(point for point, _ in itertools.groupby([start, *middles, finish]))


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


def _end(
    near: list[Point], far: list[Point], width: float, inside: Point, points: Sequence[Point]
) -> Point:
    """Where the line from ``inside`` toward the middle of the end leaves the shape.

    The middle of the end is halfway between the last vertices of each side within ``width``
    of the tip: the tip itself, or the middle of a blunt end's short side. A round tip is
    farther out than that middle, and the line goes on to it.
    """
    aim = _halfway(_last_within(near, width), _last_within(far, width))
    if aim == inside:
        return aim
    leaves = _exit(inside, aim, points)
    return aim if leaves is None else leaves


def _last_within(side: list[Point], width: float) -> Point:
    tip = side[0]
    return list(itertools.takewhile(lambda point: math.dist(tip, point) <= width, side))[-1]


def _exit(origin: Point, aim: Point, points: Sequence[Point]) -> Point | None:
    """The first point where the ray from ``origin`` through ``aim`` crosses the contour."""
    ends = [*points[1:], *points[:1]]
    crossings = [
        crossing
        for start, end in zip(points, ends, strict=True)
        if (crossing := _crossing(origin, aim, start, end)) is not None
    ]
    return min(crossings)[1] if crossings else None


def _crossing(origin: Point, aim: Point, start: Point, end: Point) -> tuple[float, Point] | None:
    """How far along the ray (in ``aim - origin`` lengths) it crosses the edge, and where."""
    (ox, oy), (ax, ay), (sx, sy), (ex, ey) = origin, aim, start, end
    dx, dy, edge_x, edge_y = ax - ox, ay - oy, ex - sx, ey - sy
    denominator = dx * edge_y - dy * edge_x
    if denominator == 0:
        return None
    along = ((sx - ox) * edge_y - (sy - oy) * edge_x) / denominator
    share = ((sx - ox) * dy - (sy - oy) * dx) / denominator
    if along <= 0 or not 0 <= share <= 1:
        return None
    return along, (sx + share * edge_x, sy + share * edge_y)

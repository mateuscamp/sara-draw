# SPDX-License-Identifier: GPL-3.0-only
"""Vector path: lines and Bezier curves in subpaths, like SVG's ``<path>``.

A path stores commands, not pixels. Only ``contours()`` flattens it into polygons, one
segment per pixel of curve length; that is why transforming comes first, in
``transformed``, so the curve flattens at the size it will have on screen.

    >>> drop = Path().move_to(16, 2).cubic_to(30, 20, 26, 30, 16, 30)
    >>> drop = drop.cubic_to(6, 30, 2, 20, 16, 2).close()
    >>> len(drop.contours())
    1
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Self

from ai_draw.errors import GeometryError, SettingError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_draw.geometry.transform import Transform

Point = tuple[float, float]
CommandKind = Literal["move", "line", "quad", "cubic", "close"]
FillRule = Literal["nonzero", "evenodd"]
"""SVG's fill rules: "nonzero" counts edge direction, "evenodd" only the crossings."""

# Fraction of the radius that puts the control points of a quarter ellipse on the arc:
# 4/3 * (sqrt(2) - 1). Largest error 0.027% of the radius, invisible in pixels.
ELLIPSE_CONTROL = 0.5522847498

# Ceiling of segments per curve: a runaway control point cannot stall the live preview,
# and 256 segments is more than any canvas this library targets needs.
MAX_SEGMENTS = 256


@dataclass(frozen=True, slots=True)
class Contour:
    """A flattened subpath.

    ``closed`` tells the stroke to join the last point to the first; filling always treats a
    contour as closed.
    """

    points: tuple[Point, ...]
    closed: bool


@dataclass(frozen=True, slots=True)
class Command:
    """One drawing command and its points: the end point last, control points before it."""

    kind: CommandKind
    points: tuple[Point, ...]


class Path:
    """A builder of subpaths; every drawing method returns the path, so calls chain."""

    def __init__(self) -> None:
        """Start an empty path; the first command must be ``move_to``."""
        self._commands: list[Command] = []

    def _add(self, kind: CommandKind, *points: Point) -> Self:
        if kind != "move":
            last = self._commands[-1] if self._commands else None
            if last is None or last.kind == "close":
                message = f"{kind} without a starting point: begin the subpath with move_to(x, y)"
                raise GeometryError(message)
        self._commands.append(Command(kind, points))
        return self

    def move_to(self, x: float, y: float) -> Self:
        """Start a subpath at (x, y)."""
        return self._add("move", (x, y))

    def line_to(self, x: float, y: float) -> Self:
        """Straight segment to (x, y)."""
        return self._add("line", (x, y))

    def quad_to(self, cx: float, cy: float, x: float, y: float) -> Self:
        """Quadratic Bezier: one control point (cx, cy), ending at (x, y)."""
        return self._add("quad", (cx, cy), (x, y))

    def cubic_to(  # noqa: PLR0913, PLR0917  # motivo: the six numbers of an SVG C command
        self, c1x: float, c1y: float, c2x: float, c2y: float, x: float, y: float
    ) -> Self:
        """Cubic Bezier: two control points, ending at (x, y)."""
        return self._add("cubic", (c1x, c1y), (c2x, c2y), (x, y))

    def close(self) -> Self:
        """Close the subpath back to where it started."""
        return self._add("close")

    def extend(self, other: Path) -> Self:
        """Append the subpaths of ``other``.

        A ring is the outer ellipse plus the inner one, filled with "evenodd".
        """
        self._commands.extend(other._commands)
        return self

    def transformed(self, transform: Transform) -> Path:
        """A copy with every point passed through ``transform``."""
        copy = Path()
        copy._commands = [
            Command(command.kind, tuple(transform.apply(x, y) for x, y in command.points))
            for command in self._commands
        ]
        return copy

    @property
    def commands(self) -> tuple[Command, ...]:
        """The commands as written, for replaying the path elsewhere (a renderer, a file)."""
        return tuple(self._commands)

    def contours(self, segments_per_pixel: int = 1) -> list[Contour]:
        """The subpaths flattened into polygons.

        The pixel output takes one segment per pixel of curve; the smooth output asks for more,
        so the chord stays well within one step of coverage.
        """
        if segments_per_pixel < 1:
            message = f"segments_per_pixel={segments_per_pixel!r}, expected an integer >= 1"
            raise SettingError(message)
        flattened: list[tuple[list[Point], bool]] = []
        for command in self._commands:
            if command.kind == "move":
                flattened.append((list(command.points), False))
            elif command.kind == "close":
                flattened[-1] = (flattened[-1][0], True)
            elif command.kind == "line":
                flattened[-1][0].extend(command.points)
            else:
                _flatten_curve(flattened[-1][0], command.points, segments_per_pixel)
        return [Contour(tuple(points), closed) for points, closed in flattened]


def _segments(controls: Sequence[Point], per_pixel: int) -> int:
    """``per_pixel`` segments per pixel of the control polygon, never shorter than the curve."""
    # A plain running sum, not sum(): since Python 3.12 sum() compensates rounding, and the
    # segment count must match the Lua original bit for bit at the ceil.
    length = 0.0
    for (x0, y0), (x1, y1) in itertools.pairwise(controls):
        length += math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
    return max(1, min(MAX_SEGMENTS * per_pixel, math.ceil(length * per_pixel)))


def _curve_point(controls: Sequence[Point], t: float) -> Point:
    """Point of a Bezier of any degree at ``t``, by De Casteljau."""
    xs = [x for x, _ in controls]
    ys = [y for _, y in controls]
    for degree in range(len(xs) - 1, 0, -1):
        for i in range(degree):
            xs[i] += (xs[i + 1] - xs[i]) * t
            ys[i] += (ys[i + 1] - ys[i]) * t
    return xs[0], ys[0]


def _flatten_curve(points: list[Point], curve: tuple[Point, ...], per_pixel: int) -> None:
    controls = [points[-1], *curve]
    segments = _segments(controls, per_pixel)
    points.extend(_curve_point(controls, step / segments) for step in range(1, segments))
    # The last point is the exact end, not the computed one: the curve then joins the next
    # command without the floating-point residue of t = 1.
    points.append(curve[-1])


def polygon(points: Sequence[Point]) -> Path:
    """Closed polygon through ``points``.

    >>> polygon([(0, 0), (4, 0), (0, 3)]).contours()[0].closed
    True
    """
    if len(points) < 3:  # noqa: PLR2004  # motivo: a polygon has at least three corners
        message = f"polygon with {len(points)} points, expected at least 3 points"
        raise GeometryError(message)
    path = Path().move_to(*points[0])
    for x, y in points[1:]:
        _ = path.line_to(x, y)
    return path.close()


def rect(x: float, y: float, width: float, height: float) -> Path:
    """Rectangle with its top-left corner at (x, y)."""
    return polygon([(x, y), (x + width, y), (x + width, y + height), (x, y + height)])


def ellipse(cx: float, cy: float, rx: float, ry: float | None = None) -> Path:
    """Ellipse centered on (cx, cy) in four cubics; one radius makes a circle."""
    ry = rx if ry is None else ry
    kx, ky = rx * ELLIPSE_CONTROL, ry * ELLIPSE_CONTROL
    return (
        Path()
        .move_to(cx + rx, cy)
        .cubic_to(cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry)
        .cubic_to(cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy)
        .cubic_to(cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry)
        .cubic_to(cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy)
        .close()
    )

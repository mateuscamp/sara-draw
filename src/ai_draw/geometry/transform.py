# SPDX-License-Identifier: GPL-3.0-only
"""Affine 2D transform: move, scale and turn a path before it is rasterized.

Six numbers, like SVG's ``matrix(a, b, c, d, e, f)``::

    x' = a*x + c*y + e
    y' = b*x + d*y + f

An affine map keeps Bezier curves Bezier, so transforming the control points is the same as
transforming the curve. That is why flattening happens afterwards, in screen pixels.

    >>> Transform.rotate(90).then(Transform.translate(32, 32)).apply(1, 0)
    (32.0, 33.0)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Exact (sin, cos) for each quarter turn: math.cos(math.pi / 2) is 6e-17, and a square
# turned 90 degrees would come out with an edge half a pixel off, depending on rounding.
_QUARTER_TURNS: tuple[tuple[float, float], ...] = ((0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0))


def _sin_cos(degrees: float) -> tuple[float, float]:
    quarters = degrees / 90
    if quarters % 1 == 0:
        return _QUARTER_TURNS[int(quarters % 4)]
    # Same operation order as the Lua original, so the parity check sees the same bits.
    radians = degrees * math.pi / 180
    return math.sin(radians), math.cos(radians)


@dataclass(frozen=True, slots=True)
class Transform:
    """An affine map; build it with the static constructors and chain with ``then``."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @staticmethod
    def identity() -> Transform:
        """The map that leaves every point where it is."""
        return Transform()

    @staticmethod
    def translate(dx: float, dy: float) -> Transform:
        """Move by (dx, dy)."""
        return Transform(e=dx, f=dy)

    @staticmethod
    def scale(sx: float, sy: float | None = None) -> Transform:
        """Scale around the origin; one factor scales both axes."""
        return Transform(a=sx, d=sx if sy is None else sy)

    @staticmethod
    def rotate(degrees: float) -> Transform:
        """Turn around the origin. With y growing downward, positive turns clockwise.

        >>> Transform.rotate(90).apply(1, 0)
        (0.0, 1.0)
        """
        sin, cos = _sin_cos(degrees)
        return Transform(a=cos, b=sin, c=-sin, d=cos)

    def then(self, other: Transform) -> Transform:
        """Compose, ``self`` first: ``t.then(u).apply(p) == u.apply(t.apply(p))``."""
        o = other
        return Transform(
            a=o.a * self.a + o.c * self.b,
            b=o.b * self.a + o.d * self.b,
            c=o.a * self.c + o.c * self.d,
            d=o.b * self.c + o.d * self.d,
            e=o.a * self.e + o.c * self.f + o.e,
            f=o.b * self.e + o.d * self.f + o.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        """Where the point (x, y) lands."""
        return self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f

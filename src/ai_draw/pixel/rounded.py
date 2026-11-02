# SPDX-License-Identifier: GPL-3.0-only
"""Rounded rectangle cut row by row, not as a vector corner.

Each corner row is inset by how far the circle of the radius is from the edge at that
row's center, so the four corners mirror each other exactly. A vector corner sampled at
pixel centers gave 8 different pixels at radius 7 in the earlier code this was ported from.

    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(70, 98)
    >>> fill_rounded_rect(canvas, 0, 0, 70, 98, radius=7, color=(32, 26, 46, 255))
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ai_draw.grid.canvas import check_pixel_color

if TYPE_CHECKING:
    from ai_draw.grid.canvas import Canvas, Color


def _corner_insets(radius: int) -> list[int]:
    """Horizontal inset of each row inside a corner of ``radius``.

    ``floor(m + 0.5)`` instead of ``round``: Python's round breaks ties to even, but there is
    no tie here, since a half-width ending in .5 would need r^2 = x^2 + x + k^2 + k + 0.5
    with integers, which is impossible.
    """
    insets: list[int] = []
    for row in range(radius):
        distance = radius - 0.5 - row
        half_width = math.sqrt(max(0.0, radius * radius - distance * distance))
        insets.append(radius - math.floor(half_width + 0.5))
    return insets


def _row_inset(row: int, height: int, insets: list[int]) -> int:
    radius = len(insets)
    if row < radius:
        return insets[row]
    if row >= height - radius:
        return insets[height - 1 - row]
    return 0


def fill_rounded_rect(  # noqa: PLR0913  # motivo: position, size, radius and color
    canvas: Canvas, x: int, y: int, width: int, height: int, *, radius: int, color: Color
) -> None:
    """Fill a rectangle with rounded corners.

    A radius that does not fit is clipped to half the shorter side.
    """
    _ = check_pixel_color(color)
    insets = _corner_insets(min(radius, width // 2, height // 2))
    for row in range(height):
        inset = _row_inset(row, height, insets)
        canvas.span(x + inset, y + row, width - 2 * inset, color)

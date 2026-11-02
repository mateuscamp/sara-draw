# SPDX-License-Identifier: GPL-3.0-only
"""Compare and recolor canvases, pixel by pixel.

Pixels, not bytes: a new encoder can compress the same image differently.

    >>> from ai_draw.grid.canvas import Canvas
    >>> diff(Canvas(2, 2), Canvas(2, 2))
    0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_draw.errors import CanvasError
from ai_draw.grid.arrays import color_mask, count_differing
from ai_draw.grid.canvas import check_color

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ai_draw.grid.canvas import Canvas, Color


def diff(first: Canvas, second: Canvas) -> int:
    """Count the pixels that differ in any channel; both canvases must have the same size."""
    if (first.width, first.height) != (second.width, second.height):
        sizes = f"{first.width}x{first.height} against {second.width}x{second.height}"
        message = f"size {sizes}, expected the same size"
        raise CanvasError(message)
    return count_differing(first.pixels, second.pixels)


def recolor(canvas: Canvas, mapping: Mapping[Color, Color]) -> Canvas:
    """Return a copy with each color in ``mapping`` swapped for its new color; the rest stays.

    Every swap reads the original, so ``{a: b, b: a}`` exchanges the two colors.
    """
    for old, new in mapping.items():
        _ = check_color(old), check_color(new)
    result = canvas.copy()
    for old, new in mapping.items():
        result.pixels[color_mask(canvas.pixels, old)] = new
    return result

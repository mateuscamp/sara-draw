# SPDX-License-Identifier: GPL-3.0-only
"""The one-pixel outline of a silhouette, computed rather than drawn.

A uniform outline ties pieces together; the pixel artist draws it by hand only where the
computed one would eat a thin part.

    >>> from ai_draw.grid.rows import from_rows, to_rows
    >>> ink, skin = (30, 20, 40, 255), (230, 180, 140, 255)
    >>> to_rows(outline(from_rows(["sss", "sss", "sss"], {"s": skin}), ink), {"k": ink, "s": skin})
    ['kkk', 'ksk', 'kkk']
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_draw.grid.arrays import edge_mask, halo_mask, opaque_mask
from ai_draw.grid.canvas import Canvas, check_color

if TYPE_CHECKING:
    from ai_draw.grid.canvas import Color


def outline(canvas: Canvas, ink: Color) -> Canvas:
    """Return a copy with the silhouette's border pixels turned to ``ink``.

    A border pixel is opaque and touches transparency, or the canvas edge, by one of its four
    sides. The outline sits inside the silhouette, so the size does not change.
    """
    _ = check_color(ink)
    result = canvas.copy()
    result.pixels[edge_mask(opaque_mask(canvas.pixels))] = ink
    return result


def outlined(canvas: Canvas, ink: Color) -> Canvas:
    """Return a canvas one pixel larger on every side, ringed in ``ink``.

    Every transparent pixel with an opaque one among its eight neighbors becomes ink, so the
    outline sits outside the silhouette and keeps every pixel of the drawing.
    """
    _ = check_color(ink)
    result = Canvas(canvas.width + 2, canvas.height + 2)
    result.pixels[1:-1, 1:-1] = canvas.pixels
    result.pixels[halo_mask(opaque_mask(canvas.pixels))] = ink
    return result

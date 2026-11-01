# SPDX-License-Identifier: GPL-3.0-only
"""A canvas as rows of characters, one per pixel: the readable form of a small raster.

A failing test prints the drawing it expected and the one it got, and a diff shows the
pixel that changed.

    >>> from ai_draw.grid.canvas import Canvas
    >>> canvas = Canvas(3, 1)
    >>> canvas.paint(1, 0, (255, 0, 0, 255))
    >>> to_rows(canvas, {"r": (255, 0, 0, 255)})
    ['.r.']
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ai_draw.grid.canvas import Canvas, Color

TRANSPARENT_CHAR = "."
UNKNOWN_CHAR = "?"


def to_rows(canvas: Canvas, legend: Mapping[str, Color]) -> list[str]:
    """Write one string per row.

    Each pixel becomes the legend character of its color, ``.`` when it is fully transparent
    and ``?`` when the legend does not name its color.
    """
    chars = {color: char for char, color in legend.items()}
    return [
        "".join(_char(canvas.color_at(x, y), chars) for x in range(canvas.width))
        for y in range(canvas.height)
    ]


def _char(color: Color | None, chars: Mapping[Color, str]) -> str:
    if color is None:
        return UNKNOWN_CHAR
    if color in chars:
        return chars[color]
    return TRANSPARENT_CHAR if color[3] == 0 else UNKNOWN_CHAR

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

from ai_draw.errors import CanvasError
from ai_draw.grid.canvas import Canvas

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ai_draw.grid.canvas import Color

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


def from_rows(rows: Sequence[str], legend: Mapping[str, Color]) -> Canvas:
    """Draw a sprite from a character map: each char is a legend color, ``.`` is transparent.

    Every pixel is a readable decision, and a change shows up in the diff. The tool for the
    small detail, where no rule replaces choosing pixel by pixel.

    >>> to_rows(from_rows([".r.", "rrr"], {"r": (200, 0, 0, 255)}), {"r": (200, 0, 0, 255)})
    ['.r.', 'rrr']
    """
    _check_map(rows, legend)
    canvas = Canvas(len(rows[0]), len(rows))
    for y, row in enumerate(rows):
        for x in (x for x, char in enumerate(row) if char != TRANSPARENT_CHAR):
            canvas.paint(x, y, legend[row[x]])
    return canvas


def _check_map(rows: Sequence[str], legend: Mapping[str, Color]) -> None:
    if not rows:
        message = "no rows, expected at least one row of characters"
        raise CanvasError(message)
    if TRANSPARENT_CHAR in legend:
        message = f"legend uses {TRANSPARENT_CHAR!r}, which always means transparent"
        raise CanvasError(message)
    width = len(rows[0])
    for y, row in enumerate(rows):
        if len(row) != width:
            message = f"row {y} has {len(row)} columns, expected {width}: {row!r}"
            raise CanvasError(message)
        unknown = sorted(set(row) - set(legend) - {TRANSPARENT_CHAR})
        if unknown:
            message = f"char {unknown[0]!r} in row {y} has no color in the legend"
            raise CanvasError(message)


def _char(color: Color | None, chars: Mapping[Color, str]) -> str:
    if color is None:
        return UNKNOWN_CHAR
    if color in chars:
        return chars[color]
    return TRANSPARENT_CHAR if color[3] == 0 else UNKNOWN_CHAR

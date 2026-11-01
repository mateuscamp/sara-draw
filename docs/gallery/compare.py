# SPDX-License-Identifier: GPL-3.0-only
"""The README's picture: four shapes (columns) drawn four ways (rows).

Rows, top to bottom: skimage.draw, raw raster, ai-draw pixel, ai-draw smooth. Columns: a
one-pixel circle, a one-pixel 1:2 line, a two-pixel wave and an even-odd star::

    uv run ai-draw render docs/gallery/compare.py --scale 4
"""

from collections.abc import Callable

from scores import BACK, ENGINES, Engine, blank, circle, line, star, wave

from ai_draw.grid.canvas import Canvas

GAP = 4
ROW_HEIGHT = 32
PANELS: tuple[Callable[[Engine], Canvas], ...] = (
    lambda engine: circle(engine, 12),
    lambda engine: line(engine, 2, steps=12),
    wave,
    star,
)


def _panel_widths() -> list[int]:
    return [panel("pixel").width for panel in PANELS]


def _place(canvas: Canvas, panel: Canvas, x: int, y: int) -> None:
    top = y + (ROW_HEIGHT - panel.height) // 2
    canvas.pixels[top : top + panel.height, x : x + panel.width] = panel.pixels


def draw() -> Canvas:
    """All panels on one sheet."""
    widths = _panel_widths()
    canvas = blank(GAP + sum(w + GAP for w in widths), GAP + len(ENGINES) * (ROW_HEIGHT + GAP))
    canvas.rect(0, 0, canvas.width, canvas.height, BACK)
    for row, engine in enumerate(ENGINES):
        x = GAP
        for panel, width in zip(PANELS, widths, strict=True):
            _place(canvas, panel(engine), x, GAP + row * (ROW_HEIGHT + GAP))
            x += width + GAP
    return canvas

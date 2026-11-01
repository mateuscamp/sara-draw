# SPDX-License-Identifier: GPL-3.0-only
"""A potion bottle drawn pixel by pixel from a character map, outlined by the library.

Small detail is where no rule replaces choosing each pixel, so the map is the drawing; the
library only adds the one-pixel outline around the silhouette::

    uv run ai-draw render examples/potion.py --scale 10
    uv run ai-draw watch examples/potion.py --scale 10
"""

from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.outline import outline
from ai_draw.grid.rows import from_rows

INK: Color = (34, 28, 40, 255)
LEGEND: dict[str, Color] = {
    "c": (150, 100, 62, 255),  # cork
    "g": (172, 206, 226, 255),  # glass
    "w": (248, 248, 240, 255),  # glint, top left: the light comes from there
    "l": (96, 196, 120, 255),  # potion
    "L": (52, 132, 92, 255),  # potion in shadow, bottom right
}
BOTTLE = (
    "....cccc....",
    "....cccc....",
    "....gggg....",
    "....gggg....",
    "...gggggg...",
    "..gwgggggg..",
    ".gwgggggggg.",
    ".gllllllllg.",
    "glwlllllllLg",
    "glllllllllLg",
    "glllllllllLg",
    "glllllllLLLg",
    ".gllllllLLg.",
    "..gLLLLLLg..",
    "...gggggg...",
)


def draw() -> Canvas:
    """The bottle with its outline, 12 by 15 pixels."""
    return outline(from_rows(BOTTLE, LEGEND), INK)

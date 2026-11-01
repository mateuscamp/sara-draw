# SPDX-License-Identifier: GPL-3.0-only
"""A potion bottle drawn pixel by pixel from a character map, outlined by the library.

Small detail is where no rule replaces choosing each pixel, so the map is the drawing; the
library only adds the one-pixel outline around the silhouette::

    uv run ai-draw render examples/pixel/potion.py --scale 10
    uv run ai-draw watch examples/pixel/potion.py --scale 10
"""

from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.outline import outline
from ai_draw.grid.palette import Family, Palette
from ai_draw.grid.rows import from_rows

# The closed palette: every color the bottle may use, by material and role.
INK = Family.of("ink", ["221c28 outline"])
CORK = Family.of("cork", ["96643e base"])
GLASS = Family.of("glass", ["accee2 base", "f8f8f0 glint, top left: the light comes from there"])
POTION = Family.of("potion", ["60c478 base", "34845c shadow, bottom right"])
PALETTE = Palette((INK, CORK, GLASS, POTION))


def _color(family: Family, index: int = 0) -> Color:
    return family.swatches[index].color


LEGEND: dict[str, Color] = {
    "c": _color(CORK),
    "g": _color(GLASS),
    "w": _color(GLASS, 1),
    "l": _color(POTION),
    "L": _color(POTION, 1),
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
    return outline(from_rows(BOTTLE, LEGEND), _color(INK))

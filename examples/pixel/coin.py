# SPDX-License-Identifier: GPL-3.0-only
"""A gold coin drawn with vectors and rasterized as pixel art.

No pixel here is placed by hand: a disc, a crescent of shadow, a star, a glint and a
one-pixel rim, all paths. The pixel output keeps the rim free of L corners and mirrored, and
every color comes from the closed palette::

    uv run ai-draw render examples/pixel/coin.py --scale 10
    uv run ai-draw lint examples/pixel/coin.py --line '#26202e'
"""

import math

from ai_draw.geometry.path import Path, ellipse, polygon
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.palette import Family, Palette
from ai_draw.pixel.fill import fill
from ai_draw.pixel.stroke import stroke

INK = Family.of("ink", ["26202e outline"])
GOLD = Family.of("gold", ["e8b13c base", "b97a26 shadow, bottom right", "fbe58a light"])
PALETTE = Palette((INK, GOLD))


def _color(family: Family, index: int = 0) -> Color:
    return family.swatches[index].color


def star(cx: float, cy: float, radius: float) -> Path:
    """Five tips in one stroke, the first pointing up."""
    tips = [math.radians(-90 + tip * 144) for tip in range(5)]
    return polygon([(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in tips])


def draw() -> Canvas:
    """The coin, 24 by 24 pixels."""
    canvas = Canvas(24, 24)
    fill(canvas, ellipse(12, 12, 10), _color(GOLD, 1))
    # The face, nudged up and left, leaves the shadow as a crescent at the bottom right.
    fill(canvas, ellipse(11.5, 11.5, 9), _color(GOLD))
    fill(canvas, star(12, 12, 6), _color(GOLD, 2))
    stroke(canvas, Path().move_to(5.5, 11.5).quad_to(6, 6, 10.5, 5.5), _color(GOLD, 2), 1)
    stroke(canvas, ellipse(12, 12, 10), _color(INK), 1)
    return canvas

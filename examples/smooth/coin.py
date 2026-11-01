# SPDX-License-Identifier: GPL-3.0-only
"""The gold coin of ``examples/pixel/coin.py``, the same paths four times larger, smooth.

The smooth output gives every edge pixel the share of its area inside the shape, so the
same geometry reads as vector art instead of pixel art::

    uv run ai-draw render examples/smooth/coin.py
"""

import math

from ai_draw.geometry.path import Path, ellipse, polygon
from ai_draw.geometry.transform import Transform
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.smooth.coverage import fill
from ai_draw.smooth.stroke import stroke

INK: Color = (38, 32, 46, 255)
GOLD: Color = (232, 177, 60, 255)
SHADOW: Color = (185, 122, 38, 255)
LIGHT: Color = (251, 229, 138, 255)
SCALE = 4


def star(cx: float, cy: float, radius: float) -> Path:
    """Five tips in one stroke, the first pointing up."""
    tips = [math.radians(-90 + tip * 144) for tip in range(5)]
    return polygon([(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in tips])


def draw() -> Canvas:
    """The coin, 96 by 96 pixels."""
    big = Transform.scale(SCALE)
    canvas = Canvas(24 * SCALE, 24 * SCALE)
    fill(canvas, ellipse(12, 12, 10).transformed(big), SHADOW)
    fill(canvas, ellipse(11.5, 11.5, 9).transformed(big), GOLD)
    fill(canvas, star(12, 12, 6).transformed(big), LIGHT)
    glint = Path().move_to(5.5, 11.5).quad_to(6, 6, 10.5, 5.5).transformed(big)
    stroke(canvas, glint, LIGHT, SCALE)
    stroke(canvas, ellipse(12, 12, 10).transformed(big), INK, SCALE)
    return canvas

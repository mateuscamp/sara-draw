# SPDX-License-Identifier: GPL-3.0-only
"""Speckle noise with a fixed seed: random-looking, the same on every run.

>>> from ai_draw.grid.canvas import Canvas
>>> ground = Canvas(16, 16)
>>> speckle(ground, 0, 0, 16, 16, colors=[(90, 70, 50, 255)], chance=0.2, seed=13)
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ai_draw.errors import ColorError, SettingError
from ai_draw.grid.canvas import check_color

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_draw.grid.canvas import Canvas, Color


def speckle(  # noqa: PLR0913  # motivo: an area and three settings
    canvas: Canvas,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    colors: Sequence[Color],
    chance: float,
    seed: int,
) -> None:
    """Paint each pixel of the area, with probability ``chance``, in one of ``colors``.

    The seed is required: the same seed gives the same pixels, row by row from the top.
    """
    if not 0 <= chance <= 1:
        message = f"chance={chance!r}, expected a probability from 0 to 1"
        raise SettingError(message)
    if not colors:
        message = "colors=[], expected at least one color"
        raise ColorError(message)
    palette = [check_color(color) for color in colors]
    rng = random.Random(seed)  # noqa: S311  # motivo: texture, not security
    for row in range(y, y + height):
        for column in range(x, x + width):
            if rng.random() < chance:
                canvas.paint(column, row, rng.choice(palette))

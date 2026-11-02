# SPDX-License-Identifier: GPL-3.0-only
"""PNG files through Pillow, which only reads and writes here, never draws (ADR-0002).

Compare images by pixels, not bytes: a new Pillow may compress the same image differently::

    write_png(canvas, Path("out/scene.png"))
    assert read_png(Path("out/scene.png")).same_pixels(canvas)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from ai_draw.grid.canvas import Canvas

if TYPE_CHECKING:
    from pathlib import Path


def write_png(canvas: Canvas, path: Path) -> None:
    """Save ``canvas`` as an RGBA PNG at ``path``, creating the folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas.pixels).save(path, format="PNG")


# Pillow opens 16-bit gray in these modes and clips it to 255 on the way to RGBA (audit B2).
_WIDE_GRAY = frozenset({"I", "I;16", "I;16B", "I;16L"})


def read_png(path: Path) -> Canvas:
    """Load the image at ``path`` as a canvas; any mode is converted to RGBA."""
    with Image.open(path) as image:
        if image.mode in _WIDE_GRAY:
            # Keep the high byte, as Pillow does for 16-bit color.
            return _canvas_of(image.convert("I").point(lambda value: value / 256).convert("L"))
        return _canvas_of(image)


def _canvas_of(image: Image.Image) -> Canvas:
    return Canvas.from_pixels(np.asarray(image.convert("RGBA"), dtype=np.uint8))

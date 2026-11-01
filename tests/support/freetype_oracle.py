# SPDX-License-Identifier: GPL-3.0-only
# fontTools ships no type information: its pen and array calls are untyped, and the strict
# checker would flag every one. This adapter is the only place that touches it.
# motivo: fontTools has no types (above); this file is the only one that calls it
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportAny=false, reportMissingTypeStubs=false
"""FreeType as the reference for the smooth output: the same path, rasterized by FreeType.

At the picture's own size FreeType flattens curves coarsely: on the bench heart it strays up
to 28/255 from the true coverage (measured 31/10). So the reference draws the path 32 times
larger and averages each 32 x 32 block back into one pixel; that leaves FreeType's own error
under 1/255 (0.73/255 against our coverage on the heart, the same with twice our segments).

FreeType reads y growing upward and returns row 0 at the top, so each point's y is flipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

import numpy as np
from fontTools.pens.freetypePen import FreeTypePen

from ai_draw.geometry.transform import Transform

if TYPE_CHECKING:
    from ai_draw.geometry.path import CommandKind, Path


SUPERSAMPLE = 32


def freetype_coverage(
    path: Path, width: int, height: int, *, evenodd: bool = False
) -> list[list[float]]:
    """The coverage of ``path`` on a ``width`` x ``height`` grid, every contour closed.

    Drawn by FreeType ``SUPERSAMPLE`` times larger and averaged back into each pixel.
    """
    k = SUPERSAMPLE
    big = np.asarray(
        _rasterize(path.transformed(Transform.scale(k)), width * k, height * k, evenodd=evenodd)
    )
    rows: list[list[float]] = big.reshape(height, k, width, k).mean(axis=(1, 3)).tolist()
    return rows


def _rasterize(path: Path, width: int, height: int, *, evenodd: bool) -> list[list[float]]:
    pen = FreeTypePen(None)
    left_open = False
    for command in path.commands:
        # FreeType closes a contour before the next starts; ai-draw fills every contour closed.
        if command.kind == "move" and left_open:
            pen.closePath()
        flipped = [(x, height - y) for x, y in command.points]
        left_open = _replay(pen, command.kind, flipped)
    if left_open:
        pen.closePath()
    rows: list[list[float]] = pen.array(width=width, height=height, evenOdd=evenodd).tolist()
    return rows


def _replay(pen: FreeTypePen, kind: CommandKind, points: list[tuple[float, float]]) -> bool:
    """Send one command to the pen; return whether a contour is left open."""
    match kind:
        case "move":
            pen.moveTo(points[0])
        case "line":
            pen.lineTo(points[0])
        case "quad":
            pen.qCurveTo(*points)
        case "cubic":
            pen.curveTo(*points)
        case "close":
            pen.closePath()
            return False
        case _:
            assert_never(kind)
    return True

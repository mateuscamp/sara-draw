# SPDX-License-Identifier: GPL-3.0-only
# fontTools ships no type information: its pen and array calls are untyped, and the strict
# checker would flag every one. This adapter is the only place that touches it.
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

from typing import TYPE_CHECKING

import numpy as np
from fontTools.pens.freetypePen import FreeTypePen

from ai_draw.geometry.transform import Transform

if TYPE_CHECKING:
    from ai_draw.geometry.path import Path, Point


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

    def flip(point: Point) -> tuple[float, float]:
        return point[0], height - point[1]

    started = False
    for command in path.commands:
        points = [flip(point) for point in command.points]
        if command.kind == "move":
            if started:
                pen.closePath()
            pen.moveTo(points[0])
            started = True
        elif command.kind == "line":
            pen.lineTo(points[0])
        elif command.kind == "quad":
            pen.qCurveTo(*points)
        elif command.kind == "cubic":
            pen.curveTo(*points)
        else:
            pen.closePath()
            started = False
    if started:
        pen.closePath()
    rows: list[list[float]] = pen.array(width=width, height=height, evenOdd=evenodd).tolist()
    return rows

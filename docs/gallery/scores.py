# SPDX-License-Identifier: GPL-3.0-only
"""The README's comparison: the same shapes drawn four ways, and the defects each way leaves.

- skimage.draw: a classic raster library (Bresenham line and circle, Bezier, polygon fill);
  it has no stroke width, so its wave is one pixel wide and is not counted.
- raw raster: the stroke outline of ai-draw filled by sampling pixel centers, with no rule:
  what a vector library gives with antialiasing switched off.
- ai-draw pixel: the pixel output.
- ai-draw smooth: the smooth output, in the picture only; it has no pixel defects to count.

Print the README table::

    uv run python docs/gallery/scores.py
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import Literal, SupportsInt

from skimage import draw as skdraw

from ai_draw.geometry.path import FillRule, Path, ellipse, polygon
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.pixel import fill as pixel_fill
from ai_draw.pixel import stroke as pixel_stroke
from ai_draw.pixel.defects import (
    Cells,
    cells_of,
    components,
    l_corners,
    thickness_defects,
    uneven_steps,
    wobble,
)
from ai_draw.smooth import coverage as smooth_fill
from ai_draw.smooth import stroke as smooth_stroke
from ai_draw.smooth.stroke import stroke_outline

Engine = Literal["skimage", "raw", "pixel", "smooth"]
ENGINES: tuple[Engine, ...] = ("skimage", "raw", "pixel", "smooth")
COUNTED: tuple[Engine, ...] = ("skimage", "raw", "pixel")
NAMES = {"skimage": "skimage.draw", "raw": "raw raster", "pixel": "ai-draw pixel"}
INK: Color = (240, 230, 210, 255)
BACK: Color = (30, 34, 48, 255)


def blank(width: int, height: int) -> Canvas:
    """A canvas painted with the background color."""
    canvas = Canvas(width, height)
    canvas.rect(0, 0, width, height, BACK)
    return canvas


def _paint(canvas: Canvas, rows: Iterable[SupportsInt], columns: Iterable[SupportsInt]) -> None:
    for y, x in zip(rows, columns, strict=True):
        canvas.paint(int(x), int(y), INK)


def _raw_fill(canvas: Canvas, path: Path, rule: FillRule = "nonzero") -> None:
    for span in pixel_fill.spans(path.contours(), rule, canvas.height):
        canvas.span(span.x, span.y, span.length, INK)


def _draw(engine: Engine, canvas: Canvas, path: Path, width: int) -> None:
    """Stroke ``path`` with every engine but skimage, which the shapes draw themselves."""
    if engine == "raw":
        _raw_fill(canvas, stroke_outline(path, width))
    elif engine == "pixel":
        pixel_stroke.stroke(canvas, path, INK, width)
    elif engine == "smooth":
        smooth_stroke.stroke(canvas, path, INK, width)


def circle(engine: Engine, radius: int) -> Canvas:
    """A one-pixel circle; skimage centers it on a pixel, the others on a pixel corner."""
    center = radius + 3
    canvas = blank(2 * center, 2 * center)
    if engine == "skimage":
        _paint(canvas, *skdraw.circle_perimeter(center, center, radius))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]  # motivo: skimage ships no types
    else:
        _draw(engine, canvas, ellipse(center, center, radius), 1)
    return canvas


def line(engine: Engine, run: int, *, steep: bool = False, steps: int = 4) -> Canvas:
    """A one-pixel 1:``run`` line through pixel centers, wide or (``steep``) tall."""
    long, short = steps * run, steps
    width, height = (short + 3, long + 3) if steep else (long + 3, short + 3)
    canvas = blank(width, height)
    end = (1 + short, 1 + long) if steep else (1 + long, 1 + short)
    if engine == "skimage":
        _paint(canvas, *skdraw.line(1, 1, end[1], end[0]))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]  # motivo: skimage ships no types
    else:
        _draw(engine, canvas, Path().move_to(1.5, 1.5).line_to(end[0] + 0.5, end[1] + 0.5), 1)
    return canvas


WAVE_POINTS = ((3, 16), (9, 6), (15, 16), (21, 26), (27, 16), (33, 6), (39, 16), (45, 26), (51, 16))


def wave(engine: Engine) -> Canvas:
    """Two periods of a quadratic wave, two pixels wide (one for skimage, which has no width)."""
    canvas = blank(54, 32)
    if engine == "skimage":
        for i in range(0, len(WAVE_POINTS) - 2, 2):
            (x0, y0), (x1, y1), (x2, y2) = WAVE_POINTS[i : i + 3]
            _paint(canvas, *skdraw.bezier_curve(y0, x0, y1, x1, y2, x2, 1))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]  # motivo: skimage ships no types
        return canvas
    path = Path().move_to(*WAVE_POINTS[0])
    for i in range(1, len(WAVE_POINTS) - 1, 2):
        path = path.quad_to(*WAVE_POINTS[i], *WAVE_POINTS[i + 1])
    _draw(engine, canvas, path, 2)
    return canvas


def star(engine: Engine) -> Canvas:
    """Five tips in one stroke, filled "evenodd": the middle pentagon is hollow."""
    tips = [math.radians(-90 + tip * 144) for tip in range(5)]
    points = [(16 + 14 * math.cos(a), 16 + 14 * math.sin(a)) for a in tips]
    canvas = blank(32, 32)
    if engine == "skimage":
        # skimage samples pixel (x, y) at the point (x, y); ai-draw at (x + 0.5, y + 0.5)
        rows = [y - 0.5 for _, y in points]
        columns = [x - 0.5 for x, _ in points]
        _paint(canvas, *skdraw.polygon(rows, columns, (32, 32)))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]  # motivo: skimage ships no types
    elif engine == "raw":
        _raw_fill(canvas, polygon(points), "evenodd")
    elif engine == "pixel":
        pixel_fill.fill(canvas, polygon(points), INK, "evenodd")
    else:
        smooth_fill.fill(canvas, polygon(points), INK, "evenodd")
    return canvas


def ink(canvas: Canvas) -> Cells:
    """The cells of the drawing's color."""
    return cells_of(canvas, INK)


def _lines(engine: Engine) -> list[Cells]:
    return [ink(line(engine, run, steep=steep)) for run in range(1, 7) for steep in (False, True)]


def _circles(engine: Engine) -> list[Cells]:
    return [ink(circle(engine, radius)) for radius in range(3, 17)]


Check = Callable[[Engine], int | None]
CHECKS: tuple[tuple[str, str, Check], ...] = (
    ("1-px circles, r 3-16", "L corners", lambda e: sum(map(l_corners, _circles(e)))),
    ("1-px circles, r 3-16", "wobble", lambda e: sum(wobble(c, 1) for c in _circles(e))),
    ("1-px circles, r 3-16", "extra pieces", lambda e: sum(components(c) - 1 for c in _circles(e))),
    ("1-px lines, 1:1 to 1:6", "L corners", lambda e: sum(map(l_corners, _lines(e)))),
    ("1-px lines, 1:1 to 1:6", "uneven steps", lambda e: sum(map(uneven_steps, _lines(e)))),
    ("2-px wave", "wobble", lambda e: None if e == "skimage" else wobble(ink(wave(e)), 2)),
    (
        "2-px wave",
        "thickness",
        lambda e: None if e == "skimage" else thickness_defects(ink(wave(e)), 2),
    ),
    ("even-odd star", "extra pieces", lambda e: components(ink(star(e))) - 1),
)


def markdown() -> str:
    """The README table: each check counted for each engine; 0 is clean."""
    header = "| shape | check | " + " | ".join(NAMES[e] for e in COUNTED) + " |"
    lines = [header, "|---|---|" + "---:|" * len(COUNTED)]
    for shape, check, count in CHECKS:
        cells = ["—" if (n := count(e)) is None else str(n) for e in COUNTED]
        lines.append(f"| {shape} | {check} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(markdown())

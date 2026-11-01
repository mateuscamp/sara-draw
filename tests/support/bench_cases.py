# SPDX-License-Identifier: GPL-3.0-only
"""The fixed bench: shapes judged by the craft rules, measured by ``ai_draw.pixel.defects``.

Every metric is 0 on clean pixel art. ``measure()`` gives the score that
``tests/bench/score.json`` records; a later phase that improves the rasterizer lowers it.
The shapes are drawn with today's public API, so the bench measures what a user gets.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING

from ai_draw.geometry.path import Path, ellipse, polygon, rect
from ai_draw.geometry.transform import Transform
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.pixel.defects import (
    Cells,
    asymmetric_cells,
    cells_of,
    components,
    l_corners,
    orphans,
    thickness_defects,
    uneven_steps,
    wobble,
)
from ai_draw.pixel.fill import FillRule, fill
from ai_draw.pixel.stroke import stroke

if TYPE_CHECKING:
    from collections.abc import Callable

INK: Color = (20, 20, 20, 255)
Score = dict[str, int]


def filled(size: tuple[int, int], path: Path, rule: FillRule = "nonzero") -> Cells:
    canvas = Canvas(*size)
    fill(canvas, path, INK, rule)
    return cells_of(canvas)


def stroked(size: tuple[int, int], path: Path, width: int) -> Cells:
    canvas = Canvas(*size)
    stroke(canvas, path, INK, width)
    return cells_of(canvas)


def star(cx: float, cy: float, radius: float) -> Path:
    """Five tips in one stroke: "evenodd" leaves the middle pentagon hollow."""
    tips = [math.radians(-90 + tip * 144) for tip in range(5)]
    return polygon([(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in tips])


def heart() -> Path:
    """Four cubics, mirror images around x = 16."""
    return (
        Path()
        .move_to(16, 10)
        .cubic_to(14, 5, 5, 4, 4, 12)
        .cubic_to(4, 19, 12, 24, 16, 28)
        .cubic_to(20, 24, 28, 19, 28, 12)
        .cubic_to(27, 4, 18, 5, 16, 10)
        .close()
    )


def wave() -> Path:
    """Two periods of a quadratic wave."""
    return (
        Path()
        .move_to(3, 16)
        .quad_to(9, 6, 15, 16)
        .quad_to(21, 26, 27, 16)
        .quad_to(33, 6, 39, 16)
        .quad_to(45, 26, 51, 16)
    )


def shape_score(cells: Cells) -> Score:
    return {"extra_components": max(0, components(cells) - 1), "orphans": orphans(cells)}


def line_score(cells: Cells, width: int) -> Score:
    return {
        **shape_score(cells),
        "thickness": thickness_defects(cells, width),
        "wobble": wobble(cells, width),
    }


def total(scores: list[Score]) -> Score:
    summed: Counter[str] = Counter()
    for score in scores:
        summed.update(score)
    return {metric: summed[metric] for metric in sorted(summed)}


def star_evenodd() -> Score:
    return shape_score(filled((32, 32), star(16, 16, 14), "evenodd"))


def star_nonzero() -> Score:
    cells = filled((32, 32), star(16, 16, 14))
    return {**shape_score(cells), "asymmetry": asymmetric_cells(cells, mirror_x=16)}


def heart_fill() -> Score:
    cells = filled((32, 32), heart())
    return {**shape_score(cells), "asymmetry": asymmetric_cells(cells, mirror_x=16)}


def circle_fill(radius: int) -> Score:
    center = radius + 2
    cells = filled((2 * center, 2 * center), ellipse(center, center, radius))
    asymmetry = asymmetric_cells(cells, mirror_x=center, mirror_y=center)
    return {**shape_score(cells), "asymmetry": asymmetry}


def circle_stroke(radius: int) -> Score:
    center = radius + 3
    cells = stroked((2 * center, 2 * center), ellipse(center, center, radius), 1)
    asymmetry = asymmetric_cells(cells, mirror_x=center, mirror_y=center)
    return {**line_score(cells, 1), "asymmetry": asymmetry, "l_corners": l_corners(cells)}


def straight_line(run: int, *, steep: bool) -> Score:
    """A 1:run line through pixel centers, wide or (``steep``) tall."""
    start, end = (1.5, 1.5), (1.5 + 4 * run, 5.5)
    size = (4 * run + 3, 7)
    if steep:
        (start, end), size = ((1.5, 1.5), (5.5, 1.5 + 4 * run)), (7, 4 * run + 3)
    cells = stroked(size, Path().move_to(*start).line_to(*end), 1)
    steps = {"l_corners": l_corners(cells), "uneven_steps": uneven_steps(cells)}
    return {**line_score(cells, 1), **steps}


def diamond_stroke() -> Score:
    turned = Transform.rotate(45).then(Transform.translate(16, 16))
    cells = stroked((32, 32), rect(-8, -8, 16, 16).transformed(turned), 1)
    asymmetry = asymmetric_cells(cells, mirror_x=16, mirror_y=16)
    return {**line_score(cells, 1), "asymmetry": asymmetry, "l_corners": l_corners(cells)}


def wave_stroke() -> Score:
    return line_score(stroked((54, 32), wave(), 2), 2)


CASES: dict[str, Callable[[], Score]] = {
    "star_fill_evenodd": star_evenodd,
    "star_fill_nonzero": star_nonzero,
    "heart_fill": heart_fill,
    "circle_fill_r2_to_r16": lambda: total([circle_fill(r) for r in range(2, 17)]),
    "circle_stroke_1px_r3_to_r16": lambda: total([circle_stroke(r) for r in range(3, 17)]),
    "lines_1px_1to1_to_1to6": lambda: total(
        [straight_line(run, steep=steep) for run in range(1, 7) for steep in (False, True)]
    ),
    "diamond_stroke_1px": diamond_stroke,
    "wave_stroke_2px": wave_stroke,
}


def measure() -> dict[str, Score]:
    """The score of every case, by case name."""
    return {name: case() for name, case in CASES.items()}


def _verdict(before: int | None, after: int | None) -> str:
    if before is None:
        return "new"
    if after is None:
        return "gone"
    return "worse" if after > before else "better"


def differences(recorded: dict[str, Score], measured: dict[str, Score]) -> list[str]:
    """One line per metric that changed, saying if it got worse or better."""
    lines: list[str] = []
    for case in sorted(recorded.keys() | measured.keys()):
        old, new = recorded.get(case, {}), measured.get(case, {})
        for metric in sorted(old.keys() | new.keys()):
            before, after = old.get(metric), new.get(metric)
            if before != after:
                lines.append(f"{case}.{metric}: {before} -> {after} ({_verdict(before, after)})")
    return lines


def worse(recorded: dict[str, Score], measured: dict[str, Score]) -> list[str]:
    """The changes that would raise the score: the ratchet refuses them."""
    return [line for line in differences(recorded, measured) if line.endswith("(worse)")]

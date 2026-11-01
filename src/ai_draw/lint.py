# SPDX-License-Identifier: GPL-3.0-only
"""Lint a picture against the pixel artist's rules, whoever drew it: by hand, by an AI, or here.

Every check is a count that is 0 on clean pixel art, so ``ai-draw lint`` can fail a build:

- half alpha: pixels neither transparent nor opaque (pixel art has no half tones);
- loose pixels: opaque pixels with none of their eight neighbors opaque;
- near colors: opaque colors at most ``near`` apart on every channel (one of them is a slip);

and, given the color of a line (the outline, say) and its width, the line checks of
``ai_draw.pixel.defects``: L corners, wobble, thickness and extra pieces.

    >>> from ai_draw.grid.rows import from_rows
    >>> legend = {"k": (30, 20, 40, 255), "s": (230, 180, 140, 255)}
    >>> sprite = from_rows([".kk.", "kssk", ".kk."], legend)
    >>> [finding.count for finding in lint(sprite)]
    [0, 0, 0]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_draw.grid.palette import collect, near_pairs, to_hex
from ai_draw.pixel.defects import (
    cells_of,
    components,
    l_corners,
    orphans,
    thickness_defects,
    wobble,
)

if TYPE_CHECKING:
    from ai_draw.grid.canvas import Canvas, Color

_OPAQUE = 255


@dataclass(frozen=True, slots=True)
class Finding:
    """One check: its name, how many times it failed (0 is clean), and which, when it says."""

    check: str
    count: int
    detail: str


def _half_alpha(canvas: Canvas) -> Finding:
    count = sum(use.pixels for use in collect({"picture": canvas}) if 0 < use.color[3] < _OPAQUE)
    return Finding("half alpha", count, "")


def _loose(canvas: Canvas) -> Finding:
    opaque = frozenset(
        cell for cell in cells_of(canvas) if (canvas.color_at(*cell) or (0, 0, 0, 0))[3] == _OPAQUE
    )
    return Finding("loose pixels", orphans(opaque), "")


def _near(canvas: Canvas, tolerance: int) -> Finding:
    colors = [use.color for use in collect({"picture": canvas}) if use.color[3] == _OPAQUE]
    pairs = near_pairs(colors, tolerance)
    detail = ", ".join(f"{to_hex(first)} {to_hex(second)}" for first, second in pairs)
    return Finding("near colors", len(pairs), detail)


def _line(canvas: Canvas, color: Color, width: int) -> list[Finding]:
    cells = cells_of(canvas, color)
    return [
        Finding("L corners", l_corners(cells), ""),
        Finding("wobble", wobble(cells, width), ""),
        Finding("thickness", thickness_defects(cells, width), ""),
        Finding("extra pieces", max(0, components(cells) - 1), ""),
    ]


def lint(
    canvas: Canvas, *, line: Color | None = None, width: int = 1, near: int = 10
) -> list[Finding]:
    """Check ``canvas``; ``line`` and ``width`` add the checks of a line of that color."""
    findings = [_half_alpha(canvas), _loose(canvas), _near(canvas, near)]
    if line is not None:
        findings.extend(_line(canvas, line, width))
    return findings

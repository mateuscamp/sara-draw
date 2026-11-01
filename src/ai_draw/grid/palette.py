# SPDX-License-Identifier: GPL-3.0-only
"""Closed palette in families: each color with its role, and nothing outside it.

A palette is a list of materials (cloth, wood, skin...), each with its base, its shadow and,
when there is one, its highlight. New art uses only the list; a new color enters a family.
The tools around it find what a set of pictures really uses, the pairs that are almost the
same color, and fold those within a family without erasing the tones of any one picture.

    >>> wood = Family.of("wood", ["8a5a34 base", "5e3a22 shadow"])
    >>> palette = Palette((wood,))
    >>> [to_hex(color) for color in palette.colors]
    ['#8a5a34', '#5e3a22']
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_draw.grid.arrays import color_counts, color_mask
from ai_draw.grid.canvas import CLEAR

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ai_draw.grid.canvas import Canvas, Color

_HEX = re.compile(r"#?([0-9a-fA-F]{6})([0-9a-fA-F]{2})?")
# Below this alpha a pixel quantizes to transparent: the pixel output has alpha 0 or 255 only.
_OPAQUE_FROM = 128


def parse_hex(text: str) -> Color:
    """Read ``#rrggbb`` or ``#rrggbbaa`` (the ``#`` is optional); no alpha means opaque."""
    match = _HEX.fullmatch(text.strip())
    if match is None:
        message = f"hex={text!r}, expected #rrggbb or #rrggbbaa"
        raise ValueError(message)
    rgb, alpha = match.group(1), match.group(2)
    r, g, b = (int(rgb[i : i + 2], 16) for i in (0, 2, 4))
    return r, g, b, int(alpha, 16) if alpha else 255


def to_hex(color: Color) -> str:
    """Write ``#rrggbb``, with ``aa`` appended only when the color is not opaque."""
    r, g, b, a = color
    return f"#{r:02x}{g:02x}{b:02x}" + ("" if a == 255 else f"{a:02x}")  # noqa: PLR2004 - opaque


@dataclass(frozen=True, slots=True)
class Swatch:
    """A color and the role it plays in a picture: base, shadow, highlight, or what it paints."""

    color: Color
    role: str


@dataclass(frozen=True, slots=True)
class Family:
    """The tones of one material."""

    name: str
    swatches: tuple[Swatch, ...]

    @staticmethod
    def of(name: str, entries: Sequence[str]) -> Family:
        """Build a family from entries written ``"rrggbb role"``."""
        swatches: list[Swatch] = []
        for entry in entries:
            code, _, role = entry.strip().partition(" ")
            if not role.strip():
                message = f"family {name!r}: entry {entry!r}, expected 'rrggbb role'"
                raise ValueError(message)
            swatches.append(Swatch(parse_hex(code), role.strip()))
        return Family(name, tuple(swatches))


def _redmean(first: Color, second: Color) -> float:
    """Squared color distance weighted for the eye (the "redmean" approximation)."""
    mean = (first[0] + second[0]) / 2
    dr, dg, db = (first[i] - second[i] for i in range(3))
    return (2 + mean / 256) * dr * dr + 4 * dg * dg + (2 + (255 - mean) / 256) * db * db


@dataclass(frozen=True, slots=True)
class Palette:
    """The closed palette: every color of every family, each color in exactly one family."""

    families: tuple[Family, ...]

    def __post_init__(self) -> None:
        """Refuse a color listed in two families: its material would be ambiguous."""
        owner: dict[Color, str] = {}
        for family in self.families:
            for swatch in family.swatches:
                if swatch.color in owner:
                    names = f"{owner[swatch.color]!r} and {family.name!r}"
                    message = f"color {to_hex(swatch.color)} in {names}, expected one family"
                    raise ValueError(message)
                owner[swatch.color] = family.name

    @property
    def colors(self) -> tuple[Color, ...]:
        """Every color, family by family, in the order written."""
        return tuple(swatch.color for family in self.families for swatch in family.swatches)

    def family_of(self, color: Color) -> Family | None:
        """The family that lists ``color``, or None."""
        return next((f for f in self.families if color in {s.color for s in f.swatches}), None)

    def foreign(self, canvas: Canvas) -> list[Color]:
        """The opaque colors of ``canvas`` outside the palette, most used first."""
        counts = color_counts(canvas.pixels)
        allowed = set(self.colors)
        outside = [color for color in counts if color[3] != 0 and color not in allowed]
        return sorted(outside, key=lambda color: (-counts[color], color))

    def nearest(self, color: Color) -> Color:
        """The palette color closest to ``color`` to the eye; ties go to the first listed."""
        if not self.colors:
            message = "palette has no colors, expected at least one family with a swatch"
            raise ValueError(message)
        return min(self.colors, key=lambda candidate: _redmean(candidate, color))

    def quantize(self, canvas: Canvas) -> Canvas:
        """Return a copy painted only with palette colors and hard alpha, without dithering.

        Each pixel takes the nearest palette color; one below half alpha becomes transparent.
        """
        result = canvas.copy()
        for color in color_counts(canvas.pixels):
            target = CLEAR if color[3] < _OPAQUE_FROM else self.nearest(color)
            if target != color:
                result.pixels[color_mask(canvas.pixels, color)] = target
        return result


@dataclass(frozen=True, slots=True)
class ColorUse:
    """A color in use: how many opaque pixels, and in which pictures."""

    color: Color
    pixels: int
    pieces: tuple[str, ...]


def collect(pieces: Mapping[str, Canvas]) -> list[ColorUse]:
    """The opaque colors that the named pictures use, most used first; ties by color."""
    totals: dict[Color, int] = {}
    names: dict[Color, list[str]] = {}
    for name in sorted(pieces):
        for color, count in color_counts(pieces[name].pixels).items():
            if color[3] != 0:
                totals[color] = totals.get(color, 0) + count
                names.setdefault(color, []).append(name)
    ordered = sorted(totals, key=lambda color: (-totals[color], color))
    return [ColorUse(color, totals[color], tuple(names[color])) for color in ordered]


def distance(first: Color, second: Color) -> int:
    """The largest difference of one channel, red, green or blue; alpha does not count."""
    return max(abs(first[i] - second[i]) for i in range(3))


def near_pairs(colors: Sequence[Color], tolerance: int) -> list[tuple[Color, Color]]:
    """The pairs, in list order, whose ``distance`` is at most ``tolerance``."""
    return [
        (first, second)
        for index, first in enumerate(colors)
        for second in colors[index + 1 :]
        if distance(first, second) <= tolerance
    ]


def _group_for(
    groups: list[list[ColorUse]], use: ColorUse, tolerance: int
) -> list[ColorUse] | None:
    """The first group whose owner is close enough and that shares no picture with ``use``."""
    for group in groups:
        close = distance(group[0].color, use.color) <= tolerance
        if close and not any(set(member.pieces) & set(use.pieces) for member in group):
            return group
    return None


def merge(palette: Palette, used: Sequence[ColorUse], tolerance: int) -> dict[Color, Color]:
    """Fold near colors within each family; return which color goes into which.

    Colors go, most used first, to the first more used color of the same family within
    ``tolerance``, unless one picture uses both: every picture keeps its number of tones.
    """
    groups: dict[str, list[list[ColorUse]]] = {}
    folded: dict[Color, Color] = {}
    for use in used:
        family = palette.family_of(use.color)
        if family is None:
            message = f"color {to_hex(use.color)} in {', '.join(use.pieces)} has no family"
            raise ValueError(message)
        family_groups = groups.setdefault(family.name, [])
        group = _group_for(family_groups, use, tolerance)
        if group is None:
            family_groups.append([use])
        else:
            group.append(use)
            folded[use.color] = group[0].color
    return folded

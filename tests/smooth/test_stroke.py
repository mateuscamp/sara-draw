# SPDX-License-Identifier: GPL-3.0-only
import math

import pytest

from ai_draw.geometry.path import Path, Point, ellipse
from ai_draw.smooth.coverage import coverage
from ai_draw.smooth.stroke import stroke_outline
from bench_cases import wave
from freetype_oracle import freetype_coverage

ONE_STEP = 1 / 255


def area(rows: list[list[float]]) -> float:
    return sum(sum(row) for row in rows)


def test_straight_stroke_is_a_band_with_round_caps() -> None:
    rows = coverage(stroke_outline(Path().move_to(2, 3).line_to(8, 3), 2), 10, 6)
    assert rows[2][5] == pytest.approx(1)
    assert rows[3][5] == pytest.approx(1)
    assert rows[1][5] == pytest.approx(0)
    assert area(rows) == pytest.approx(6 * 2 + math.pi, abs=0.02)


def test_closed_stroke_is_a_ring() -> None:
    rows = coverage(stroke_outline(ellipse(12, 12, 8), 2), 24, 24)
    assert rows[12][12] == pytest.approx(0)
    assert area(rows) == pytest.approx(math.pi * (9 * 9 - 7 * 7), rel=0.002)


@pytest.mark.parametrize(
    "corner",
    [((2, 3), (12, 3), (12, 13)), ((2, 13), (12, 13), (12, 3))],
    ids=["turning_down", "turning_up"],
)
def test_sharp_turn_is_round_outside_and_sharp_inside(corner: tuple[Point, Point, Point]) -> None:
    # Two legs of 10 and a 2-pixel width: the legs overlap in a 1 x 1 square at the inner
    # corner, the outer corner is a quarter disc, and the two caps are half discs.
    start, middle, end = corner
    rows = coverage(
        stroke_outline(Path().move_to(*start).line_to(*middle).line_to(*end), 2), 16, 16
    )
    assert area(rows) == pytest.approx(39 + 1.25 * math.pi, abs=0.03)


@pytest.mark.parametrize(("turn_degrees", "width"), [(120, 3), (135, 3), (150, 2)])
def test_a_sharp_turn_keeps_the_inner_corner_filled(turn_degrees: float, width: float) -> None:
    # Regression (audit A2, 01/11): past about 120 degrees the inner corner was clamped and
    # left a notch. Two legs of 14 swept by a disc of radius r turning by t cover exactly
    # 2r(L1 + L2) + pi r^2 + r^2 (t/2 - tan(t/2)), while the overlap fits on the legs.
    turn, r = math.radians(turn_degrees), width / 2
    end = (20 + 14 * math.cos(turn), 20 - 14 * math.sin(turn))
    rows = coverage(
        stroke_outline(Path().move_to(6, 20).line_to(20, 20).line_to(*end), width), 40, 40
    )
    exact = 2 * r * 28 + math.pi * r * r + r * r * (turn / 2 - math.tan(turn / 2))
    assert area(rows) == pytest.approx(exact, abs=0.05)


def test_stroke_outline_matches_freetype_within_one_step() -> None:
    outline = stroke_outline(wave(), 2)
    ours = coverage(outline, 54, 32)
    reference = freetype_coverage(outline, 54, 32)
    worst = max(
        abs(a - b)
        for row, ref in zip(ours, reference, strict=True)
        for a, b in zip(row, ref, strict=True)
    )
    assert worst <= ONE_STEP


@pytest.mark.parametrize("width", [0, -1])
def test_stroke_width_must_be_positive(width: float) -> None:
    with pytest.raises(ValueError, match="width"):
        _ = stroke_outline(Path().move_to(0, 0).line_to(4, 0), width)

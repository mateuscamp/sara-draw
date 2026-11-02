# SPDX-License-Identifier: GPL-3.0-only
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_draw.geometry.path import Path, Point, polygon, rect
from ai_draw.smooth.coverage import coverage
from bench_cases import heart
from freetype_oracle import freetype_coverage

# The reference returns coverage in steps of 1/255: closer than one step is a match.
ONE_STEP = 1 / 255


def rounded(rows: list[list[float]]) -> list[list[float]]:
    return [[round(value, 6) for value in row] for row in rows]


def test_square_on_the_grid_covers_its_pixels_fully() -> None:
    expected = [[0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 0, 0, 0]]
    assert rounded(coverage(rect(1, 1, 2, 2), 4, 4)) == expected


def test_half_pixel_edges_cover_half_a_pixel() -> None:
    assert rounded(coverage(rect(0.5, 0, 2, 1), 3, 1)) == [[0.5, 1, 0.5]]
    assert rounded(coverage(rect(0, 0.25, 1, 0.5), 1, 1)) == [[0.5]]


def test_a_slanted_edge_covers_its_exact_area() -> None:
    triangle = polygon([(0, 0), (2, 0), (0, 2)])
    assert rounded(coverage(triangle, 2, 2)) == [[1, 0.5], [0.5, 0]]


def test_coverage_does_not_depend_on_the_contour_direction() -> None:
    backwards = polygon([(0, 2), (2, 0), (0, 0)])
    assert rounded(coverage(backwards, 2, 2)) == [[1, 0.5], [0.5, 0]]


def test_parts_outside_the_canvas_are_clipped_exactly() -> None:
    assert rounded(coverage(rect(-1, 0, 2, 1), 2, 1)) == [[1, 0]]
    assert rounded(coverage(rect(1, -2, 1, 3), 2, 2)) == [[0, 1], [0, 0]]


def test_evenodd_hollows_a_nested_square_and_nonzero_does_not() -> None:
    nested = rect(0, 0, 3, 3).extend(rect(1, 1, 1, 1))
    assert rounded(coverage(nested, 3, 3, "nonzero"))[1] == [1, 1, 1]
    assert rounded(coverage(nested, 3, 3, "evenodd"))[1] == [1, 0, 1]


@pytest.mark.parametrize("rule", ["nonzero", "evenodd"])
def test_heart_matches_freetype_within_one_step(rule: str) -> None:
    ours = coverage(heart(), 32, 32, "evenodd" if rule == "evenodd" else "nonzero")
    reference = freetype_coverage(heart(), 32, 32, evenodd=rule == "evenodd")
    worst = max(
        abs(a - b)
        for row, ref in zip(ours, reference, strict=True)
        for a, b in zip(row, ref, strict=True)
    )
    assert worst <= ONE_STEP


def test_a_curve_is_flattened_finely_enough_for_the_coverage() -> None:
    circle = Path().move_to(16, 4).cubic_to(22.6, 4, 28, 9.4, 28, 16).close()
    ours = coverage(circle, 32, 32)
    reference = freetype_coverage(circle, 32, 32)
    worst = max(
        abs(a - b)
        for row, ref in zip(ours, reference, strict=True)
        for a, b in zip(row, ref, strict=True)
    )
    assert worst <= ONE_STEP


_INSIDE = st.floats(1, 31)


def _area(corners: list[Point]) -> float:
    ends = [*corners[1:], corners[0]]
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(corners, ends, strict=True))) / 2


@given(st.lists(st.tuples(_INSIDE, _INSIDE), min_size=3, max_size=3))
def test_the_coverage_of_a_triangle_adds_up_to_its_area(corners: list[Point]) -> None:
    # Property (ADR-0006): one contour inside the canvas is covered exactly, pixel by pixel.
    rows = coverage(polygon(corners), 32, 32)
    assert math.fsum(map(math.fsum, rows)) == pytest.approx(_area(corners), abs=1e-6)

# SPDX-License-Identifier: GPL-3.0-only
import time

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from ai_draw.errors import ColorError
from ai_draw.geometry.path import Path, Point, ellipse, polygon, rect
from ai_draw.geometry.transform import Transform
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows
from ai_draw.pixel.defects import (
    abrupt_steps,
    asymmetric_cells,
    components,
    l_corners,
    orphans,
    wobble,
)
from ai_draw.pixel.line import line, line_cells

INK: Color = (20, 20, 20, 255)
LEGEND = {"#": INK}


def drawn(path: Path, size: tuple[int, int]) -> list[str]:
    canvas = Canvas(*size)
    line(canvas, path, INK)
    return to_rows(canvas, LEGEND)


def test_line_through_pixel_centers_paints_those_pixels() -> None:
    expected = ["......", "#####.", "......"]
    assert drawn(Path().move_to(0.5, 1.5).line_to(4.5, 1.5), (6, 3)) == expected


def test_diagonal_steps_corner_to_corner_without_l() -> None:
    expected = ["#...", ".#..", "..#.", "...#"]
    assert drawn(Path().move_to(0.5, 0.5).line_to(3.5, 3.5), (4, 4)) == expected


ONE_TO_TWO = ["##.......", "..##.....", "....##...", "......##.", "........#"]


def test_one_to_two_line_keeps_steps_of_two_and_puts_the_odd_one_at_the_end() -> None:
    assert drawn(Path().move_to(0.5, 0.5).line_to(8.5, 4.5), (9, 5)) == ONE_TO_TWO


def test_steep_line_is_the_transpose_of_its_wide_twin() -> None:
    transposed = ["".join(column) for column in zip(*ONE_TO_TWO, strict=True)]
    assert drawn(Path().move_to(0.5, 0.5).line_to(4.5, 8.5), (5, 9)) == transposed


def test_line_runs_the_same_backwards() -> None:
    assert drawn(Path().move_to(8.5, 4.5).line_to(0.5, 0.5), (9, 5)) == ONE_TO_TWO


def test_square_keeps_its_corners() -> None:
    expected = ["####", "#..#", "#..#", "####"]
    assert drawn(rect(0.5, 0.5, 3, 3), (4, 4)) == expected


def test_circle_is_one_clean_symmetric_ring() -> None:
    cells = frozenset(line_cells(ellipse(8, 8, 5)))
    assert (components(cells), orphans(cells), l_corners(cells)) == (1, 0, 0)
    assert asymmetric_cells(cells, mirror_x=8, mirror_y=8) == 0


def test_turned_square_has_no_l_corner() -> None:
    turned = Transform.rotate(45).then(Transform.translate(16, 16))
    cells = frozenset(line_cells(rect(-8, -8, 16, 16).transformed(turned)))
    assert (components(cells), l_corners(cells)) == (1, 0)
    assert asymmetric_cells(cells, mirror_x=16, mirror_y=16) == 0


def test_open_line_ending_on_a_pixel_edge_keeps_only_its_own_pixels() -> None:
    expected = ["......", "####..", "......"]
    assert drawn(Path().move_to(0, 1.5).line_to(4, 1.5), (6, 3)) == expected


@pytest.mark.parametrize("radius", range(3, 17))
def test_circles_of_every_small_radius_are_mirror_images_without_l(radius: int) -> None:
    center = radius + 3
    cells = frozenset(line_cells(ellipse(center, center, radius)))
    assert asymmetric_cells(cells, mirror_x=center, mirror_y=center) == 0
    assert l_corners(cells) == 0
    assert wobble(cells, 1) == 0


def test_curve_that_only_touches_a_pixel_edge_stays_on_its_own_side() -> None:
    dip = Path().move_to(0.5, 1).line_to(4, 3).line_to(7.5, 1)
    assert max(y for _, y in line_cells(dip)) == 2


def test_a_large_ellipse_settles_its_steps_quickly() -> None:
    # Regression (audit G1, 01/11): this ellipse's steps swapped back and forth until the
    # n**2 pass ceiling, 2.3 s here and minutes for a circle of radius 220.
    start = time.perf_counter()
    cells = frozenset(line_cells(ellipse(62, 63, 59, 60)))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5
    assert l_corners(cells) == 0


def test_a_repeated_vertex_draws_the_same_line_as_a_single_one() -> None:
    # Regression (audit M1, 01/11): the repeated point had no tangent and added two pixels.
    single = Path().move_to(0.5, 0.5).line_to(4.5, 0.5).line_to(4.5, 4.5)
    repeated = Path().move_to(0.5, 0.5).line_to(4.5, 0.5).line_to(4.5, 0.5).line_to(4.5, 4.5)
    assert line_cells(repeated) == line_cells(single)


def test_a_zero_length_line_paints_one_pixel() -> None:
    assert len(line_cells(Path().move_to(4, 4).line_to(4, 4))) == 1


def test_line_refuses_a_half_transparent_color() -> None:
    with pytest.raises(ColorError, match="alpha"):
        line(Canvas(8, 8), Path().move_to(0.5, 0.5).line_to(6.5, 0.5), (20, 20, 20, 128))


@pytest.mark.parametrize("rx", [1.0, 1.5, 2.0, 2.5])
def test_narrow_ellipses_end_in_a_clean_tip(rx: float) -> None:
    # Regression (audit M2, 01/11): the two-pixel tip lost only one of its halves, which left
    # an L and a lopsided tip in 76 of 2,418 ellipses of a sweep.
    for ry in [step / 2 for step in range(2, 41)]:
        cells = frozenset(line_cells(ellipse(40, 40, rx, ry)))
        assert l_corners(cells) == 0, f"ellipse(40, 40, {rx}, {ry})"


def test_a_narrow_ellipse_tip_stays_mirrored() -> None:
    cells = frozenset(line_cells(ellipse(40, 40, 2, 8.5)))
    assert asymmetric_cells(cells, mirror_x=40, mirror_y=40) == 0


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (rect(0, 4, 8, 0), {(x, 4) for x in range(8)}),
        (polygon([(0, 4), (4, 4), (8, 4)]), {(x, 4) for x in range(8)}),
        (ellipse(8, 8, 6, 0), {(x, 8) for x in range(2, 14)}),
        (Path().move_to(4, 4).close(), {(4, 4)}),
        (ellipse(4, 4, 0), {(4, 4)}),
    ],
    ids=["flat_rect", "flat_polygon", "flat_ellipse", "closed_point", "zero_circle"],
)
def test_a_flat_shape_on_a_pixel_edge_is_one_pixel_thick(
    path: Path, expected: set[tuple[int, int]]
) -> None:
    # Regression (audit B5, 02/11): a closed contour of zero area runs both ways over the same
    # pixels, and each way took its own side of the edge: two rows, or a 2x2 block for a point.
    # Like the fill's half-open rows, it takes the pixel past the edge.
    assert line_cells(path) == expected


@pytest.mark.parametrize(
    ("rx", "ry"),
    [
        (2.5, 13.5),
        (3.5, 21.5),
        (4.0, 25.5),
        (4.5, 25.5),
        (6.0, 30.0),
        (12.0, 29.5),
        (15.5, 6.5),
        (18.0, 4.5),
        (25.0, 7.5),
        (27.0, 5.0),
        (28.5, 6.5),
    ],
)
def test_ellipses_are_mirror_images(rx: float, ry: float) -> None:
    # Regression (audit M2's rest, 02/11): 184 of 3,481 ellipses of a sweep came out lopsided.
    # A segment's middle tie was decided from its smaller cell, which mirror images have at
    # opposite ends.
    cells = frozenset(line_cells(ellipse(40, 40, rx, ry)))
    assert asymmetric_cells(cells, mirror_x=40, mirror_y=40) == 0


@pytest.mark.parametrize(("radius", "center"), [(186, 189), (200, 203.5), (214, 217.5)])
def test_large_circles_are_mirror_images(radius: int, center: float) -> None:
    # Regression (02/11): from radius about 180, 28 circles of a sweep came out lopsided, by the
    # same middle tie as the ellipses.
    cells = frozenset(line_cells(ellipse(center, center, radius)))
    assert asymmetric_cells(cells, mirror_x=center, mirror_y=center) == 0


@pytest.mark.parametrize("radius", range(17, 61))
def test_larger_circles_have_steps_that_only_grow_or_shrink(radius: int) -> None:
    # Regression (02/11): from radius 19, most circles had a step out of its run, as in
    # 2, 2, 1, 1, 2, 1, 1, which the wobble detector counts.
    for center in (radius + 3, radius + 3.5):
        cells = frozenset(line_cells(ellipse(center, center, radius)))
        assert wobble(cells, 1) == 0, f"center {center}"


@pytest.mark.parametrize("radius", [8, 12, 20, 40, 60, 100])
def test_circles_have_no_abrupt_step(radius: int) -> None:
    # Regression (02/11): a large circle read as an octagon, a flat top of 9 and then 3 at once
    # at radius 40. The top now passes cells to the runs after it while one is over twice the
    # other.
    for center in (radius + 3, radius + 3.5):
        cells = frozenset(line_cells(ellipse(center, center, radius)))
        assert abrupt_steps(cells) == 0, f"center {center}"


_ON_CANVAS = st.floats(0.3, 30)


def _on_an_edge(value: float) -> bool:
    """Within the rounding that treats a point as lying on a pixel edge (``_SNAP_DECIMALS``)."""
    return abs(value - round(value)) < 1e-9  # line.py rounds to 9 decimals


@given(st.tuples(_ON_CANVAS, _ON_CANVAS), st.tuples(_ON_CANVAS, _ON_CANVAS))
def test_an_open_line_off_the_pixel_edges_is_the_same_both_ways(start: Point, end: Point) -> None:
    # Property (ADR-0006). On a pixel edge the direction decides, on purpose (audit B6); the
    # first draft of this property found 1.0000000000000002, which rounds onto the edge.
    _ = assume(not any(_on_an_edge(value) for value in (*start, *end)))
    forward = line_cells(Path().move_to(*start).line_to(*end))
    backward = line_cells(Path().move_to(*end).line_to(*start))
    assert forward == backward


_HALVES = st.integers(60, 100).map(lambda doubled: doubled / 2)
_RADII = st.floats(1.5, 18)


@given(_HALVES, _HALVES, _RADII, _RADII)
@example(cx=30.5, cy=30.0, rx=2.0, ry=5.0)
@example(cx=30.0, cy=30.0, rx=7.0, ry=6.125)
def test_the_line_of_any_ellipse_is_one_clean_mirrored_ring(
    cx: float, cy: float, rx: float, ry: float
) -> None:
    # Property (ADR-0006). The grid sweeps only tried centers on whole pixels. Both examples are
    # the softening of abrupt steps making a stroke swell and thin (2, 1, 2), which 146 of 3,000
    # random ellipses had (02/11). Still pending, older than the softening and found with
    # --hypothesis-profile=explore: the tip of a narrow ellipse centered on a pixel, as
    # ellipse(30.5, 30.5, 2, 6), whose legs end on a pixel edge.
    cells = frozenset(line_cells(ellipse(cx, cy, rx, ry)))
    assert (components(cells), orphans(cells)) == (1, 0)
    assert l_corners(cells) == 0
    assert wobble(cells, 1) == 0
    assert asymmetric_cells(cells, mirror_x=cx, mirror_y=cy) == 0

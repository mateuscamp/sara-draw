# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.geometry.path import Path, ellipse, rect
from ai_draw.geometry.transform import Transform
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows
from ai_draw.pixel.defects import asymmetric_cells, components, l_corners, orphans, wobble
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

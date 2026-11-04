# SPDX-License-Identifier: GPL-3.0-only
import time

import pytest

from ai_draw.errors import SettingError
from ai_draw.grid.canvas import Color
from ai_draw.grid.rows import from_rows
from ai_draw.pixel.defects import (
    Cells,
    abrupt_steps,
    asymmetric_cells,
    cells_of,
    components,
    l_corners,
    orphans,
    thickness_defects,
    uneven_steps,
    wobble,
)

INK: Color = (20, 20, 20, 255)
RED: Color = (200, 30, 30, 255)


def cells(*rows: str) -> Cells:
    return cells_of(from_rows(rows, {"#": INK}))


def transposed(*rows: str) -> tuple[str, ...]:
    return tuple("".join(column) for column in zip(*rows, strict=True))


def test_cells_of_takes_every_opaque_pixel_or_one_color() -> None:
    canvas = from_rows(["#r", ".."], {"#": INK, "r": RED})
    assert cells_of(canvas) == {(0, 0), (1, 0)}
    assert cells_of(canvas, RED) == {(1, 0)}


def test_orphan_is_a_pixel_with_no_neighbor_of_eight() -> None:
    assert orphans(cells("#....", "...##", ".....")) == 1
    assert orphans(cells("#.", ".#")) == 0


def test_components_join_by_eight_neighbors() -> None:
    assert components(cells("##..#", ".....", "#....")) == 3
    assert components(cells("#.", ".#")) == 1
    assert components(frozenset()) == 0


def test_clean_lines_have_no_l_corner() -> None:
    assert l_corners(cells("#..", ".#.", "..#")) == 0
    assert l_corners(cells("##....", "..##..", "....##")) == 0
    assert l_corners(cells("##", "##")) == 0


def test_l_corner_is_a_side_and_an_up_or_down_neighbor_without_the_diagonal() -> None:
    assert l_corners(cells("#.", "##")) == 1
    assert l_corners(cells("#..", "##.", ".##")) == 3


STEPS_2_2_3_2_2 = (
    "##...........",
    "..##.........",
    "....###......",
    ".......##....",
    ".........##..",
)


def test_even_steps_are_not_uneven() -> None:
    assert uneven_steps(cells("##......", "..##....", "....##..", "......##")) == 0


def test_a_step_that_breaks_the_rhythm_is_uneven() -> None:
    assert uneven_steps(cells(*STEPS_2_2_3_2_2)) == 1


def test_uneven_steps_reads_steep_lines_by_columns() -> None:
    assert uneven_steps(cells(*transposed(*STEPS_2_2_3_2_2))) == 1


def test_line_of_its_own_width_has_no_thickness_defect() -> None:
    assert thickness_defects(cells("####"), 1) == 0
    assert thickness_defects(cells("####", "####"), 2) == 0


def test_a_cell_whose_runs_across_are_shorter_than_the_width_is_too_thin() -> None:
    # (1, 0): its column is 1 pixel tall across a 2-pixel line that runs flat
    assert thickness_defects(cells("####", "#.##"), 2) == 1


def test_a_steep_stroke_staggered_row_by_row_keeps_its_width() -> None:
    assert thickness_defects(cells("##..", ".##.", "..##"), 2) == 0


def test_cells_inside_a_block_wider_than_the_width_are_too_thick() -> None:
    assert thickness_defects(cells("###", "###", "###"), 2) == 9
    assert thickness_defects(cells("##", "##"), 1) == 4
    assert thickness_defects(cells("##", "#."), 1) == 0


def test_symmetric_cells_have_their_mirror() -> None:
    assert asymmetric_cells(cells("#..#"), mirror_x=2.0) == 0
    assert asymmetric_cells(cells("#...", "...."), mirror_x=2.0) == 1


def test_asymmetry_adds_both_axes() -> None:
    assert asymmetric_cells(cells("#.", ".."), mirror_x=1.0, mirror_y=1.0) == 2


def test_mirror_must_fall_on_a_pixel_edge_or_center() -> None:
    with pytest.raises(ValueError, match="mirror"):
        _ = asymmetric_cells(cells("#"), mirror_x=1.25)


def test_a_steady_stroke_does_not_wobble() -> None:
    assert wobble(cells("##....", ".##...", "..##..", "...##."), 2) == 0
    assert wobble(cells("######", "######"), 2) == 0


def test_a_stroke_whose_width_swings_back_and_forth_wobbles() -> None:
    assert wobble(cells("###...", ".##...", ".###..", "..##..", "..###."), 2) == 3


def test_steps_that_swing_along_a_one_pixel_line_wobble() -> None:
    assert wobble(cells("##.....", "..#....", "...##.."), 1) == 1


def test_a_one_pixel_tip_between_steps_of_two_is_not_a_wobble() -> None:
    # Regression (02/11): the reading ran through the tip, 2, 1, 2, where the line turns back.
    # The midpoint ellipse and Zingl's draw the tip of an ellipse 2 by 6 just like this.
    tip = cells("..#..", ".#.#.", ".#.#.", "#...#", "#...#", ".#.#.", ".#.#.", "..#..")
    assert wobble(tip, 1) == 0


@pytest.mark.parametrize("width", [0, -5])
def test_wobble_refuses_a_width_below_one(width: int) -> None:
    # Regression (audit B8, 02/11): wobble answered 0 where thickness_defects refuses the width.
    with pytest.raises(SettingError, match="expected an integer >= 1"):
        _ = wobble(cells("##"), width)


def test_components_of_many_loose_pixels_take_linear_time() -> None:
    # Regression (audit B4, 02/11): each new piece recounted the labels, 5.8 s for 40,000.
    loose = frozenset((2 * x, 2 * y) for x in range(200) for y in range(200))
    start = time.perf_counter()
    count = components(loose)
    elapsed = time.perf_counter() - start
    assert count == 40_000
    assert elapsed < 0.5


CLEAN_CIRCLE = (
    ".....######.....",
    "...##......##...",
    "..#..........#..",
    ".#............#.",
    ".#............#.",
    "#..............#",
    "#..............#",
    "#..............#",
    "#..............#",
    "#..............#",
    "#..............#",
    ".#............#.",
    ".#............#.",
    "..#..........#..",
    "...##......##...",
    ".....######.....",
)


def test_a_circle_whose_steps_change_gently_has_no_abrupt_step() -> None:
    assert abrupt_steps(cells(*CLEAN_CIRCLE)) == 0


def test_a_step_more_than_twice_the_next_on_a_curve_is_abrupt() -> None:
    # The octagon look of a large circle: a long flat top, then short steps at once.
    assert abrupt_steps(cells("#########...", ".........##.", "...........#")) == 1


def test_the_top_of_a_round_shape_counts_half_its_length() -> None:
    # The top is shared by both sides: 10 is 5 per side, abrupt against 1; 4 is 2, gentle.
    assert abrupt_steps(cells(".##########.", "#..........#")) == 2
    assert abrupt_steps(cells(".####.", "#....#")) == 0


def test_corners_and_straight_lines_have_no_abrupt_step() -> None:
    assert abrupt_steps(cells("#########", "#.......#", "#########")) == 0
    assert abrupt_steps(cells("###......", "...###...", "......###")) == 0

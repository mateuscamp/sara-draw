# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.errors import SettingError
from ai_draw.grid.canvas import Color
from ai_draw.grid.rows import from_rows
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


@pytest.mark.parametrize("width", [0, -5])
def test_wobble_refuses_a_width_below_one(width: int) -> None:
    # Regression (audit B8, 02/11): wobble answered 0 where thickness_defects refuses the width.
    with pytest.raises(SettingError, match="expected an integer >= 1"):
        _ = wobble(cells("##"), width)

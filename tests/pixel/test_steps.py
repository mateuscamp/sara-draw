# SPDX-License-Identifier: GPL-3.0-only
from ai_draw.pixel.steps import Cell, even_out_steps

# rows "####....", "....#...", ".....##.", ".......#": steps of 4, 1, 2, 1 cells
JAGGED: list[Cell] = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (5, 2), (6, 2), (7, 3)]
# rows "####....", "....##..", "......#.", ".......#": steps of 4, 2, 1, 1
SMOOTH: list[Cell] = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (5, 1), (6, 2), (7, 3)]


def test_a_step_out_of_order_swaps_with_its_neighbor() -> None:
    assert even_out_steps(JAGGED, closed=False) == SMOOTH


def test_the_same_line_backwards_gets_the_mirror_fix() -> None:
    assert even_out_steps(JAGGED[::-1], closed=False) == SMOOTH[::-1]


def test_steps_already_in_order_stay() -> None:
    assert even_out_steps(SMOOTH, closed=False) == SMOOTH


def test_a_square_corner_is_not_a_step_to_move() -> None:
    square = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
    assert even_out_steps(square, closed=True) == square


def from_runs(lengths: list[int]) -> list[Cell]:
    """A one-pixel line going right and down: a row run of each length, then a diagonal."""
    cells: list[Cell] = []
    x = 0
    for y, length in enumerate(lengths):
        cells.extend((x + i, y) for i in range(length))
        x += length
    return cells


def test_a_step_between_two_equal_ones_joins_its_kind_on_a_curve() -> None:
    # Regression (02/11): circles from radius 19 had steps like 4, 3, 2, 1, 2, 1, 1, the
    # wobble of a curve. The lone 2 sat between two 1s, a case left alone for straight lines.
    # Its kind is on one side only, and the other side goes on the other way (3 then 4).
    assert even_out_steps(from_runs([4, 3, 2, 1, 2, 1, 1, 1]), closed=False) == from_runs(
        [4, 3, 2, 2, 1, 1, 1, 1]
    )


def test_a_lone_step_far_from_its_kind_travels_back_to_it() -> None:
    assert even_out_steps(from_runs([4, 3, 2, 2, 1, 1, 2, 1, 1, 1]), closed=False) == from_runs(
        [4, 3, 2, 2, 2, 1, 1, 1, 1, 1]
    )


def test_the_rhythm_of_a_straight_line_stays() -> None:
    for lengths in ([2, 3, 2, 3, 2, 3, 2], [2, 2, 3, 2, 2, 3, 2, 2, 3, 2]):
        assert even_out_steps(from_runs(lengths), closed=False) == from_runs(lengths)


def test_steps_on_a_straight_side_keep_their_order() -> None:
    # A polygon of many sides turns less than a kept corner at each vertex, so its sides would
    # read as one curve and be sorted round; their cells are held (seen with a 12-gon, 02/11).
    lengths = [4, 3, 2, 1, 2, 1, 1, 1]
    side = from_runs(lengths)
    assert even_out_steps(side, closed=False, straight=set(side)) == side

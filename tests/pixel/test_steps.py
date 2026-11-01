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

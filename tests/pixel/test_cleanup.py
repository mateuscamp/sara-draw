# SPDX-License-Identifier: GPL-3.0-only
from ai_draw.grid.canvas import Color
from ai_draw.grid.rows import from_rows
from ai_draw.pixel.cleanup import Cell, bridge_gaps
from ai_draw.pixel.defects import cells_of

INK: Color = (20, 20, 20, 255)


def cells(*rows: str) -> set[Cell]:
    return set(cells_of(from_rows(rows, {"#": INK})))


TWO_BLOCKS = cells("##...", "##...", "...##", "...##")


def test_an_outline_cell_touching_two_pieces_joins_them() -> None:
    assert bridge_gaps(TWO_BLOCKS, [(2, 1), (4, 0)]) == TWO_BLOCKS | {(2, 1)}


def test_two_touching_outline_cells_bridge_a_two_pixel_gap() -> None:
    apart = cells("#..#")
    assert bridge_gaps(apart, [(1, 0), (2, 0)]) == cells("####")


def test_outline_cells_that_join_nothing_stay_out() -> None:
    assert bridge_gaps(TWO_BLOCKS, [(4, 0), (0, 3)]) == TWO_BLOCKS


def test_one_piece_needs_no_bridge() -> None:
    block = cells("##", "##")
    assert bridge_gaps(block, [(2, 0), (2, 1)]) == block

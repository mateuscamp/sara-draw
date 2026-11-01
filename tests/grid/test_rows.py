# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.grid.canvas import CLEAR, Canvas, Color
from ai_draw.grid.rows import from_rows, to_rows

RED: Color = (255, 0, 0, 255)
BLUE: Color = (0, 0, 255, 255)


def test_to_rows_writes_legend_chars_dots_and_question_marks() -> None:
    canvas = Canvas(3, 1)
    canvas.paint(0, 0, RED)
    canvas.paint(2, 0, BLUE)
    assert to_rows(canvas, {"r": RED}) == ["r.?"]


LEGEND = {"r": RED, "b": BLUE}


def test_from_rows_paints_legend_chars_and_leaves_dots_clear() -> None:
    canvas = from_rows(["r..", ".b."], LEGEND)
    assert (canvas.width, canvas.height) == (3, 2)
    assert to_rows(canvas, LEGEND) == ["r..", ".b."]
    assert canvas.color_at(1, 0) == CLEAR


def test_from_rows_rejects_a_ragged_row() -> None:
    with pytest.raises(ValueError, match="row 1 has 3 columns, expected 2"):
        _ = from_rows(["rr", "rrr"], LEGEND)


def test_from_rows_rejects_a_char_without_color() -> None:
    with pytest.raises(ValueError, match="'x' in row 0"):
        _ = from_rows(["rx"], LEGEND)


def test_from_rows_needs_at_least_one_row() -> None:
    with pytest.raises(ValueError, match="no rows"):
        _ = from_rows([], LEGEND)


def test_from_rows_keeps_the_dot_for_transparency() -> None:
    with pytest.raises(ValueError, match=r"'\.'"):
        _ = from_rows(["r."], {".": RED, "r": RED})

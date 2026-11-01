# SPDX-License-Identifier: GPL-3.0-only
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows

RED: Color = (255, 0, 0, 255)
BLUE: Color = (0, 0, 255, 255)


def test_to_rows_writes_legend_chars_dots_and_question_marks() -> None:
    canvas = Canvas(3, 1)
    canvas.paint(0, 0, RED)
    canvas.paint(2, 0, BLUE)
    assert to_rows(canvas, {"r": RED}) == ["r.?"]

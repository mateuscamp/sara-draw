# SPDX-License-Identifier: GPL-3.0-only
import math

import pytest

from ai_draw.geometry.path import Path, rect
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows
from ai_draw.pixel.defects import cells_of, l_corners
from ai_draw.pixel.stroke import disc, stroke, stroke_pieces

INK: Color = (20, 20, 20, 255)
LEGEND = {"#": INK}


def test_one_pixel_line_on_a_row_center_paints_that_row() -> None:
    canvas = Canvas(6, 3)
    stroke(canvas, Path().move_to(0, 1.5).line_to(4, 1.5), INK, 1)
    assert to_rows(canvas, LEGEND) == ["......", "####..", "......"]


def test_open_path_gets_a_quad_per_segment_and_a_disc_per_vertex() -> None:
    pieces = stroke_pieces(Path().move_to(0, 0).line_to(4, 0).line_to(4, 4).contours(), 2)
    assert len(pieces) == 2 + 3


def test_closed_path_also_strokes_the_closing_segment() -> None:
    assert len(stroke_pieces(rect(0, 0, 4, 4).contours(), 2)) == 4 + 4


def test_zero_length_segment_gets_only_its_discs() -> None:
    assert len(stroke_pieces(Path().move_to(1, 1).line_to(1, 1).contours(), 2)) == 2


def test_disc_has_a_side_per_pixel_of_perimeter_and_at_least_eight() -> None:
    assert len(disc(0, 0, 0.5).points) == 8
    assert len(disc(0, 0, 10).points) == math.ceil(2 * math.pi * 10)


def test_disc_stays_within_its_radius() -> None:
    assert all(math.hypot(x, y) <= 3 + 1e-9 for x, y in disc(0, 0, 3).points)


@pytest.mark.parametrize("width", [0, -1])
def test_stroke_width_must_be_positive(width: float) -> None:
    with pytest.raises(ValueError, match="width"):
        _ = stroke_pieces(rect(0, 0, 1, 1).contours(), width)


def test_one_pixel_stroke_is_the_pixel_perfect_line() -> None:
    canvas = Canvas(9, 5)
    stroke(canvas, Path().move_to(0.5, 0.5).line_to(8.5, 4.5), INK, 1)
    assert l_corners(cells_of(canvas)) == 0
    assert to_rows(canvas, LEGEND)[0] == "##......."

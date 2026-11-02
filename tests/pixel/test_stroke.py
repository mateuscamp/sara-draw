# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.errors import ColorError
from ai_draw.geometry.path import Path, ellipse
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows
from ai_draw.pixel.defects import (
    asymmetric_cells,
    cells_of,
    components,
    l_corners,
    thickness_defects,
    wobble,
)
from ai_draw.pixel.stroke import stroke

INK: Color = (20, 20, 20, 255)
LEGEND = {"#": INK}


def stroked(path: Path, size: tuple[int, int], width: int) -> Canvas:
    canvas = Canvas(*size)
    stroke(canvas, path, INK, width)
    return canvas


def test_one_pixel_line_on_a_row_center_paints_that_row() -> None:
    canvas = stroked(Path().move_to(0, 1.5).line_to(4, 1.5), (6, 3), 1)
    assert to_rows(canvas, LEGEND) == ["......", "####..", "......"]


def test_one_pixel_stroke_is_the_pixel_perfect_line() -> None:
    canvas = stroked(Path().move_to(0.5, 0.5).line_to(8.5, 4.5), (9, 5), 1)
    assert l_corners(cells_of(canvas)) == 0
    assert to_rows(canvas, LEGEND)[0] == "##......."


def test_two_pixel_line_on_a_pixel_edge_takes_a_row_on_each_side() -> None:
    canvas = stroked(Path().move_to(1, 2).line_to(7, 2), (8, 4), 2)
    assert to_rows(canvas, LEGEND) == ["........", ".######.", ".######.", "........"]


def test_three_pixel_line_through_pixel_centers_is_centered() -> None:
    canvas = stroked(Path().move_to(1, 2.5).line_to(7, 2.5), (8, 5), 3)
    expected = ["........", ".######.", ".######.", ".######.", "........"]
    assert to_rows(canvas, LEGEND) == expected


def test_two_pixel_curve_keeps_its_width_steady() -> None:
    wave = Path().move_to(3, 12).quad_to(9, 2, 15, 12).quad_to(21, 22, 27, 12)
    cells = cells_of(stroked(wave, (30, 24), 2))
    assert (components(cells), thickness_defects(cells, 2), wobble(cells, 2)) == (1, 0, 0)


@pytest.mark.parametrize("width", [2, 3])
def test_thick_circle_is_a_steady_symmetric_ring(width: int) -> None:
    cells = cells_of(stroked(ellipse(12, 12, 7), (24, 24), width))
    assert asymmetric_cells(cells, mirror_x=12, mirror_y=12) == 0
    assert (components(cells), thickness_defects(cells, width), wobble(cells, width)) == (1, 0, 0)


@pytest.mark.parametrize("width", [0, -1, 1.5])
def test_stroke_width_is_a_whole_number_of_pixels(width: float) -> None:
    with pytest.raises(ValueError, match="width"):
        stroke(Canvas(4, 4), Path().move_to(0, 0).line_to(3, 3), INK, width)  # pyright: ignore[reportArgumentType]  # motivo: the bad value is the point


def test_stroke_refuses_a_half_transparent_color() -> None:
    with pytest.raises(ColorError, match="alpha"):
        stroke(Canvas(16, 16), ellipse(8, 8, 5), (20, 20, 20, 128), 3)


def test_a_whole_width_written_as_a_float_strokes_like_the_integer() -> None:
    # Regression (audit M5, 01/11): width 2.0 raised TypeError from range().
    as_int, as_float = Canvas(16, 16), Canvas(16, 16)
    stroke(as_int, ellipse(8, 8, 5), INK, 2)
    stroke(as_float, ellipse(8, 8, 5), INK, 2.0)  # pyright: ignore[reportArgumentType]  # motivo: untyped callers pass floats
    assert to_rows(as_float, LEGEND) == to_rows(as_int, LEGEND)

# SPDX-License-Identifier: GPL-3.0-only
import numpy as np
import pytest

from ai_draw.grid.canvas import CLEAR, Canvas, Color
from ai_draw.grid.rows import to_rows

RED: Color = (255, 0, 0, 255)
LEGEND = {"#": RED}


def test_new_canvas_is_transparent_with_rows_first() -> None:
    canvas = Canvas(3, 2)
    assert (canvas.width, canvas.height) == (3, 2)
    assert canvas.pixels.shape == (2, 3, 4)
    assert canvas.color_at(2, 1) == CLEAR


@pytest.mark.parametrize(("width", "height"), [(0, 1), (1, -2)])
def test_canvas_needs_positive_size(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="expected positive"):
        _ = Canvas(width, height)


@pytest.mark.parametrize("color", [(256, 0, 0, 255), (0, 0, -1, 255), (0, 0, 0)])
def test_invalid_color_is_an_error(color: Color) -> None:
    with pytest.raises(ValueError, match="color"):
        Canvas(1, 1).paint(0, 0, color)


def test_paint_outside_is_ignored_and_color_at_outside_is_none() -> None:
    canvas = Canvas(2, 2)
    canvas.paint(5, 0, RED)
    assert canvas.color_at(5, 0) is None
    assert to_rows(canvas, LEGEND) == ["..", ".."]


def test_paint_overwrites_even_with_transparent() -> None:
    canvas = Canvas(1, 1)
    canvas.paint(0, 0, RED)
    canvas.paint(0, 0, CLEAR)
    assert canvas.color_at(0, 0) == CLEAR


def test_span_is_clipped_to_the_canvas() -> None:
    canvas = Canvas(4, 2)
    canvas.span(-1, 0, 3, RED)
    canvas.span(0, 5, 3, RED)
    assert to_rows(canvas, LEGEND) == ["##..", "...."]


def test_rect_paints_width_by_height() -> None:
    canvas = Canvas(4, 3)
    canvas.rect(1, 1, 2, 2, RED)
    assert to_rows(canvas, LEGEND) == ["....", ".##.", ".##."]


def test_enlarged_repeats_each_pixel() -> None:
    canvas = Canvas(2, 1)
    canvas.paint(0, 0, RED)
    assert to_rows(canvas.enlarged(2), LEGEND) == ["##..", "##.."]


def test_enlarged_needs_a_positive_integer() -> None:
    with pytest.raises(ValueError, match="factor"):
        _ = Canvas(1, 1).enlarged(0)


def test_from_pixels_copies_the_array() -> None:
    pixels = np.zeros((1, 2, 4), dtype=np.uint8)
    canvas = Canvas.from_pixels(pixels)
    pixels[0, 0] = RED
    assert canvas.color_at(0, 0) == CLEAR
    assert canvas.width == 2


def test_from_pixels_needs_rgba_rows() -> None:
    with pytest.raises(ValueError, match="shape"):
        _ = Canvas.from_pixels(np.zeros((2, 2, 3), dtype=np.uint8))


def test_same_pixels_compares_size_and_every_channel() -> None:
    first, second = Canvas(2, 1), Canvas(2, 1)
    assert first.same_pixels(second)
    second.paint(1, 0, RED)
    assert not first.same_pixels(second)
    assert not first.same_pixels(Canvas(1, 2))

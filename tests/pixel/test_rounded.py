# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.errors import ColorError
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows
from ai_draw.pixel.rounded import fill_rounded_rect

INK: Color = (20, 20, 20, 255)
LEGEND = {"#": INK}


def rounded(width: int, height: int, radius: int) -> list[str]:
    canvas = Canvas(width, height)
    fill_rounded_rect(canvas, 0, 0, width, height, radius=radius, color=INK)
    return to_rows(canvas, LEGEND)


def test_corners_are_cut_row_by_row_and_mirror_each_other() -> None:
    assert rounded(8, 5, 2) == [".######.", "########", "########", "########", ".######."]


def test_radius_that_does_not_fit_is_clipped_to_half_the_side() -> None:
    assert rounded(4, 4, 10) == [".##.", "####", "####", ".##."]


def test_radius_zero_is_a_plain_rectangle() -> None:
    assert rounded(3, 2, 0) == ["###", "###"]


def test_rounded_rect_refuses_a_half_transparent_color() -> None:
    with pytest.raises(ColorError, match="alpha"):
        fill_rounded_rect(Canvas(8, 8), 0, 0, 8, 8, radius=2, color=(20, 20, 20, 128))

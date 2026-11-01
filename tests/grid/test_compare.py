# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.compare import diff, recolor
from ai_draw.grid.rows import from_rows, to_rows

RED: Color = (200, 30, 30, 255)
BLUE: Color = (30, 30, 200, 255)
LEGEND = {"r": RED, "b": BLUE}


def test_diff_counts_the_pixels_that_differ() -> None:
    assert diff(from_rows(["rr", ".."], LEGEND), from_rows(["rb", ".r"], LEGEND)) == 2


def test_diff_of_a_canvas_and_its_copy_is_zero() -> None:
    canvas = from_rows(["rb"], LEGEND)
    assert diff(canvas, canvas.copy()) == 0


def test_diff_needs_the_same_size() -> None:
    with pytest.raises(ValueError, match="size 2x1 against 1x2"):
        _ = diff(Canvas(2, 1), Canvas(1, 2))


def test_recolor_swaps_only_the_mapped_colors_into_a_new_canvas() -> None:
    original = from_rows(["rb."], LEGEND)
    assert to_rows(recolor(original, {RED: BLUE}), LEGEND) == ["bb."]
    assert to_rows(original, LEGEND) == ["rb."]

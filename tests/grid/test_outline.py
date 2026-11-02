# SPDX-License-Identifier: GPL-3.0-only
from collections.abc import Callable

import pytest

from ai_draw.errors import ColorError
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.outline import outline, outlined
from ai_draw.grid.rows import from_rows, to_rows

INK: Color = (30, 20, 40, 255)
SKIN: Color = (230, 180, 140, 255)
LEGEND = {"k": INK, "s": SKIN}


def test_outline_inks_the_pixels_that_touch_transparency() -> None:
    block = from_rows([".....", ".sss.", ".sss.", ".sss.", "....."], LEGEND)
    expected = [".....", ".kkk.", ".ksk.", ".kkk.", "....."]
    assert to_rows(outline(block, INK), LEGEND) == expected


def test_outline_treats_the_canvas_edge_as_outside() -> None:
    assert to_rows(outline(from_rows(["ss", "ss"], LEGEND), INK), LEGEND) == ["kk", "kk"]


def test_outline_looks_at_the_four_side_neighbors_only() -> None:
    notched = from_rows(["sss.", "ssss", "ssss", "ssss"], LEGEND)
    # (1, 1) touches the notch only by its corner, so it keeps its color
    assert to_rows(outline(notched, INK), LEGEND) == ["kkk.", "kssk", "kssk", "kkkk"]


def test_outline_leaves_its_input_untouched() -> None:
    block = from_rows(["ss"], LEGEND)
    _ = outline(block, INK)
    assert to_rows(block, LEGEND) == ["ss"]


def test_outlined_grows_a_pixel_and_rings_the_silhouette_by_eight_neighbors() -> None:
    assert to_rows(outlined(from_rows(["s"], LEGEND), INK), LEGEND) == ["kkk", "ksk", "kkk"]


def test_outlined_fills_a_gap_between_two_shapes() -> None:
    expected = ["kkkkk", "ksksk", "kkkkk"]
    assert to_rows(outlined(from_rows(["s.s"], LEGEND), INK), LEGEND) == expected


@pytest.mark.parametrize("draw", [outline, outlined])
def test_outline_refuses_an_ink_that_is_not_a_color(
    draw: Callable[[Canvas, Color], Canvas],
) -> None:
    # Regression (audit B3, 02/11): a bad ink leaked numpy's OverflowError or ValueError.
    with pytest.raises(ColorError, match="expected"):
        _ = draw(from_rows(["s"], LEGEND), (300, 0, 0, 255))

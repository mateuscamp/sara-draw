# SPDX-License-Identifier: GPL-3.0-only
import math
from typing import cast

import pytest

from ai_draw.geometry.path import Path, polygon, rect
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows
from ai_draw.pixel.defects import cells_of, components
from ai_draw.pixel.fill import FillRule, Span, fill, spans

INK: Color = (20, 20, 20, 255)
LEGEND = {"#": INK}


def filled(path: Path, size: tuple[int, int], rule: FillRule = "nonzero") -> list[str]:
    canvas = Canvas(*size)
    fill(canvas, path, INK, rule)
    return to_rows(canvas, LEGEND)


def test_square_on_the_grid_fills_exactly_its_pixels() -> None:
    expected = [Span(0, 0, 4), Span(0, 1, 4), Span(0, 2, 4), Span(0, 3, 4)]
    assert spans(rect(0, 0, 4, 4).contours(), "nonzero", 8) == expected


def test_pixel_enters_when_its_center_is_inside() -> None:
    assert filled(rect(0.4, 0.6, 2.2, 1), (4, 3)) == ["....", "###.", "...."]


def test_vertex_on_a_pixel_center_opens_no_hole() -> None:
    diamond = polygon([(2, 0), (4, 1.5), (2, 3), (0, 1.5)])
    assert filled(diamond, (4, 3)) == [".##.", "####", ".##."]


def test_evenodd_hollows_a_nested_square_and_nonzero_does_not() -> None:
    nested = rect(0, 0, 4, 4).extend(rect(1, 1, 2, 2))
    assert filled(nested, (4, 4), "nonzero") == ["####"] * 4
    assert filled(nested, (4, 4), "evenodd") == ["####", "#..#", "#..#", "####"]


def test_nonzero_hollows_when_the_inner_contour_runs_backwards() -> None:
    backwards = polygon([(1, 1), (1, 3), (3, 3), (3, 1)])
    assert filled(rect(0, 0, 4, 4).extend(backwards), (4, 4)) == ["####", "#..#", "#..#", "####"]


def test_rows_outside_the_height_are_skipped() -> None:
    assert [span.y for span in spans(rect(0, -2, 1, 9).contours(), "nonzero", 3)] == [0, 1, 2]


def test_empty_path_has_no_spans() -> None:
    assert spans(Path().contours(), "nonzero", 4) == []


def test_unknown_rule_is_an_error() -> None:
    with pytest.raises(ValueError, match="nonzero"):
        _ = spans(rect(0, 0, 1, 1).contours(), cast("FillRule", cast("object", "winding")), 4)


def test_evenodd_star_keeps_its_tips_joined() -> None:
    tips = [math.radians(-90 + tip * 144) for tip in range(5)]
    star = polygon([(16 + 14 * math.cos(a), 16 + 14 * math.sin(a)) for a in tips])
    canvas = Canvas(32, 32)
    fill(canvas, star, INK, "evenodd")
    assert components(cells_of(canvas)) == 1

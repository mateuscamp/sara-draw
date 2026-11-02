# SPDX-License-Identifier: GPL-3.0-only
import math
from typing import cast

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from ai_draw.errors import ColorError
from ai_draw.geometry.path import Path, Point, ellipse, polygon, rect
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import to_rows
from ai_draw.pixel.defects import cells_of, components, orphans
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
    bad_rule = cast("FillRule", cast("object", "winding"))  # motivo: the bad rule is the test
    with pytest.raises(ValueError, match="nonzero"):
        _ = spans(rect(0, 0, 1, 1).contours(), bad_rule, 4)


def test_evenodd_star_keeps_its_tips_joined() -> None:
    tips = [math.radians(-90 + tip * 144) for tip in range(5)]
    star = polygon([(16 + 14 * math.cos(a), 16 + 14 * math.sin(a)) for a in tips])
    canvas = Canvas(32, 32)
    fill(canvas, star, INK, "evenodd")
    assert components(cells_of(canvas)) == 1


def test_separate_shapes_close_together_in_one_path_stay_apart() -> None:
    # Regression (audit A1, 01/11): the thin-part bridge joined two subpaths 1 to 2 px apart.
    two_rects = rect(0.5, 0, 4, 4).extend(rect(5.5, 0, 4, 4))
    assert filled(two_rects, (12, 4))[0] == "####.####..."
    eyes = ellipse(3.5, 4, 2.6).extend(ellipse(9.5, 4, 2.6))
    canvas = Canvas(14, 8)
    fill(canvas, eyes, INK)
    assert components(cells_of(canvas)) == 2


def test_a_thin_ring_drawn_as_two_contours_stays_in_one_piece() -> None:
    # Regression of the A1 fix, caught by the post-audit (01/11): the ring's gaps are bridged
    # by the outline of its hole, which is another contour of the same shape.
    canvas = Canvas(30, 30)
    fill(canvas, ellipse(15, 15, 12).extend(ellipse(15, 15, 11.5)), INK, "evenodd")
    assert components(cells_of(canvas)) == 1


def test_fill_refuses_a_half_transparent_color() -> None:
    # Regression (audit M4, 01/11): pixel output is alpha 0 or 255, and 128 was written as is.
    with pytest.raises(ColorError, match="alpha"):
        fill(Canvas(8, 8), rect(1, 1, 4, 4), (20, 20, 20, 128))


_INSIDE = st.floats(1, 31)
_CORNERS = st.lists(st.tuples(_INSIDE, _INSIDE), min_size=3, max_size=3)


def _area(corners: list[Point]) -> float:
    ends = [*corners[1:], corners[0]]
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(corners, ends, strict=True))) / 2


@given(_CORNERS)
@example(corners=[(1.0, 20.0), (1.0, 21.0), (10.0, 1.0)])
def test_a_filled_triangle_is_one_piece_without_loose_pixels(corners: list[Point]) -> None:
    # Property (ADR-0006): "thin parts kept joined" (README). A sliver's gap was wider than the
    # bridge of one or two outline cells: 91 of 3,000 random triangles came out in pieces
    # (02/11). Still pending, found with --hypothesis-profile=explore: a sliver thin all along,
    # whose fill is one lone pixel, as (1, 22.5), (27, 9.25), (22.375, 12.09375).
    _ = assume(_area(corners) > 4)  # a sliver smaller than this may vanish altogether
    canvas = Canvas(32, 32)
    fill(canvas, polygon(corners), INK)
    cells = cells_of(canvas)
    assert components(cells) <= 1
    assert orphans(cells) == 0

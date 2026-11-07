# SPDX-License-Identifier: GPL-3.0-only
"""The rule of a thin contour over a thicker shape, as properties (ADR-0006).

The ink is what the shapes fill and the thin lines draw, less what a thin contour cuts from the
shapes. Examples alone could not tell a right version from a wrong one: 488 tests passed on each
of the versions the audit tried (04/11).
"""

from __future__ import annotations

import itertools
import math
import time

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from ai_draw.geometry.midline import midline
from ai_draw.geometry.path import Path, Point, ellipse, polygon, rect
from ai_draw.geometry.transform import Transform
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.pixel.defects import Cells, cells_of, components, l_corners, wobble
from ai_draw.pixel.fill import FillRule, Span, fill, spans
from ai_draw.pixel.thin import thin_parts
from ai_draw.smooth.stroke import stroke_outline

INK: Color = (20, 20, 20, 255)
SIZE = 40
_Ribbon = tuple[float, float, float, float, float, bool, bool]

_ON_CANVAS = st.floats(1, SIZE - 1).map(lambda value: round(value * 8) / 8)
_RIBBONS = st.tuples(
    _ON_CANVAS,
    _ON_CANVAS,
    _ON_CANVAS,
    _ON_CANVAS,
    st.sampled_from([0.1, 0.3, 0.5]),
    st.booleans(),
    st.booleans(),
)
_IN_THE_SQUARE = st.floats(13, 26.75).map(lambda value: round(value * 8) / 8)
_RIBBONS_IN_THE_SQUARE = st.tuples(
    _IN_THE_SQUARE,
    _IN_THE_SQUARE,
    _IN_THE_SQUARE,
    _IN_THE_SQUARE,
    st.sampled_from([0.1, 0.3, 0.5]),
    st.booleans(),
    st.booleans(),
)
_ON_THE_SQUARE = st.floats(12.5, 27.25).map(lambda value: round(value * 8) / 8)
_RIBBONS_ON_THE_SQUARE = st.tuples(
    _ON_THE_SQUARE,
    _ON_THE_SQUARE,
    _ON_THE_SQUARE,
    _ON_THE_SQUARE,
    st.sampled_from([0.1, 0.3, 0.5]),
    st.booleans(),
    st.booleans(),
)
_RULES = st.sampled_from(["nonzero", "evenodd"])
# One shape or several in the same path, with empty canvas between them: a line can leave one
# and enter the next (audit, 04/11).
_Layout = tuple[tuple[float, float, float, float], ...]
_SQUARE: _Layout = ((12.4, 12.4, 15, 15),)
_TWO: _Layout = ((3.4, 10, 12, 20), (22.4, 10, 12, 20))
_THREE: _Layout = ((2.4, 10, 8, 20), (15.4, 10, 9, 20), (30.4, 10, 7, 20))
_EDGE: _Layout = ((5, 9.8, 20, 10),)
_NARROW_GAP: _Layout = ((2, 2, 8.4, 8), (10.6, 2, 8, 8))
_LAYOUTS = st.sampled_from([_SQUARE, _TWO, _THREE, _EDGE, _NARROW_GAP])


def _corners(ribbon: _Ribbon) -> list[Point]:
    x0, y0, x1, y1, width, backwards, sideways = ribbon
    dx, dy = (width, 0.0) if sideways else (0.0, width)
    corners = [(x0, y0), (x1, y1), (x1 + dx, y1 + dy), (x0 + dx, y0 + dy)]
    return corners[::-1] if backwards else corners


def _ribbon(ribbon: _Ribbon) -> Path:
    return polygon(_corners(ribbon))


def _square() -> Path:
    return _shapes(_SQUARE)


def _shapes(layout: _Layout) -> Path:
    path = Path()
    for x, y, width, height in layout:
        _ = path.extend(rect(x, y, width, height))
    return path


def _inked(path: Path, rule: FillRule) -> Cells:
    canvas = Canvas(SIZE, SIZE)
    fill(canvas, path, INK, rule)
    return cells_of(canvas)


def _cells(found: list[Span]) -> set[tuple[int, int]]:
    return {(x, span.y) for span in found for x in range(span.x, span.x + span.length)}


def _sampled(path: Path, rule: FillRule) -> set[tuple[int, int]]:
    return _cells(spans(path.contours(), rule, SIZE))


def _is_thin(ribbon: _Ribbon) -> bool:
    return midline(_ribbon(ribbon).contours()[0].points, 1) is not None


def _in_square(x: float, y: float) -> bool:
    return 12.4 < x < 27.4 and 12.4 < y < 27.4


def _stays_on_shapes(line: tuple[Point, ...], layout: _Layout, margin: float = 0.0) -> bool:
    """The line lies on the shapes all along, ``margin`` inside them, read every 1/200 of it."""

    def on_a_shape(x: float, y: float) -> bool:
        return any(
            a + margin <= x <= a + w - margin and b + margin <= y <= b + h - margin
            for a, b, w, h in layout
        )

    return all(
        on_a_shape(x0 + (x1 - x0) * step / 200, y0 + (y1 - y0) * step / 200)
        for (x0, y0), (x1, y1) in itertools.pairwise(line)
        for step in range(201)
    )


@given(_RIBBONS, _RIBBONS, _LAYOUTS, _RULES)
@example(
    (19.5, 13.5, 19.5, 26.5, 0.5, False, True),
    (13.5, 19.5, 26.5, 19.5, 0.5, False, False),
    _SQUARE,
    "evenodd",
)
def test_what_the_whole_path_keeps_of_the_shapes_stays_painted(
    first: _Ribbon, second: _Ribbon, layout: _Layout, rule: FillRule
) -> None:
    _ = assume(_is_thin(first) and _is_thin(second))
    solid = _sampled(_shapes(layout), rule)
    whole = _sampled(_shapes(layout).extend(_ribbon(first)).extend(_ribbon(second)), rule)
    inked = _inked(_shapes(layout).extend(_ribbon(first)).extend(_ribbon(second)), rule)
    assert solid & whole <= inked


@given(_RIBBONS, _RIBBONS, _LAYOUTS, _RULES)
def test_what_the_whole_path_takes_from_the_shapes_stays_open(
    first: _Ribbon, second: _Ribbon, layout: _Layout, rule: FillRule
) -> None:
    _ = assume(_is_thin(first) and _is_thin(second))
    path = _shapes(layout).extend(_ribbon(first)).extend(_ribbon(second))
    # A hole with no wall on one side goes back to sampling, and its bridges paint it over, as on
    # main: that is the price of keeping a narrow ring whole (README).
    _ = assume(len(thin_parts(path.contours(), rule, SIZE).thick) == len(layout))
    solid = _sampled(_shapes(layout), rule)
    assert not (solid - _sampled(path, rule)) & _inked(path, rule)


@given(_RIBBONS, _LAYOUTS, _RULES)
@example((14.5, 25.5, 13.25, 27.25, 0.5, False, False), _SQUARE, "nonzero")
@example((3.0, 20.25, 36.0, 20.25, 0.5, False, False), _THREE, "evenodd")
@example((3.25, 5.2, 17.5, 5.2, 0.5, False, False), _NARROW_GAP, "evenodd")
@example((2.0, 2.0, 11.0, 2.0, 0.1, False, False), _NARROW_GAP, "evenodd")
def test_past_the_shapes_a_thin_contour_is_its_line(
    ribbon: _Ribbon, layout: _Layout, rule: FillRule
) -> None:
    # A line that stays on the shapes all along may be a hole, whatever its corners do.
    line = midline(_ribbon(ribbon).contours()[0].points, 1)
    _ = assume(line is not None and not _stays_on_shapes(line, layout))
    solid = _sampled(_shapes(layout), rule)
    assert _inked(_shapes(layout).extend(_ribbon(ribbon)), rule) - solid == (
        _inked(_ribbon(ribbon), "nonzero") - solid
    )


@given(_RIBBONS_ON_THE_SQUARE, st.just(_SQUARE))
@example((8.0, 9.625, 20.0, 9.625, 0.75, False, False), _EDGE)
@example((8.0, 9.45, 20.0, 9.45, 0.8, False, False), _EDGE)
def test_a_hole_past_the_shapes_keeps_what_the_whole_path_paints(
    ribbon: _Ribbon, layout: _Layout
) -> None:
    # Regression (audit, 04/11): a hole drew no line, and what stuck out of the shapes vanished.
    line = midline(_ribbon(ribbon).contours()[0].points, 1)
    # With a margin: a line exactly on the edge where a shape stops reads as outside (README).
    _ = assume(line is not None and _stays_on_shapes(line, layout, 0.01))
    solid = _sampled(_shapes(layout), "evenodd")
    whole = _sampled(_shapes(layout).extend(_ribbon(ribbon)), "evenodd")
    assert _inked(_shapes(layout).extend(_ribbon(ribbon)), "evenodd") - solid == whole - solid


@given(_RIBBONS_IN_THE_SQUARE)
@example((27.125, 15, 27.125, 22, 0.125, True, True))
def test_a_hole_inside_a_shape_adds_no_ink(ribbon: _Ribbon) -> None:
    _ = assume(_is_thin(ribbon) and all(_in_square(x, y) for x, y in _corners(ribbon)))
    assert _inked(_square().extend(_ribbon(ribbon)), "evenodd") <= _sampled(_square(), "evenodd")


@pytest.mark.parametrize("backwards", [False, True], ids=["forward", "backwards"])
def test_a_slit_from_edge_to_edge_adds_no_ink(backwards: bool) -> None:  # noqa: FBT001  # motivo: pytest passes the parameter by name
    # Regression (audit, 04/11): its end, on the edge where a shape stops, read as outside it.
    corners = [(18.125, 5.625), (18.25, 5.625), (18.25, 21.875), (18.125, 21.875)]
    slit = polygon(corners[::-1] if backwards else corners)
    outside = _inked(rect(5.625, 5.625, 16.25, 16.25).extend(slit), "evenodd")
    assert outside <= _sampled(rect(5.625, 5.625, 16.25, 16.25), "evenodd")


def test_two_slits_that_cross_near_an_edge_add_no_ink() -> None:
    down = polygon([(6.15, 3), (6.15, 6), (6.25, 6), (6.25, 3)])
    along = polygon([(4, 4.2), (4, 4.7), (6.35, 4.7), (6.35, 4.2)])
    square = rect(2.4, 2.4, 4, 4)
    inked = _inked(rect(2.4, 2.4, 4, 4).extend(down).extend(along), "evenodd")
    assert inked <= _sampled(square, "evenodd")


def test_a_thin_contour_on_a_shape_that_adds_ink_keeps_its_line() -> None:
    edge = polygon([(6.25, 3), (6.25, 6), (6.15, 6), (6.15, 3)])
    assert len(_inked(rect(2.4, 2.4, 4, 4).extend(edge), "nonzero")) == 19


def test_thin_contours_with_the_same_points_in_another_order_do_not_cancel_out() -> None:
    # Regression (audit, 04/11): the second crosses itself; it is another contour, not the first
    # one drawn again.
    corners = [(2.0, 10.0), (30.0, 10.2), (30.0, 10.8), (2.0, 10.6)]
    scrambled = [corners[0], corners[2], corners[1], corners[3]]
    assert _inked(polygon(corners).extend(polygon(scrambled)), "nonzero")


def test_a_contour_drawn_again_from_another_point_still_cancels_out() -> None:
    corners = [(2.0, 10.0), (30.0, 10.2), (30.0, 10.8), (2.0, 10.6)]
    assert not _inked(polygon(corners).extend(polygon([*corners[2:], *corners[:2]])), "evenodd")


@given(st.integers(0, 179), st.integers(3, 17))
@example(55, 16)
def test_a_thin_ellipse_stays_on_its_axis_at_any_angle(degrees: int, radius: int) -> None:
    # Regression (audit, 04/11): the line was straight, but the step sorting took its many short
    # segments for a curve and bent it, 2.6 pixels off at 55 degrees. Counting L corners, which
    # went down, hid this: distance to the shape is its own measure.
    turn = Transform.rotate(degrees).then(Transform.translate(20, 20))
    across = math.radians(degrees)
    inked = _inked(ellipse(0, 0, 0.25, radius).transformed(turn), "nonzero")
    off_axis = [
        abs((x + 0.5 - 20) * math.cos(across) + (y + 0.5 - 20) * math.sin(across)) for x, y in inked
    ]
    assert max(off_axis) < 1.2  # one pixel's reach, and the base reaches 1.1


def test_a_dot_smaller_than_a_pixel_has_no_l_corner() -> None:
    # Regression (audit, 04/11): every vertex lay near the tip, and the line ended on corners.
    assert l_corners(_inked(rect(8.375, 8.625, 0.75, 0.75), "nonzero")) == 0


def test_a_contour_with_a_repeated_point_cancels_out_when_drawn_both_ways() -> None:
    # Regression (audit, 04/11): the repeated point made the two ways look like two contours.
    corners = [(4.0, 4.0), (20.0, 4.0), (20.0, 4.4), (4.0, 4.4), (4.0, 4.0)]
    assert not _inked(polygon(corners).extend(polygon(corners[::-1])), "nonzero")


def test_a_repeated_point_does_not_make_another_contour() -> None:
    corners = [(4.0, 4.0), (20.0, 4.0), (20.0, 4.4), (4.0, 4.4)]
    repeated = [corners[0], corners[1], corners[1], corners[2], corners[3]]
    assert not _inked(polygon(corners).extend(polygon(repeated)), "evenodd")


@pytest.mark.parametrize(
    ("controls", "width"),
    [
        (((4, 24), (26, 38), (32, 16), (46, 14)), 0.3),
        (((14, 41), (38, 43), (13, 45), (35, 48)), 0.5),
    ],
    ids=["s_curve", "tight_s_curve"],
)
def test_a_thin_s_curve_stays_on_its_shape(
    controls: tuple[Point, Point, Point, Point], width: float
) -> None:
    # Regression (audit, 04/11): sorting the steps takes a curve that bends both ways for one
    # curve, and the line came out clean and 3 pixels off the shape. No L corner shows it.
    start, first, second, end = controls
    curve = Path().move_to(*start).cubic_to(*first, *second, *end)
    along = curve.contours()[0].points
    canvas = Canvas(64, 64)
    fill(canvas, stroke_outline(curve, width), INK)
    cells = cells_of(canvas)
    assert cells
    assert all(min(math.dist((x + 0.5, y + 0.5), p) for p in along) < 1.2 for x, y in cells)


_LONG = st.floats(10, 18).map(lambda value: round(value * 8) / 8)
_HOLE = st.floats(0.125, 0.5).map(lambda value: round(value * 8) / 8)
_WALL = st.floats(0.3, 0.9).map(lambda value: round(value * 8) / 8)


@given(_LONG, _HOLE, _WALL, st.sampled_from([0.0, 0.25, 0.5]))
@example(20.0, 0.5, 0.75, 0.5)
@example(10.0, 0.5, 0.875, 0.25)
def test_a_narrow_ring_stays_in_one_piece(
    long: float, hole: float, wall: float, shift: float
) -> None:
    # Regression (audit, 06/11): the hole, thinner than a pixel, cut walls that had no pixel center
    # of their own, and the ring came apart or vanished. A slit has pixels on both sides.
    center = 20 + shift

    def ring() -> Path:
        outer = ellipse(center, center, long + wall, hole + wall)
        return outer.extend(ellipse(center, center, long, hole))

    _ = assume(midline(ellipse(center, center, long, hole).contours()[0].points, 1) is not None)
    # At most: walls with no pixel center at all leave nothing to sample, here as on main.
    assert components(_inked(ring(), "evenodd")) <= 1


def test_a_wall_is_what_the_other_cuts_leave() -> None:
    # The slit in the middle has only slits beside it, so it has no walls: it goes back to the
    # sampled fill, and the bridge joins what the five of them part. Reading the shape and not
    # what the cuts leave kept all five open (audit, 06/11).
    path = rect(2, 2, 20, 12)
    for row in range(5, 10):
        _ = path.extend(rect(2, row + 0.2, 20, 0.6))
    canvas = Canvas(24, 16)
    fill(canvas, path, INK, "evenodd")
    assert components(cells_of(canvas)) == 1


def test_a_narrow_ring_between_other_shapes_stays_whole() -> None:
    # Regression (audit, 06/11): the shapes beside it counted as its walls, and it was cut apart.
    def scene() -> Path:
        return (
            rect(4, 2, 40, 2)
            .extend(rect(4, 7, 40, 2))
            .extend(ellipse(24, 5.5, 18, 0.75))
            .extend(ellipse(24, 5.5, 16, 0.25))
        )

    canvas = Canvas(48, 16)
    fill(canvas, scene(), INK, "evenodd")
    assert len(cells_of(canvas)) == 252


def test_a_shape_far_wider_than_the_canvas_fills_at_once() -> None:
    # Regression (audit, 06/11): reading a hole's walls listed every pixel of every shape, thin
    # contour or not: 0.1 ms became 3.6 s here, and a wider rectangle ran out of memory.
    canvas = Canvas(32, 32)
    start = time.perf_counter()
    fill(canvas, rect(0, 0, 400_000, 32), INK)
    assert time.perf_counter() - start < 0.5


def test_a_stroked_narrow_ellipse_keeps_its_outline() -> None:
    # Regression (audit, 06/11): 116 pixels in one piece became 2 loose ones.
    canvas = Canvas(48, 16)
    fill(canvas, stroke_outline(ellipse(24, 4.5, 20, 0.7), 0.5), INK)
    cells = cells_of(canvas)
    assert (len(cells) > 100, components(cells)) == (True, 1)


def test_a_crescent_keeps_its_steps_in_order() -> None:
    # Regression (audit, 06/11): one cell 1.02 pixels off its line unsorted the whole curve.
    moon = Path().move_to(8.5, 20.75).quad_to(28.5, 60.75, 48.5, 20.75)
    moon = moon.quad_to(28.5, 62.35, 8.5, 20.75).close()
    canvas = Canvas(64, 64)
    fill(canvas, moon, INK)
    assert wobble(cells_of(canvas), 1) == 0


def test_a_pixel_under_two_thin_slits_follows_the_rule() -> None:
    # Regression (audit, 04/11): each slit was judged alone, and this pixel, inside the path by
    # the rule, was left out.
    across = polygon([(3.45, 1), (3.45, 7), (3.55, 7), (3.55, 1)])
    along = polygon([(1, 3.45), (7, 3.45), (7, 3.55), (1, 3.55)])
    canvas = Canvas(SIZE, SIZE)
    fill(canvas, rect(0, 0, 8, 8).extend(across).extend(along), INK, "evenodd")
    assert (3, 3) in cells_of(canvas)


def test_a_thin_contour_that_crosses_itself_keeps_the_sampled_fill() -> None:
    # Regression (audit, 04/11): under the middle of its line lay nothing, and it vanished.
    fold = polygon([(34.8, 27), (35.2, 34), (34.2, 23), (33.8, 23), (34.8, 34), (35.2, 27)])
    assert len(_inked(fold, "nonzero")) == 5


def test_a_ring_is_cut_like_a_square() -> None:
    ring = ellipse(20, 20, 16).extend(ellipse(20, 20, 10))
    across = rect(1, 20.2, 38, 0.6)
    solid = _sampled(ellipse(20, 20, 16).extend(ellipse(20, 20, 10)), "evenodd")
    inked = _inked(ring.extend(across), "evenodd")
    assert not {(x, y) for x, y in solid if y == 20} & inked


def test_a_cut_in_one_span_leaves_the_others_of_its_row_alone() -> None:
    ring = ellipse(20, 20, 16).extend(ellipse(20, 20, 10))
    across_one_side = rect(32, 20.2, 7, 0.6)
    inked = _inked(ring.extend(across_one_side), "evenodd")
    assert (20, 20) not in inked
    assert {(x, 20) for x in range(5, 10)} <= inked

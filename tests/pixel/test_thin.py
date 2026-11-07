# SPDX-License-Identifier: GPL-3.0-only
"""The rule of a thin contour over a thicker shape, as properties (ADR-0006).

The ink is what the shapes fill and the thin lines draw, less what a thin contour cuts from the
shapes. Examples alone could not tell a right version from a wrong one: 488 tests passed on each
of the versions the audit tried (04/11).
"""

from __future__ import annotations

import math

from hypothesis import example, given
from hypothesis import strategies as st

from ai_draw.geometry.path import Path, ellipse, rect
from ai_draw.geometry.transform import Transform
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.pixel.defects import Cells, cells_of, l_corners
from ai_draw.pixel.fill import FillRule, fill

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


def _inked(path: Path, rule: FillRule) -> Cells:
    canvas = Canvas(SIZE, SIZE)
    fill(canvas, path, INK, rule)
    return cells_of(canvas)


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


_LONG = st.floats(10, 18).map(lambda value: round(value * 8) / 8)
_HOLE = st.floats(0.125, 0.5).map(lambda value: round(value * 8) / 8)
_WALL = st.floats(0.3, 0.9).map(lambda value: round(value * 8) / 8)

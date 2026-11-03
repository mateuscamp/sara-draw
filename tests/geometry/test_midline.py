# SPDX-License-Identifier: GPL-3.0-only
from ai_draw.geometry.midline import midline
from ai_draw.geometry.path import Path, Point, polygon, rect


def _points(path: Path) -> tuple[Point, ...]:
    return path.contours()[0].points


def test_a_thin_rectangle_runs_from_the_middle_of_one_end_to_the_other() -> None:
    line = midline(_points(rect(0, 10, 20, 0.5)), 1)
    assert line is not None
    assert {line[0], line[-1]} == {(0, 10.25), (20, 10.25)}
    assert all(y == 10.25 for _, y in line)


def test_a_thin_triangle_ends_at_its_tip_and_on_its_short_side() -> None:
    line = midline(_points(polygon([(0, 0), (10, 1), (0, 0.5)])), 1)
    assert line is not None
    tip, blunt = sorted([line[0], line[-1]], reverse=True)
    assert tip == (10, 1)
    assert blunt[0] == 0
    assert 0 < blunt[1] < 0.5


def test_a_shape_as_wide_as_the_width_has_no_middle_line() -> None:
    assert midline(_points(rect(0.2, 0.2, 1, 1)), 1) is None


def test_a_flat_shape_has_no_middle_line() -> None:
    # Its fill is empty, as it has no area; the line along it is ai_draw.pixel.line's (audit B5).
    assert midline(_points(rect(0, 4, 8, 0)), 1) is None

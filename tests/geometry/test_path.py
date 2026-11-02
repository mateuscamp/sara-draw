# SPDX-License-Identifier: GPL-3.0-only
import math
from collections.abc import Callable

import pytest

from ai_draw.errors import GeometryError
from ai_draw.geometry.path import Contour, Path, ellipse, polygon, rect
from ai_draw.geometry.transform import Transform


def only_contour(path: Path) -> Contour:
    contours = path.contours()
    assert len(contours) == 1
    return contours[0]


def test_rect_is_one_closed_contour_of_four_corners() -> None:
    assert rect(0, 0, 4, 2).contours() == [Contour(((0, 0), (4, 0), (4, 2), (0, 2)), closed=True)]


def test_open_path_is_not_closed() -> None:
    contours = Path().move_to(0, 0).line_to(3, 0).contours()
    assert contours == [Contour(((0, 0), (3, 0)), closed=False)]


DRAW_COMMANDS: dict[str, Callable[[Path], Path]] = {
    "line": lambda path: path.line_to(1, 1),
    "quad": lambda path: path.quad_to(1, 1, 2, 2),
    "cubic": lambda path: path.cubic_to(1, 1, 2, 2, 3, 3),
    "close": lambda path: path.close(),
}


@pytest.mark.parametrize("command", sorted(DRAW_COMMANDS))
def test_drawing_before_move_to_is_an_error(command: str) -> None:
    draw = DRAW_COMMANDS[command]
    with pytest.raises(ValueError, match="move_to"):
        _ = draw(Path())


def test_drawing_after_close_needs_a_new_move_to() -> None:
    path = rect(0, 0, 1, 1)
    with pytest.raises(ValueError, match="move_to"):
        _ = path.line_to(5, 5)


def test_curve_gets_one_segment_per_unit_of_control_polygon() -> None:
    contour = only_contour(Path().move_to(0, 0).quad_to(5, 0, 10, 0))
    assert len(contour.points) == 11
    assert [x for x, _ in contour.points] == pytest.approx([float(n) for n in range(11)])


def test_curve_ends_exactly_on_its_end_point() -> None:
    contour = only_contour(Path().move_to(0, 0).cubic_to(1, 7, 3, 9, 10 / 3, 1 / 3))
    assert contour.points[-1] == (10 / 3, 1 / 3)


def test_long_curve_is_capped_at_256_segments() -> None:
    contour = only_contour(Path().move_to(0, 0).quad_to(500, 0, 1000, 0))
    assert len(contour.points) == 257


def test_polygon_needs_three_points() -> None:
    with pytest.raises(ValueError, match="3 points"):
        _ = polygon([(0, 0), (1, 1)])


def test_polygon_closes_its_points() -> None:
    triangle = polygon([(0, 0), (4, 0), (0, 3)])
    assert triangle.contours() == [Contour(((0, 0), (4, 0), (0, 3)), closed=True)]


def test_ellipse_starts_at_the_right_and_passes_through_the_bottom() -> None:
    contour = only_contour(ellipse(0, 0, 10, 5))
    assert contour.closed
    assert contour.points[0] == (10, 0)
    assert (0, 5) in contour.points


def test_ellipse_with_one_radius_is_a_circle() -> None:
    contour = only_contour(ellipse(0, 0, 4))
    assert (0, 4) in contour.points
    assert (-4, 0) in contour.points


def test_extend_keeps_each_subpath() -> None:
    ring = ellipse(0, 0, 9).extend(ellipse(0, 0, 5))
    assert len(ring.contours()) == 2


def test_transformed_moves_every_point_and_keeps_the_original() -> None:
    square = rect(0, 0, 1, 1)
    moved = square.transformed(Transform.translate(2, 3))
    assert moved.contours() == [Contour(((2, 3), (3, 3), (3, 4), (2, 4)), closed=True)]
    assert square.contours() == [Contour(((0, 0), (1, 0), (1, 1), (0, 1)), closed=True)]


def test_finer_flattening_multiplies_the_segments() -> None:
    (contour,) = Path().move_to(0, 0).quad_to(5, 0, 10, 0).contours(segments_per_pixel=4)
    assert len(contour.points) == 41


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_a_point_that_is_not_a_finite_number_is_refused(bad: float) -> None:
    # Regression (audit M5, 01/11): NaN and inf reached the rasterizer and failed there with
    # a plain ValueError or OverflowError, outside the library's error family.
    with pytest.raises(GeometryError, match="finite"):
        _ = Path().move_to(0, 0).line_to(bad, 1)

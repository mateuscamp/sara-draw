# SPDX-License-Identifier: GPL-3.0-only
from collections.abc import Callable

import pytest

from ai_draw.errors import CanvasError, ColorError, DrawingError, GeometryError, SettingError
from ai_draw.geometry.path import Path, polygon, rect
from ai_draw.grid.canvas import Canvas
from ai_draw.grid.noise import speckle
from ai_draw.grid.palette import parse_hex
from ai_draw.grid.rows import from_rows
from ai_draw.io.scene import SceneError
from ai_draw.pixel import stroke as pixel_stroke
from ai_draw.pixel.fill import spans
from ai_draw.smooth import stroke as smooth_stroke

INK = (20, 20, 20, 255)


def test_every_error_is_a_drawing_error_and_a_value_error() -> None:
    for error in (GeometryError, ColorError, CanvasError, SettingError, SceneError):
        assert issubclass(error, DrawingError)
        assert issubclass(error, ValueError)


CASES: list[tuple[type[DrawingError], Callable[[], object]]] = [
    (GeometryError, lambda: Path().line_to(1, 1)),
    (GeometryError, lambda: polygon([(0, 0)])),
    (ColorError, lambda: parse_hex("zz")),
    (ColorError, lambda: Canvas(1, 1).paint(0, 0, (256, 0, 0, 255))),
    (CanvasError, lambda: Canvas(0, 1)),
    (CanvasError, lambda: from_rows([], {})),
    (SettingError, lambda: spans(rect(0, 0, 1, 1).contours(), "winding", 4)),  # pyright: ignore[reportArgumentType]  # motivo: the bad rule is the test
    (SettingError, lambda: pixel_stroke.stroke(Canvas(2, 2), rect(0, 0, 1, 1), INK, 0)),
    (SettingError, lambda: smooth_stroke.stroke(Canvas(2, 2), rect(0, 0, 1, 1), INK, 0)),
    (SettingError, lambda: speckle(Canvas(2, 2), 0, 0, 2, 2, colors=[INK], chance=2, seed=1)),
]


@pytest.mark.parametrize(("expected", "action"), CASES)
def test_each_bad_input_raises_its_own_kind_of_error(
    expected: type[DrawingError], action: Callable[[], object]
) -> None:
    with pytest.raises(ValueError) as caught:  # noqa: PT011  # motivo: the kind is checked below
        _ = action()
    assert isinstance(caught.value, expected)

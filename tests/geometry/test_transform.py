# SPDX-License-Identifier: GPL-3.0-only
import math
from collections.abc import Callable

import pytest

from ai_draw.errors import GeometryError
from ai_draw.geometry.transform import Transform


def test_translate_moves_the_point() -> None:
    assert Transform.translate(3, -2).apply(1, 1) == (4, -1)


def test_scale_with_one_factor_is_uniform() -> None:
    assert Transform.scale(2).apply(3, 4) == (6, 8)


def test_scale_with_two_factors_stretches_each_axis() -> None:
    assert Transform.scale(2, 3).apply(1, 1) == (2, 3)


def test_identity_keeps_the_point() -> None:
    assert Transform.identity().apply(5, 7) == (5, 7)


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [(90, (0, 1)), (180, (-1, 0)), (270, (0, -1)), (-90, (0, -1)), (360, (1, 0))],
)
def test_quarter_turns_are_exact(degrees: float, expected: tuple[float, float]) -> None:
    # y grows downward, so a positive angle turns clockwise on screen
    assert Transform.rotate(degrees).apply(1, 0) == expected


def test_rotate_45_lands_on_the_diagonal() -> None:
    half = math.sqrt(0.5)
    assert Transform.rotate(45).apply(1, 0) == pytest.approx((half, half))


def test_then_applies_self_first() -> None:
    turn_then_move = Transform.rotate(90).then(Transform.translate(32, 32))
    assert turn_then_move.apply(1, 0) == (32, 33)


@pytest.mark.parametrize(
    "build",
    [
        lambda: Transform.rotate(math.nan),
        lambda: Transform.scale(math.inf),
        lambda: Transform.translate(0, math.nan),
    ],
)
def test_a_transform_that_is_not_finite_is_refused(build: Callable[[], Transform]) -> None:
    with pytest.raises(GeometryError, match="finite"):
        _ = build()

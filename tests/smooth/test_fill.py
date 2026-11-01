# SPDX-License-Identifier: GPL-3.0-only
from ai_draw.geometry.path import rect
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.smooth.coverage import fill

ORANGE: Color = (200, 100, 50, 255)


def test_full_coverage_paints_the_exact_color() -> None:
    canvas = Canvas(1, 1)
    fill(canvas, rect(0, 0, 1, 1), ORANGE)
    assert canvas.color_at(0, 0) == ORANGE


def test_half_coverage_on_transparency_keeps_the_color_at_half_alpha() -> None:
    canvas = Canvas(1, 1)
    fill(canvas, rect(0, 0, 0.5, 1), ORANGE)
    assert canvas.color_at(0, 0) == (200, 100, 50, 128)


def test_half_coverage_on_an_opaque_ground_mixes_the_colors() -> None:
    canvas = Canvas(1, 1)
    canvas.paint(0, 0, (0, 0, 0, 255))
    fill(canvas, rect(0, 0, 0.5, 1), ORANGE)
    assert canvas.color_at(0, 0) == (100, 50, 25, 255)


def test_a_translucent_color_keeps_its_own_alpha() -> None:
    canvas = Canvas(1, 1)
    fill(canvas, rect(0, 0, 1, 1), (200, 100, 50, 128))
    assert canvas.color_at(0, 0) == (200, 100, 50, 128)

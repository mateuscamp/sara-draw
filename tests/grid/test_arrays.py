# SPDX-License-Identifier: GPL-3.0-only
from ai_draw.grid.arrays import blend
from ai_draw.grid.canvas import Canvas


def test_coverage_too_small_to_show_leaves_the_pixel_untouched() -> None:
    # Regression (audit M8, 01/11): a 1e-17 float residue wrote the color with alpha 0, and
    # a canvas that looks clear compared as different from a clear one.
    canvas = Canvas(2, 1)
    blend(canvas.pixels, [[1e-17, 1 / 600]], (200, 40, 40, 255))
    assert canvas.pixels.tolist() == Canvas(2, 1).pixels.tolist()


def test_a_faint_ground_still_takes_a_little_paint() -> None:
    # Regression (review of M8, 01/11): a threshold on coverage skipped this pixel, whose
    # color changes a lot under source-over because its own alpha is tiny.
    canvas = Canvas(1, 1)
    canvas.pixels[0, 0] = (200, 0, 0, 1)
    blend(canvas.pixels, [[0.0019]], (0, 0, 255, 255))
    assert canvas.pixels.tolist() == [[[135, 0, 83, 1]]]

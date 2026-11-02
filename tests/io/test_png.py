# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

from PIL import Image

from ai_draw.grid.canvas import Canvas
from ai_draw.io.png import read_png, write_png


def test_png_round_trip_keeps_every_channel(tmp_path: Path) -> None:
    canvas = Canvas(3, 2)
    canvas.paint(0, 0, (255, 0, 0, 255))
    canvas.paint(2, 1, (1, 2, 3, 128))
    target = tmp_path / "out" / "picture.png"
    write_png(canvas, target)
    assert read_png(target).same_pixels(canvas)


def test_read_png_turns_rgb_into_opaque_rgba(tmp_path: Path) -> None:
    target = tmp_path / "rgb.png"
    Image.new("RGB", (2, 1), (10, 20, 30)).save(target)
    canvas = read_png(target)
    assert canvas.color_at(1, 0) == (10, 20, 30, 255)


def test_read_png_scales_16_bit_gray_down_to_8_bits(tmp_path: Path) -> None:
    # Regression (audit B2, 02/11): 16-bit gray was clipped to 255 and every light pixel read white.
    target = tmp_path / "gray16.png"
    Image.frombytes("I;16", (3, 1), bytes([0, 0, 0, 128, 255, 255])).save(target)
    canvas = read_png(target)
    assert [canvas.color_at(x, 0) for x in range(3)] == [
        (0, 0, 0, 255),
        (128, 128, 128, 255),
        (255, 255, 255, 255),
    ]

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

# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import pytest

from ai_draw.cli import main
from ai_draw.io.png import read_png

SCENE = """
from ai_draw.geometry.path import ellipse
from ai_draw.grid.canvas import Canvas
from ai_draw.pixel.fill import fill


def draw() -> Canvas:
    canvas = Canvas(16, 12)
    fill(canvas, ellipse(8, 6, 5, 4), (200, 40, 40, 255))
    return canvas
"""


def write_scene(tmp_path: Path, source: str = SCENE) -> Path:
    scene = tmp_path / "scene.py"
    _ = scene.write_text(source, encoding="utf-8")
    return scene


def test_render_writes_the_png_next_to_the_scene(tmp_path: Path) -> None:
    scene = write_scene(tmp_path)
    assert main(["render", str(scene)]) == 0
    canvas = read_png(tmp_path / "scene.png")
    assert (canvas.width, canvas.height) == (16, 12)
    assert canvas.color_at(8, 6) == (200, 40, 40, 255)


def test_render_scale_enlarges_and_output_picks_the_file(tmp_path: Path) -> None:
    target = tmp_path / "big.png"
    assert main(["render", str(write_scene(tmp_path)), "--scale", "3", "-o", str(target)]) == 0
    assert (read_png(target).width, read_png(target).height) == (48, 36)


def test_render_is_deterministic(tmp_path: Path) -> None:
    scene = write_scene(tmp_path)
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    assert main(["render", str(scene), "-o", str(first)]) == 0
    assert main(["render", str(scene), "-o", str(second)]) == 0
    assert read_png(first).same_pixels(read_png(second))


@pytest.mark.parametrize(
    ("source", "message"),
    [("x = 1\n", "draw()"), ("def draw():\n    return 3\n", "Canvas")],
)
def test_scene_without_a_canvas_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source: str, message: str
) -> None:
    assert main(["render", str(write_scene(tmp_path, source))]) == 2
    assert message in capsys.readouterr().err

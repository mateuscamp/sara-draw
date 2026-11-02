# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import pytest

from ai_draw.cli import main
from ai_draw.grid.canvas import Canvas
from ai_draw.io.png import read_png, write_png

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


def test_watch_once_draws_without_opening_a_viewer(tmp_path: Path) -> None:
    scene = write_scene(tmp_path)
    assert main(["watch", str(scene), "--once", "--no-viewer", "--scale", "2"]) == 0
    assert (tmp_path / "scene.png").exists()
    assert read_png(tmp_path / "scene.png").width == 32


def test_watch_once_reports_a_broken_scene(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scene = write_scene(tmp_path, "x = 1\n")
    assert main(["watch", str(scene), "--once", "--no-viewer"]) == 2
    assert "draw()" in capsys.readouterr().err


def test_palette_lists_the_colors_in_use_and_the_near_pairs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = """
from ai_draw.grid.canvas import Canvas


def draw() -> Canvas:
    canvas = Canvas(3, 1)
    canvas.paint(0, 0, (200, 40, 40, 255))
    canvas.paint(1, 0, (200, 40, 40, 255))
    canvas.paint(2, 0, (204, 42, 40, 255))
    return canvas
"""
    assert main(["palette", str(write_scene(tmp_path, source)), "--near", "5"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["#c82828  2 px", "#cc2a28  1 px", "near: #c82828 #cc2a28"]


def test_lint_reports_and_fails_on_a_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = """
from ai_draw.grid.canvas import Canvas


def draw() -> Canvas:
    canvas = Canvas(3, 3)
    canvas.paint(1, 1, (200, 40, 40, 255))
    return canvas
"""
    assert main(["lint", str(write_scene(tmp_path, source))]) == 1
    assert "loose pixels: 1" in capsys.readouterr().out.splitlines()


def test_lint_reads_a_png_and_passes_a_clean_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = Canvas(2, 1)
    clean.rect(0, 0, 2, 1, (200, 40, 40, 255))
    target = tmp_path / "clean.png"
    write_png(clean, target)
    assert main(["lint", str(target)]) == 0
    assert "loose pixels: 0" in capsys.readouterr().out.splitlines()


# Regression (audit A4, 01/11): lint exits 0 when clean and 1 on a finding, so a bad input
# must not look like either; it exits 2, like the other commands' scene errors.
CLEAN_SCENE = """
from ai_draw.grid.canvas import Canvas


def draw() -> Canvas:
    canvas = Canvas(2, 1)
    canvas.rect(0, 0, 2, 1, (200, 40, 40, 255))
    return canvas
"""


@pytest.mark.parametrize(
    "arguments",
    [
        ["--line", "#ff00ff"],
        ["--line", "#c82828", "--width", "0"],
    ],
    ids=["line color not in the picture", "width 0"],
)
def test_lint_with_a_bad_setting_exits_2(tmp_path: Path, arguments: list[str]) -> None:
    assert main(["lint", str(write_scene(tmp_path, CLEAN_SCENE)), *arguments]) == 2


@pytest.mark.parametrize("command", ["lint", "render", "palette"])
def test_a_scene_that_does_not_run_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    assert main([command, str(write_scene(tmp_path, "def draw(:\n"))]) == 2
    assert "SyntaxError" in capsys.readouterr().err


def test_lint_reads_a_png_whatever_the_case_of_its_suffix(tmp_path: Path) -> None:
    clean = Canvas(2, 1)
    clean.rect(0, 0, 2, 1, (200, 40, 40, 255))
    target = tmp_path / "CLEAN.PNG"
    write_png(clean, target)
    assert main(["lint", str(target)]) == 0


def test_render_to_a_place_it_cannot_write_exits_2(tmp_path: Path) -> None:
    # Regression (audit M7, 01/11): the failed write left a traceback and exit 1.
    blocker = tmp_path / "a_file"
    _ = blocker.write_text("", encoding="utf-8")
    assert main(["render", str(write_scene(tmp_path)), "-o", str(blocker / "out.png")]) == 2

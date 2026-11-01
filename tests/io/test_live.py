# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_draw.io.live import LiveSession, run
from ai_draw.io.png import read_png

if TYPE_CHECKING:
    from pathlib import Path

    from ai_draw.grid.canvas import Color

RED: Color = (255, 0, 0, 255)
BLUE: Color = (0, 0, 255, 255)
SCENE = """
from ai_draw.grid.canvas import Canvas


def draw() -> Canvas:
    canvas = Canvas(2, 1)
    canvas.paint(0, 0, {color})
    return canvas
"""


def write_scene(path: Path, color: Color = RED) -> Path:
    _ = path.write_text(SCENE.format(color=color), encoding="utf-8")
    return path


def session_in(tmp_path: Path, scale: int = 1) -> LiveSession:
    return LiveSession(write_scene(tmp_path / "scene.py"), tmp_path / "live.png", scale=scale)


def test_first_poll_draws_the_scene(tmp_path: Path) -> None:
    result = session_in(tmp_path, scale=3).poll()
    assert result is not None
    assert result.drew
    assert (tmp_path / "live.png").exists()
    assert read_png(tmp_path / "live.png").width == 6


def test_poll_without_changes_does_nothing(tmp_path: Path) -> None:
    session = session_in(tmp_path)
    assert session.poll() is not None
    assert session.poll() is None


def test_poll_redraws_after_the_scene_is_saved(tmp_path: Path) -> None:
    session = session_in(tmp_path)
    _ = session.poll()
    _ = write_scene(tmp_path / "scene.py", BLUE)
    result = session.poll()
    assert result is not None
    assert result.drew
    assert read_png(tmp_path / "live.png").color_at(0, 0) == BLUE


def test_poll_redraws_when_a_watched_file_changes(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    _ = notes.write_text("one", encoding="utf-8")
    scene = write_scene(tmp_path / "scene.py")
    session = LiveSession(scene, tmp_path / "live.png", also=[notes])
    _ = session.poll()
    _ = notes.write_text("two", encoding="utf-8")
    result = session.poll()
    assert result is not None
    assert result.drew


def test_broken_scene_is_reported_and_the_last_good_image_stays(tmp_path: Path) -> None:
    session = session_in(tmp_path)
    _ = session.poll()
    _ = (tmp_path / "scene.py").write_text("def draw(:\n", encoding="utf-8")
    result = session.poll()
    assert result is not None
    assert not result.drew
    assert "SyntaxError" in result.message
    assert read_png(tmp_path / "live.png").color_at(0, 0) == RED


def test_scene_imports_its_sibling_modules_and_sees_their_edits(tmp_path: Path) -> None:
    tint = tmp_path / "tint_for_live_test.py"
    _ = tint.write_text(f"COLOR = {RED}\n", encoding="utf-8")
    scene = tmp_path / "scene.py"
    source = SCENE.replace("{color}", "COLOR").replace(
        "from ai", "from tint_for_live_test import COLOR\nfrom ai"
    )
    _ = scene.write_text(source, encoding="utf-8")
    session = LiveSession(scene, tmp_path / "live.png", also=[tint])
    first = session.poll()
    assert first is not None
    assert first.drew, first.message
    _ = tint.write_text(f"COLOR = {BLUE}\n", encoding="utf-8")
    _ = session.poll()
    assert read_png(tmp_path / "live.png").color_at(0, 0) == BLUE


class FakeViewer:
    """Records what the live loop opens and closes, in place of imv."""

    def __init__(self) -> None:
        self.opened: list[Path] = []
        self.closed: int = 0

    def open(self, output: Path) -> FakeViewer:
        self.opened.append(output)
        return self

    def terminate(self) -> None:
        self.closed += 1


def test_run_polls_until_told_to_stop_and_logs_each_drawing(tmp_path: Path) -> None:
    rounds = iter([True, True, False])
    logs: list[str] = []
    run(
        session_in(tmp_path),
        viewer=None,
        interval=0,
        keep_going=lambda: next(rounds),
        log=logs.append,
    )
    assert len(logs) == 1
    assert "scene.py" in logs[0]


def test_run_opens_the_viewer_once_and_closes_it_at_the_end(tmp_path: Path) -> None:
    rounds = iter([True, True, False])
    viewer = FakeViewer()
    run(
        session_in(tmp_path),
        viewer=viewer.open,
        interval=0,
        keep_going=lambda: next(rounds),
        log=lambda _: None,
    )
    assert viewer.opened == [tmp_path / "live.png"]
    assert viewer.closed == 1

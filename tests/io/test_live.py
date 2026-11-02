# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ai_draw.io.live import LiveSession, run
from ai_draw.io.live import _forget_siblings as forget_siblings  # pyright: ignore[reportPrivateUsage]  # motivo: the rule that keeps ai_draw loaded has no public door
from ai_draw.io.png import read_png

if TYPE_CHECKING:
    import pytest

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


def scene_using(tmp_path: Path, module: str) -> Path:
    scene = tmp_path / "scene.py"
    source = SCENE.replace("{color}", "COLOR").replace(
        "from ai", f"from {module} import COLOR\nfrom ai"
    )
    _ = scene.write_text(source, encoding="utf-8")
    return scene


def test_a_helper_edited_twice_in_the_same_second_still_reloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression (audit M6, 01/11): same size and same mtime, so the cached .pyc won. The
    # bytecode is switched on here because a PYTHONDONTWRITEBYTECODE shell would hide it.
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    tint = tmp_path / "tint_same_second.py"
    _ = tint.write_text(f"COLOR = {RED}\n", encoding="utf-8")
    stamp = tint.stat().st_mtime_ns
    session = LiveSession(
        scene_using(tmp_path, "tint_same_second"), tmp_path / "live.png", also=[tint]
    )
    _ = session.poll()
    _ = tint.write_text(f"COLOR = {BLUE}\n", encoding="utf-8")
    os.utime(tint, ns=(stamp, stamp))
    _ = session.poll()
    assert read_png(tmp_path / "live.png").color_at(0, 0) == BLUE


def test_a_helper_in_a_subfolder_reloads_too(tmp_path: Path) -> None:
    package = tmp_path / "live_helpers"
    package.mkdir()
    tint = package / "tint.py"
    _ = tint.write_text(f"COLOR = {RED}\n", encoding="utf-8")
    session = LiveSession(
        scene_using(tmp_path, "live_helpers.tint"), tmp_path / "live.png", also=[tint]
    )
    _ = session.poll()
    _ = tint.write_text(f"COLOR = {BLUE}\n", encoding="utf-8")
    _ = session.poll()
    assert read_png(tmp_path / "live.png").color_at(0, 0) == BLUE


def test_a_picture_that_cannot_be_written_is_reported_and_the_session_goes_on(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "a_file"
    _ = blocker.write_text("", encoding="utf-8")
    session = LiveSession(write_scene(tmp_path / "scene.py"), blocker / "live.png")
    result = session.poll()
    assert result is not None
    assert not result.drew
    assert "Error" in result.message


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


def test_a_bytecode_cache_it_cannot_delete_does_not_end_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression (review of M6, 01/11): a read-only __pycache__ raised out of poll().
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    tint = tmp_path / "tint_read_only.py"
    _ = tint.write_text(f"COLOR = {RED}\n", encoding="utf-8")
    session = LiveSession(
        scene_using(tmp_path, "tint_read_only"), tmp_path / "live.png", also=[tint]
    )
    _ = session.poll()
    cache = tmp_path / "__pycache__"
    cache.chmod(0o500)
    try:
        _ = tint.write_text(f"COLOR = {BLUE}\n", encoding="utf-8")
        result = session.poll()
    finally:
        cache.chmod(0o700)
    assert result is not None
    assert result.drew, result.message


def test_a_scene_next_to_the_package_keeps_ai_draw_loaded() -> None:
    # Regression (review of M6, 01/11): from src/, ai_draw/ is a sibling folder, and forgetting
    # it gave the scene a second Canvas class: "draw() returned Canvas, expected a Canvas".
    package = sys.modules["ai_draw.grid.canvas"]
    source_folder = Path(package.__file__ or "").resolve().parents[2]
    forget_siblings(source_folder)
    assert sys.modules.get("ai_draw.grid.canvas") is package

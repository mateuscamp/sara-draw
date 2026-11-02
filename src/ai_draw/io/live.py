# SPDX-License-Identifier: GPL-3.0-only
"""Live drawing: save the scene and the picture redraws.

Every time the scene file (or a file passed in ``also``) changes, the scene runs again, the
PNG is rewritten and the viewer (imv) reloads it by itself. An error in the scene shows up in
the log and the picture keeps the last good drawing: a typo closes nothing.

Change is found by rereading the watched files every ``INTERVAL`` seconds. It costs less than
it seems: a scene is a few kilobytes.

    session = LiveSession(Path("scene.py"), Path("scene.png"), scale=8)
    run(session, viewer=open_imv, interval=INTERVAL, keep_going=lambda: True, log=print)
"""

from __future__ import annotations

import contextlib
import importlib
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Protocol

from ai_draw.io.png import write_png
from ai_draw.io.scene import load_scene

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

INTERVAL = 0.2
_PACKAGE = __name__.partition(".")[0]


class Viewer(Protocol):
    """A window showing the PNG; the live loop only needs to close it."""

    def terminate(self) -> None:
        """Close the window."""


class PollResult(NamedTuple):
    """What a poll did: ``drew`` is False when the scene failed and the old picture stayed."""

    drew: bool
    message: str


def open_imv(output: Path) -> Viewer:
    """Open imv on ``output``; imv reloads the file by itself when it changes."""
    return subprocess.Popen(["imv", str(output)])  # noqa: S603, S607  # motivo: fixed command, the user's viewer


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return b""


def _imported_from(folder: Path, name: str, file: object) -> bool:
    """True when the module came in through the scene's folder, as ``helper`` or ``pkg.helper``.

    Its top-level name must live in that folder: numpy or ai_draw under a ``.venv`` or ``src``
    inside it came in through their own sys.path entry, and dropping them would break them.
    """
    top_name = name.partition(".")[0]
    top = folder / top_name
    # ai_draw itself never goes, even from src/: a second Canvas class would fail every scene.
    if top_name == _PACKAGE or not (top.is_dir() or top.with_suffix(".py").is_file()):
        return False
    return isinstance(file, str) and Path(file).resolve().is_relative_to(folder)


def _forget_siblings(folder: Path) -> None:
    """Forget the modules imported from the scene's folder, so an edited helper reloads.

    Their cached bytecode goes too: an edit in the same second, of the same size, would pass
    the .pyc's timestamp check and load the old code (audit M6).
    """
    for name, module in list(sys.modules.items()):
        if _imported_from(folder, name, getattr(module, "__file__", None)):
            del sys.modules[name]
            _drop_bytecode(getattr(module, "__cached__", None))
    importlib.invalidate_caches()


def _drop_bytecode(cached: object) -> None:
    """Delete a stale .pyc if it can; a cache it cannot delete must not end the session."""
    if isinstance(cached, str):
        with contextlib.suppress(OSError):
            Path(cached).unlink(missing_ok=True)


class LiveSession:
    """Redraws ``scene`` into ``output`` when a watched file changes."""

    def __init__(
        self, scene: Path, output: Path, *, scale: int = 1, also: Sequence[Path] = ()
    ) -> None:
        """Watch ``scene`` and the files in ``also``; draw enlarged ``scale`` times."""
        self.scene: Path = scene
        self.output: Path = output
        self._scale: int = scale
        self._watched: tuple[Path, ...] = (scene, *also)
        self._signature: bytes | None = None

    def poll(self) -> PollResult | None:
        """Draw if a watched file changed since the last poll; None when nothing changed."""
        signature = b"\0".join(_read(path) for path in self._watched)
        if signature == self._signature:
            return None
        self._signature = signature
        return self._draw()

    def _draw(self) -> PollResult:
        _forget_siblings(self.scene.resolve().parent)
        try:
            canvas = load_scene(self.scene).enlarged(self._scale)
            write_png(canvas, self.output)
        except Exception as error:  # noqa: BLE001  # motivo: a broken scene or a failed write must not end the session
            reason = f"{type(error).__name__}: {error}"
            return PollResult(drew=False, message=f"{reason}; kept the last good picture")
        size = f"{canvas.width}x{canvas.height}"
        return PollResult(drew=True, message=f"drew {self.scene.name} -> {self.output} ({size})")


def _open(viewer: Callable[[Path], Viewer] | None, output: Path) -> Viewer | None:
    return viewer(output) if viewer is not None and output.exists() else None


def run(
    session: LiveSession,
    *,
    viewer: Callable[[Path], Viewer] | None,
    interval: float,
    keep_going: Callable[[], bool],
    log: Callable[[str], None],
) -> None:
    """Poll every ``interval`` seconds while ``keep_going()``.

    The viewer opens on the first picture and closes when the loop ends, Ctrl-C included.
    """
    opened: Viewer | None = None
    try:
        while keep_going():
            result = session.poll()
            if result is not None:
                log(result.message)
            opened = opened if opened is not None else _open(viewer, session.output)
            time.sleep(interval)
    except KeyboardInterrupt:
        log("stopped")
    finally:
        if opened is not None:
            opened.terminate()

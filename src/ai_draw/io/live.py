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


def _forget_siblings(folder: Path) -> None:
    """Forget the modules loaded from the scene's own folder, so an edited helper reloads.

    Only that folder: dropping numpy or ai_draw from sys.modules would break them.
    """
    for name, module in list(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if isinstance(file, str) and Path(file).resolve().parent == folder:
            del sys.modules[name]


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
        except Exception as error:  # noqa: BLE001  # motivo: a broken scene must not end the session
            reason = f"{type(error).__name__}: {error}"
            return PollResult(drew=False, message=f"{reason}; kept the last good picture")
        write_png(canvas, self.output)
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

# SPDX-License-Identifier: GPL-3.0-only
"""Scene files, which ``ai-draw render`` and ``ai-draw watch`` run.

A scene is a Python file with a ``draw()`` that returns a ``Canvas``::

    from ai_draw.grid.canvas import Canvas

    def draw() -> Canvas:
        return Canvas(16, 16)
"""

from __future__ import annotations

import runpy
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

from ai_draw.errors import DrawingError
from ai_draw.grid.canvas import Canvas

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


class SceneError(DrawingError):
    """The scene file does not give a canvas."""


@contextmanager
def _importable_from(folder: Path) -> Generator[None]:
    """Let the scene import the modules next to it, as a script run from its folder would."""
    entry = str(folder)
    sys.path.insert(0, entry)
    try:
        yield
    finally:
        sys.path.remove(entry)


def load_scene(scene: Path) -> Canvas:
    """Run ``scene`` and return the canvas its ``draw()`` gives."""
    with _importable_from(scene.resolve().parent):
        namespace: dict[str, object] = runpy.run_path(str(scene))
        draw = namespace.get("draw")
        if not callable(draw):
            message = f"{scene}: no draw() function, expected def draw() -> Canvas"
            raise SceneError(message)
        canvas = draw()
    if not isinstance(canvas, Canvas):
        message = f"{scene}: draw() returned {type(canvas).__name__}, expected a Canvas"
        raise SceneError(message)
    return canvas

# SPDX-License-Identifier: GPL-3.0-only
"""The ``ai-draw`` command.

A scene is a Python file with a ``draw()`` that returns a ``Canvas``::

    ai-draw render scene.py --scale 10        # writes scene.png next to it
    ai-draw render scene.py -o out/big.png
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ai_draw.grid.canvas import Canvas
from ai_draw.io.png import write_png

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_SCENE_ERROR = 2


class SceneError(Exception):
    """The scene file does not give a canvas."""


def load_scene(scene: Path) -> Canvas:
    """Run ``scene`` and return the canvas its ``draw()`` gives."""
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-draw", description="Vector drawing to PNG.")
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render", help="draw a scene file to a PNG")
    _ = render.add_argument("scene", type=Path, help="Python file with draw() -> Canvas")
    _ = render.add_argument("-o", "--output", type=Path, help="PNG to write (default: scene.png)")
    _ = render.add_argument("--scale", type=int, default=1, help="enlarge each pixel N times")
    return parser


def _render(scene: Path, output: Path | None, scale: int) -> None:
    canvas = load_scene(scene).enlarged(scale)
    write_png(canvas, output or scene.with_suffix(".png"))


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of ``ai-draw``; returns the exit code."""
    arguments = _parser().parse_args(argv)
    scene = arguments.scene  # pyright: ignore[reportAny] - argparse.Namespace is untyped
    output = arguments.output  # pyright: ignore[reportAny] - argparse.Namespace is untyped
    scale = arguments.scale  # pyright: ignore[reportAny] - argparse.Namespace is untyped
    try:
        _render(scene, output, scale)  # pyright: ignore[reportAny] - typed by add_argument above
    except (SceneError, ValueError) as error:
        print(f"ai-draw: {error}", file=sys.stderr)  # noqa: T201 - CLI output for a human
        return EXIT_SCENE_ERROR
    return 0

# SPDX-License-Identifier: GPL-3.0-only
"""The ``ai-draw`` command.

A scene is a Python file with a ``draw()`` that returns a ``Canvas``::

    ai-draw render scene.py --scale 10        # writes scene.png next to it
    ai-draw render scene.py -o out/big.png
    ai-draw watch scene.py --scale 8           # redraws on every save, shown in imv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ai_draw.io.live import INTERVAL, LiveSession, open_imv, run
from ai_draw.io.png import write_png
from ai_draw.io.scene import SceneError, load_scene

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_SCENE_ERROR = 2


class _Arguments(argparse.Namespace):
    """The parsed command line, typed."""

    command: str = ""
    scene: Path = Path()
    output: Path | None = None
    scale: int = 1
    also: Sequence[Path] = ()
    no_viewer: bool = False
    once: bool = False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-draw", description="Vector drawing to PNG.")
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render", help="draw a scene file to a PNG")
    watch = commands.add_parser("watch", help="redraw a scene every time it is saved")
    for command in (render, watch):
        _ = command.add_argument("scene", type=Path, help="Python file with draw() -> Canvas")
        _ = command.add_argument("-o", "--output", type=Path, help="PNG (default: scene.png)")
        _ = command.add_argument("--scale", type=int, default=1, help="enlarge each pixel N times")
    _ = watch.add_argument("--also", type=Path, action="append", default=[], help="watch too")
    _ = watch.add_argument("--no-viewer", action="store_true", help="do not open imv")
    _ = watch.add_argument("--once", action="store_true", help="draw once and exit")
    return parser


def _say(message: str) -> None:
    print(f"ai-draw: {message}", file=sys.stderr)  # noqa: T201 - CLI output for a human


def _render(arguments: _Arguments) -> int:
    try:
        canvas = load_scene(arguments.scene).enlarged(arguments.scale)
    except (SceneError, ValueError) as error:
        _say(str(error))
        return EXIT_SCENE_ERROR
    write_png(canvas, arguments.output or arguments.scene.with_suffix(".png"))
    return 0


def _watch(arguments: _Arguments) -> int:
    output = arguments.output or arguments.scene.with_suffix(".png")
    session = LiveSession(arguments.scene, output, scale=arguments.scale, also=arguments.also)
    if arguments.once:
        result = session.poll()
        drew = result is not None and result.drew
        _say(result.message if result is not None else "nothing to draw")
        return 0 if drew else EXIT_SCENE_ERROR
    viewer = None if arguments.no_viewer else open_imv
    run(session, viewer=viewer, interval=INTERVAL, keep_going=lambda: True, log=_say)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of ``ai-draw``; returns the exit code."""
    arguments = _parser().parse_args(argv, namespace=_Arguments())
    return _watch(arguments) if arguments.command == "watch" else _render(arguments)

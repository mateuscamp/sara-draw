# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import pytest

from ai_draw.io.scene import load_scene

EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples").glob("*.py"))


def test_there_are_examples() -> None:
    assert EXAMPLES


@pytest.mark.parametrize("scene", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_example_draws_hard_pixels(scene: Path) -> None:
    canvas = load_scene(scene)
    # ADR-0001: the pixel output has alpha 0 or 255 only
    assert set(canvas.pixels[:, :, 3].tobytes()) <= {0, 255}

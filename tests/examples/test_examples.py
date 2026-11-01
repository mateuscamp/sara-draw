# SPDX-License-Identifier: GPL-3.0-only
import runpy
from pathlib import Path

import pytest

from ai_draw.grid.palette import Palette
from ai_draw.io.scene import load_scene
from ai_draw.lint import lint

ROOT = Path(__file__).resolve().parents[2] / "examples"
PIXEL = sorted((ROOT / "pixel").glob("*.py"))
SMOOTH = sorted((ROOT / "smooth").glob("*.py"))


def test_there_are_pixel_and_smooth_examples() -> None:
    assert len(PIXEL) >= 2
    assert len(SMOOTH) >= 1
    assert sorted(ROOT.glob("*.py")) == [], "examples live in examples/pixel or examples/smooth"


@pytest.mark.parametrize("scene", PIXEL, ids=[path.stem for path in PIXEL])
def test_pixel_example_keeps_to_its_closed_palette_and_hard_alpha(scene: Path) -> None:
    palette = runpy.run_path(str(scene)).get("PALETTE")
    assert isinstance(palette, Palette), "every pixel example declares PALETTE"
    canvas = load_scene(scene)
    assert palette.foreign(canvas) == []
    # ADR-0001: the pixel output has alpha 0 or 255 only
    assert set(canvas.pixels[:, :, 3].tobytes()) <= {0, 255}
    assert [f.count for f in lint(canvas) if f.check in {"half alpha", "loose pixels"}] == [0, 0]


@pytest.mark.parametrize("scene", SMOOTH, ids=[path.stem for path in SMOOTH])
def test_smooth_example_draws_antialiased_edges(scene: Path) -> None:
    canvas = load_scene(scene)
    shades = set(map(tuple, canvas.pixels.reshape(-1, 4).tolist()))
    assert len(shades) > 16, "a smooth example blends its edges into many shades"

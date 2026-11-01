# SPDX-License-Identifier: GPL-3.0-only
"""The README cannot lie: its picture, its table and its code come from the library as it is."""

import re
import runpy
from pathlib import Path

import pytest

from ai_draw.io.png import read_png
from ai_draw.io.scene import load_scene

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GALLERY = ROOT / "docs" / "gallery"
COMPARE_SCALE = 4


def test_the_comparison_picture_is_up_to_date() -> None:
    fresh = load_scene(GALLERY / "compare.py").enlarged(COMPARE_SCALE)
    committed = GALLERY / "compare.png"
    assert committed.exists(), "run: uv run ai-draw render docs/gallery/compare.py --scale 4"
    assert read_png(committed).same_pixels(fresh), "rerun the render command and commit"


def test_the_readme_table_is_what_the_bench_measures_today() -> None:
    markdown = runpy.run_path(str(GALLERY / "scores.py")).get("markdown")
    assert callable(markdown)
    table = markdown()
    assert isinstance(table, str)
    assert table in README.read_text(encoding="utf-8"), (
        "paste: uv run python docs/gallery/scores.py"
    )


def test_the_readme_example_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = README.read_text(encoding="utf-8")
    blocks: list[str] = re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)
    assert blocks, "the README shows a Python example"
    monkeypatch.chdir(tmp_path)
    for block in blocks:
        exec(compile(block, "README.md", "exec"), {})  # noqa: S102 - the README's own example
    assert list(tmp_path.glob("*.png")), "the example writes a picture"

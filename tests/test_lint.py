# SPDX-License-Identifier: GPL-3.0-only
from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.rows import from_rows
from ai_draw.lint import Finding, lint

INK: Color = (30, 20, 40, 255)
SKIN: Color = (230, 180, 140, 255)
BLUSH: Color = (236, 176, 142, 255)


def counts(findings: list[Finding]) -> dict[str, int]:
    return {finding.check: finding.count for finding in findings}


def test_clean_sprite_has_nothing_to_report() -> None:
    sprite = from_rows([".kk.", "kssk", ".kk."], {"k": INK, "s": SKIN})
    assert counts(lint(sprite)) == {"half alpha": 0, "loose pixels": 0, "near colors": 0}


def test_lint_counts_half_alpha_loose_pixels_and_near_colors() -> None:
    sprite = from_rows(["ss..", "sb..", "...s"], {"s": SKIN, "b": BLUSH})
    sprite.paint(3, 0, (230, 180, 140, 120))
    found = counts(lint(sprite, near=10))
    assert found == {"half alpha": 1, "loose pixels": 1, "near colors": 1}


def test_near_colors_name_the_pair() -> None:
    sprite = from_rows(["sb"], {"s": SKIN, "b": BLUSH})
    details = [finding.detail for finding in lint(sprite) if finding.check == "near colors"]
    assert details == ["#e6b48c #ecb08e"]


def test_a_line_color_adds_the_line_checks() -> None:
    corner = from_rows(["k..", "kk.", ".kk"], {"k": INK})
    found = counts(lint(corner, line=INK, width=1))
    assert found.get("L corners") == 3
    assert found.get("extra pieces") == 0
    assert set(found) >= {"wobble", "thickness"}


def test_an_empty_canvas_is_clean() -> None:
    assert [finding.count for finding in lint(Canvas(3, 3))] == [0, 0, 0]

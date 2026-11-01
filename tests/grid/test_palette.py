# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.grid.canvas import CLEAR, Canvas, Color
from ai_draw.grid.palette import (
    ColorUse,
    Family,
    Palette,
    Swatch,
    collect,
    distance,
    merge,
    near_pairs,
    parse_hex,
    to_hex,
)
from ai_draw.grid.rows import from_rows

RED: Color = (200, 40, 40, 255)
RED_SHADE: Color = (140, 20, 30, 255)
ALMOST_RED: Color = (205, 44, 38, 255)
GRASS: Color = (90, 170, 70, 255)
LEAF: Color = (96, 166, 74, 255)
WOOD = Family.of("wood", ["8a5a34 base", "5e3a22 shadow"])
CLOTH = Family.of("cloth", ["c82828 base", "8c141e shadow"])
PALETTE = Palette((WOOD, CLOTH))


def test_hex_reads_and_writes_colors() -> None:
    assert parse_hex("#8a5a34") == (138, 90, 52, 255)
    assert parse_hex("8A5A3480") == (138, 90, 52, 128)
    assert to_hex((138, 90, 52, 255)) == "#8a5a34"
    assert to_hex((138, 90, 52, 128)) == "#8a5a3480"


@pytest.mark.parametrize("text", ["#8a5a3", "zz5a34", ""])
def test_bad_hex_is_an_error(text: str) -> None:
    with pytest.raises(ValueError, match="hex"):
        _ = parse_hex(text)


def test_family_reads_hex_and_role() -> None:
    assert WOOD.swatches == (
        Swatch((138, 90, 52, 255), "base"),
        Swatch((94, 58, 34, 255), "shadow"),
    )


def test_family_entry_needs_a_color_and_a_role() -> None:
    with pytest.raises(ValueError, match="'8a5a34'"):
        _ = Family.of("wood", ["8a5a34"])


def test_palette_lists_every_color_and_knows_its_family() -> None:
    assert PALETTE.colors == ((138, 90, 52, 255), (94, 58, 34, 255), RED, RED_SHADE)
    assert PALETTE.family_of(RED_SHADE) == CLOTH
    assert PALETTE.family_of(GRASS) is None


def test_a_color_cannot_sit_in_two_families() -> None:
    with pytest.raises(ValueError, match="#c82828"):
        _ = Palette((CLOTH, Family.of("flag", ["c82828 stripe"])))


def test_foreign_lists_the_opaque_colors_outside_the_palette_most_used_first() -> None:
    canvas = from_rows(["rggl.", "r...."], {"r": RED, "g": GRASS, "l": LEAF})
    assert PALETTE.foreign(canvas) == [GRASS, LEAF]


def test_quantize_takes_each_pixel_to_the_nearest_palette_color() -> None:
    canvas = from_rows(["ab."], {"a": ALMOST_RED, "b": (100, 70, 40, 255)})
    quantized = PALETTE.quantize(canvas)
    assert quantized.color_at(0, 0) == RED
    assert quantized.color_at(1, 0) == (94, 58, 34, 255)
    assert quantized.color_at(2, 0) == CLEAR
    assert PALETTE.foreign(quantized) == []


def test_quantize_keeps_alpha_hard() -> None:
    canvas = Canvas(2, 1)
    canvas.paint(0, 0, (200, 40, 40, 200))
    canvas.paint(1, 0, (200, 40, 40, 60))
    quantized = PALETTE.quantize(canvas)
    assert quantized.color_at(0, 0) == RED
    assert quantized.color_at(1, 0) == CLEAR


def test_collect_counts_pixels_and_pieces_most_used_first() -> None:
    hat = from_rows(["rrg"], {"r": RED, "g": GRASS})
    boot = from_rows(["g.", "gg"], {"g": GRASS})
    assert collect({"hat": hat, "boot": boot}) == [
        ColorUse(GRASS, 4, ("boot", "hat")),
        ColorUse(RED, 2, ("hat",)),
    ]


def test_distance_is_the_largest_channel_difference_without_alpha() -> None:
    assert distance(RED, (205, 44, 38, 0)) == 5


def test_near_pairs_keep_the_list_order_and_the_tolerance_inclusive() -> None:
    assert near_pairs([RED, GRASS, ALMOST_RED, LEAF], 6) == [(RED, ALMOST_RED), (GRASS, LEAF)]


TOWN = Palette(
    (
        Family.of("cloth", ["c82828 base", "cd2c26 base too"]),
        Family.of("grass", ["5aaa46 base", "60a64a lit"]),
    )
)


def test_merge_folds_near_colors_of_a_family_into_the_most_used() -> None:
    used = [ColorUse(RED, 10, ("hat",)), ColorUse(ALMOST_RED, 3, ("flag",))]
    assert merge(TOWN, used, 6) == {ALMOST_RED: RED}


def test_merge_keeps_two_tones_that_one_piece_uses_together() -> None:
    used = [ColorUse(GRASS, 10, ("bush",)), ColorUse(LEAF, 3, ("bush",))]
    assert merge(TOWN, used, 6) == {}


def test_merge_never_crosses_families() -> None:
    cross = Palette((Family.of("cloth", ["c82828 base"]), Family.of("ember", ["cd2c26 glow"])))
    used = [ColorUse(RED, 10, ("hat",)), ColorUse(ALMOST_RED, 3, ("fire",))]
    assert merge(cross, used, 6) == {}


def test_merge_refuses_a_color_without_a_family() -> None:
    with pytest.raises(ValueError, match="#5aaa46"):
        _ = merge(PALETTE, [ColorUse(GRASS, 1, ("bush",))], 6)

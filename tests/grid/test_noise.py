# SPDX-License-Identifier: GPL-3.0-only
import pytest

from ai_draw.grid.canvas import Canvas, Color
from ai_draw.grid.noise import speckle
from ai_draw.grid.rows import to_rows

RED: Color = (200, 30, 30, 255)
BLUE: Color = (30, 30, 200, 255)
LEGEND = {"r": RED, "b": BLUE}


def speckled(seed: int, chance: float = 0.5) -> Canvas:
    canvas = Canvas(8, 8)
    speckle(canvas, 1, 1, 6, 6, colors=[RED, BLUE], chance=chance, seed=seed)
    return canvas


def test_the_seed_decides_the_pixels() -> None:
    assert speckled(7).same_pixels(speckled(7))
    assert not speckled(7).same_pixels(speckled(8))


def test_chance_goes_from_nothing_to_every_pixel_of_the_area() -> None:
    assert to_rows(speckled(3, chance=0.0), LEGEND) == ["........"] * 8
    rows = to_rows(speckled(3, chance=1.0), LEGEND)
    assert rows[0] == rows[7] == "........"
    assert all(row[0] == row[7] == "." and "." not in row[1:7] for row in rows[1:7])


def test_speckle_uses_every_color_it_is_given_and_no_other() -> None:
    painted = "".join(row[1:7] for row in to_rows(speckled(3, chance=1.0), LEGEND)[1:7])
    assert set(painted) == {"r", "b"}


@pytest.mark.parametrize("chance", [-0.1, 1.5])
def test_chance_must_be_a_probability(chance: float) -> None:
    with pytest.raises(ValueError, match="chance"):
        _ = speckled(1, chance=chance)


def test_speckle_needs_colors() -> None:
    with pytest.raises(ValueError, match="colors"):
        speckle(Canvas(2, 2), 0, 0, 2, 2, colors=[], chance=0.5, seed=1)

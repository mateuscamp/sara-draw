# SPDX-License-Identifier: GPL-3.0-only
# numpy 2.5's stubs type comparisons, reductions and np.pad on NDArray as Any or partially
# unknown, which the strict checker rejects. The array arithmetic lives here, behind small
# functions with exact return types, so every other module stays fully checked.
# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false
"""Pixel masks: the only module of the package that does array arithmetic.

>>> import numpy as np
>>> pixels = np.zeros((1, 2, 4), dtype=np.uint8)
>>> pixels[0, 1] = (9, 9, 9, 255)
>>> opaque_mask(pixels).tolist()
[[False, True]]
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


def opaque_mask(pixels: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """True where the alpha is not zero."""
    return pixels[:, :, 3] != 0


def edge_mask(opaque: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """True on the opaque cells that touch a transparent cell or the border by a side."""
    # Padding with False makes the border count as transparency.
    padded = np.pad(opaque, 1, constant_values=False)
    inner = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    return opaque & ~inner


def halo_mask(opaque: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Ring of cells around the opaque ones, on a grid one cell larger on every side.

    True on the transparent cells with an opaque cell among their eight neighbors.
    """
    grown = np.pad(opaque, 1, constant_values=False)
    reach = np.pad(grown, 1, constant_values=False)
    rows, columns = grown.shape
    near = np.zeros_like(grown)
    for dy, dx in itertools.product(range(3), range(3)):
        near |= reach[dy : dy + rows, dx : dx + columns]
    return near & ~grown


def color_mask(pixels: NDArray[np.uint8], color: tuple[int, int, int, int]) -> NDArray[np.bool_]:
    """True where the pixel is exactly ``color``, alpha included."""
    return (pixels == color).all(axis=2)


def count_differing(first: NDArray[np.uint8], second: NDArray[np.uint8]) -> int:
    """How many pixels differ in any channel; the arrays must have the same shape."""
    return int(np.count_nonzero((first != second).any(axis=2)))


def color_counts(pixels: NDArray[np.uint8]) -> dict[tuple[int, int, int, int], int]:
    """How many pixels have each color, alpha included."""
    colors, counts = np.unique(pixels.reshape(-1, 4), axis=0, return_counts=True)
    return {
        (int(r), int(g), int(b), int(a)): int(count)
        for (r, g, b, a), count in zip(colors.tolist(), counts.tolist(), strict=True)
    }


def blend(
    pixels: NDArray[np.uint8], coverage: list[list[float]], color: tuple[int, int, int, int]
) -> None:
    """Paint ``color`` over ``pixels`` in place, each pixel weighted by its coverage (0 to 1).

    Source-over on straight (not premultiplied) alpha; untouched where the coverage is 0.
    """
    weight = np.asarray(coverage, dtype=np.float64) * (color[3] / 255)
    ground = pixels.astype(np.float64) / 255
    ground_alpha = ground[:, :, 3]
    alpha = weight + ground_alpha * (1 - weight)
    paint = np.asarray(color[:3], dtype=np.float64) / 255
    mixed = (
        paint * weight[:, :, None] + ground[:, :, :3] * (ground_alpha * (1 - weight))[:, :, None]
    )
    rgb = mixed / np.where(alpha > 0, alpha, 1)[:, :, None]
    result = np.floor(np.concatenate([rgb, alpha[:, :, None]], axis=2) * 255 + 0.5)
    touched = weight > 0
    pixels[touched] = result[touched].astype(np.uint8)

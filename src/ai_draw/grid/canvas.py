# SPDX-License-Identifier: GPL-3.0-only
"""RGBA pixel grid with the origin at the top-left corner.

Every write OVERWRITES the pixel, transparent ones included: that is how a hollow frame
opens its middle. Blending colors is not this grid's job; the pixel output has no
antialiasing on purpose (ADR-0001).

    >>> canvas = Canvas(70, 98)
    >>> canvas.rect(0, 0, 70, 98, (32, 26, 46, 255))
    >>> canvas.enlarged(4).width
    280
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

Color = tuple[int, int, int, int]
"""Four integers from 0 to 255: r, g, b, a (not premultiplied)."""

CLEAR: Color = (0, 0, 0, 0)

_CHANNELS = 4
_MAX_CHANNEL = 255


def check_color(color: Color) -> Color:
    """Return ``color`` if it is a valid color; raise ValueError saying why otherwise."""
    channels = cast("tuple[object, ...]", color)
    if len(channels) != _CHANNELS:
        message = f"color={color!r}, expected (r, g, b, a)"
        raise ValueError(message)
    for channel in channels:
        if not isinstance(channel, int) or not 0 <= channel <= _MAX_CHANNEL:
            message = f"color={color!r}: channel {channel!r}, expected an integer from 0 to 255"
            raise ValueError(message)
    return color


class Canvas:
    """A ``height x width x 4`` array of ``uint8``, rows first, wrapped with drawing calls."""

    def __init__(self, width: int, height: int) -> None:
        """A transparent canvas of ``width`` by ``height`` pixels."""
        if width < 1 or height < 1:
            message = f"size={width}x{height}, expected positive integers"
            raise ValueError(message)
        self._width: int = width
        self._height: int = height
        self.pixels: NDArray[np.uint8] = np.zeros((height, width, _CHANNELS), dtype=np.uint8)

    @staticmethod
    def from_pixels(pixels: NDArray[np.uint8]) -> Canvas:
        """A canvas holding a copy of ``pixels`` (rows, columns, RGBA)."""
        # numpy types a shape as tuple[Any, ...]; its sides are ints.
        shape = cast("tuple[int, ...]", pixels.shape)
        if len(shape) != 3 or shape[2] != _CHANNELS:  # noqa: PLR2004 - rows, columns, channels
            message = f"pixels with shape {shape}, expected (height, width, 4)"
            raise ValueError(message)
        canvas = Canvas(shape[1], shape[0])
        canvas.pixels[...] = pixels
        return canvas

    @property
    def width(self) -> int:
        """Columns."""
        return self._width

    @property
    def height(self) -> int:
        """Rows."""
        return self._height

    def _inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def color_at(self, x: int, y: int) -> Color | None:
        """The color of pixel (x, y), or None outside the canvas."""
        if not self._inside(x, y):
            return None
        # A slice keeps numpy's types where a plain index would give Any.
        r, g, b, a = self.pixels[y : y + 1, x : x + 1].tobytes()
        return r, g, b, a

    def paint(self, x: int, y: int, color: Color) -> None:
        """Set one pixel; outside the canvas it is ignored."""
        _ = check_color(color)
        if self._inside(x, y):
            self.pixels[y, x] = color

    def span(self, x: int, y: int, length: int, color: Color) -> None:
        """Horizontal run of ``length`` pixels from (x, y), clipped to the canvas."""
        _ = check_color(color)
        if not 0 <= y < self.height:
            return
        start, end = max(0, x), min(self.width, x + length)
        if start < end:
            self.pixels[y, start:end] = color

    def rect(self, x: int, y: int, width: int, height: int, color: Color) -> None:
        """Rectangle of ``width`` by ``height`` with its top-left corner at (x, y)."""
        for row in range(y, y + height):
            self.span(x, row, width, color)

    def enlarged(self, factor: int) -> Canvas:
        """Copy with every pixel repeated ``factor`` times on each axis (nearest neighbor)."""
        if factor < 1:
            message = f"factor={factor!r}, expected an integer >= 1"
            raise ValueError(message)
        return Canvas.from_pixels(self.pixels.repeat(factor, axis=0).repeat(factor, axis=1))

    def copy(self) -> Canvas:
        """An independent canvas with the same pixels."""
        return Canvas.from_pixels(self.pixels)

    def same_pixels(self, other: Canvas) -> bool:
        """Same size and exactly the same pixels."""
        same_size = (self.width, self.height) == (other.width, other.height)
        return same_size and self.pixels.tobytes() == other.pixels.tobytes()

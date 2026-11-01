# SPDX-License-Identifier: GPL-3.0-only
"""The errors ai-draw raises: one family, every member a ``ValueError``.

Each says what it received and what it expected. Catch ``DrawingError`` for any of them, a
member for one kind, or ``ValueError`` as before the family existed. This layer imports
nothing, so every other layer may import it (ADR-0005).

    >>> from ai_draw.grid.canvas import Canvas
    >>> try:
    ...     Canvas(0, 4)
    ... except CanvasError as error:
    ...     print(error)
    size=0x4, expected positive integers
"""


class DrawingError(ValueError):
    """Any error of ai-draw: an input it cannot draw with."""


class GeometryError(DrawingError):
    """A path that cannot be built: a line before move_to, a polygon with fewer than 3 points."""


class ColorError(DrawingError):
    """A color, hex code or palette that is not valid."""


class CanvasError(DrawingError):
    """A canvas size, pixel array or character map of the wrong shape."""


class SettingError(DrawingError):
    """A drawing setting out of range: a fill rule, a width, a chance, a factor."""

# SPDX-License-Identifier: GPL-3.0-only
"""Defect detectors: the mistakes a pixel artist avoids, each counted as a number.

They measure and never change a pixel. Every detector is 0 on clean pixel art, so the bench
(``tests/bench``) can hold the score of the rasterizer and only let it go down.

They read a set of cells, ``(x, y)`` pairs, which ``cells_of`` takes from a canvas:

    >>> from ai_draw.grid.rows import from_rows
    >>> line = cells_of(from_rows(["#..", "##.", ".##"], {"#": (0, 0, 0, 255)}))
    >>> l_corners(line), components(line)
    (3, 1)
"""

from __future__ import annotations

import itertools
from collections import Counter
from typing import TYPE_CHECKING

from ai_draw.errors import SettingError

if TYPE_CHECKING:
    from ai_draw.grid.canvas import Canvas, Color

Cell = tuple[int, int]
Cells = frozenset[Cell]

_EIGHT = tuple((dx, dy) for dx, dy in itertools.product((-1, 0, 1), repeat=2) if dx or dy)


def cells_of(canvas: Canvas, color: Color | None = None) -> Cells:
    """The cells of ``color``, or of every opaque pixel when no color is given."""
    found: set[Cell] = set()
    for y, x in itertools.product(range(canvas.height), range(canvas.width)):
        pixel = canvas.color_at(x, y)
        if pixel is not None and (pixel == color if color is not None else pixel[3] != 0):
            found.add((x, y))
    return frozenset(found)


def _neighbors(cell: Cell) -> list[Cell]:
    x, y = cell
    return [(x + dx, y + dy) for dx, dy in _EIGHT]


def orphans(cells: Cells) -> int:
    """Count the pixels with none of their eight neighbors: the loose pixel."""
    return sum(1 for cell in cells if not any(near in cells for near in _neighbors(cell)))


def component_labels(cells: Cells) -> dict[Cell, int]:
    """Number each piece, joined by any of the eight neighbors, from the top-left one."""
    labels: dict[Cell, int] = {}
    # Counted as they start: recounting the labels for each piece was quadratic (audit B4).
    pieces = itertools.count()
    for start in sorted(cells, key=lambda cell: (cell[1], cell[0])):
        if start in labels:
            continue
        piece = next(pieces)
        labels[start] = piece
        frontier = [start]
        while frontier:
            near = [cell for cell in _neighbors(frontier.pop()) if cell in cells]
            fresh = [cell for cell in near if cell not in labels]
            labels.update(dict.fromkeys(fresh, piece))
            frontier.extend(fresh)
    return labels


def components(cells: Cells) -> int:
    """Count the pieces, joined by any of the eight neighbors: a broken tip adds one."""
    return len(set(component_labels(cells).values()))


def _is_l_corner(cell: Cell, cells: Cells) -> bool:
    x, y = cell
    return any(
        (x + dx, y) in cells and (x, y + dy) in cells and (x + dx, y + dy) not in cells
        for dx, dy in itertools.product((-1, 1), repeat=2)
    )


def l_corners(cells: Cells) -> int:
    """Count the L corners: the cells that make a one-pixel line look doubled.

    An L corner has a side neighbor and an up-or-down neighbor but not the diagonal between
    them. Meant for one-pixel lines; on a fill it also counts concave corners.
    """
    return sum(1 for cell in cells if _is_l_corner(cell, cells))


def uneven_steps(cells: Cells) -> int:
    """Count the inner steps of a straight one-pixel line that break its rhythm.

    A line wider than tall is read row by row, a steeper one column by column; each row (or
    column) is one step. The first and last steps may be cut short; every other step should
    have the most common length (1:1, 1:2, 1:3...). Meant for straight lines.
    """
    if not cells:
        return 0
    xs, ys = [x for x, _ in cells], [y for _, y in cells]
    wide = max(xs) - min(xs) >= max(ys) - min(ys)
    per_line = Counter(ys if wide else xs)
    inner = [per_line[line] for line in sorted(per_line)][1:-1]
    if not inner:
        return 0
    lengths = Counter(inner)
    rhythm = min(lengths, key=lambda length: (-lengths[length], length))
    return sum(1 for length in inner if length != rhythm)


def _covered_by_blocks(cells: Cells, side: int) -> set[Cell]:
    covered: set[Cell] = set()
    for x, y in cells:
        block = [(x + dx, y + dy) for dx, dy in itertools.product(range(side), repeat=2)]
        if all(cell in cells for cell in block):
            covered.update(block)
    return covered


Run = tuple[int, int]
"""A maximal run of cells in one row or column: first and last position, inclusive."""


def _runs(positions: list[int]) -> list[Run]:
    runs: list[Run] = []
    for position in sorted(positions):
        if runs and position == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], position)
        else:
            runs.append((position, position))
    return runs


def _across_runs(cells: Cells, *, by_rows: bool, longest: int) -> dict[int, list[Run]]:
    """Per row (or column), the runs no longer than ``longest``: the ones across a stroke."""
    per_line: dict[int, list[int]] = {}
    for x, y in cells:
        line, position = (y, x) if by_rows else (x, y)
        per_line.setdefault(line, []).append(position)
    return {
        line: [run for run in _runs(positions) if run[1] - run[0] < longest]
        for line, positions in per_line.items()
    }


def _touch(first: Run, second: Run) -> bool:
    return second[0] <= first[1] + 1 and first[0] <= second[1] + 1


def _parent(run: Run, previous: list[Run], current: list[Run]) -> Run | None:
    """The run of the line before that ``run`` continues: one each way, or the chain splits."""
    parents = [candidate for candidate in previous if _touch(candidate, run)]
    if len(parents) != 1:
        return None
    children = [candidate for candidate in current if _touch(parents[0], candidate)]
    return parents[0] if len(children) == 1 else None


def _chains(across: dict[int, list[Run]]) -> list[list[int]]:
    """The lengths of across runs, followed from line to line while they continue one another."""
    chains: list[list[int]] = []
    tails: dict[Run, list[int]] = {}
    for line in sorted(across):
        tails = _grow_chains(across[line], across.get(line - 1, []), tails, chains)
    return chains


def _grow_chains(
    current: list[Run], previous: list[Run], tails: dict[Run, list[int]], chains: list[list[int]]
) -> dict[Run, list[int]]:
    """Add one line's runs to the chains they continue, or start new ones; return the tails."""
    next_tails: dict[Run, list[int]] = {}
    for run in current:
        parent = _parent(run, previous, current)
        chain = tails.get(parent) if parent is not None else None
        if chain is None:
            chain = list[int]()
            chains.append(chain)
        chain.append(run[1] - run[0] + 1)
        next_tails[run] = chain
    return next_tails


def _bumps(lengths: list[int]) -> int:
    """Count the a, b, a triples: a width that changes and comes right back."""
    triples = zip(lengths, lengths[1:], lengths[2:], strict=False)
    return sum(1 for before, middle, after in triples if before == after != middle)


def _run_lengths(cells: Cells, *, by_rows: bool) -> dict[Cell, int]:
    """For each cell, the length of its run in its row (or column)."""
    lengths: dict[Cell, int] = {}
    for line, runs in _across_runs(cells, by_rows=by_rows, longest=len(cells) + 1).items():
        for first, last in runs:
            for position in range(first, last + 1):
                cell = (position, line) if by_rows else (line, position)
                lengths[cell] = last - first + 1
    return lengths


def thickness_defects(cells: Cells, width: int) -> int:
    """Count where a stroke of ``width`` thins or swells.

    Too thin: a cell whose runs across the stroke (its row and column runs no longer than
    ``width + 1``) are all shorter than ``width``. A steep stroke staggered row by row keeps
    its width; a flat stroke with a one-pixel column does not. Too thick: a cell inside a
    block ``width + 1`` pixels on each side, the blob at a joint.
    """
    if width < 1:
        message = f"width={width!r}, expected an integer >= 1"
        raise SettingError(message)
    rows, columns = _run_lengths(cells, by_rows=True), _run_lengths(cells, by_rows=False)
    thin = 0
    for cell in cells:
        across = [n for n in (rows[cell], columns[cell]) if n <= width + 1]
        thin += bool(across) and max(across) < width
    return thin + len(_covered_by_blocks(cells, width + 1))


def wobble(cells: Cells, width: int) -> int:
    """Count where a stroke's width swings back and forth: a, b, a along the stroke.

    The width is read across the stroke, on the row and column runs no longer than
    ``width + 1``, followed from line to line. A width that changes and stays, as a curve
    turns, does not count; one that flips 3, 2, 3 is the stroke that swells and thins.
    """
    if width < 1:
        message = f"width={width!r}, expected an integer >= 1"
        raise SettingError(message)
    total = 0
    for by_rows in (True, False):
        for chain in _chains(_across_runs(cells, by_rows=by_rows, longest=width + 1)):
            total += _bumps(chain)
    return total


def _mirror_offset(axis: float, name: str) -> int:
    """Pixel ``p`` mirrors to ``offset - p`` across ``axis``.

    Its center p + 0.5 lands on 2 * axis - p - 0.5.
    """
    doubled = axis * 2
    if doubled != int(doubled):
        message = f"{name}={axis!r}, expected a whole or half number (a pixel edge or center)"
        raise SettingError(message)
    return int(doubled) - 1


def asymmetric_cells(
    cells: Cells, *, mirror_x: float | None = None, mirror_y: float | None = None
) -> int:
    """Count the cells whose mirror image is missing.

    The mirrors are a vertical line ``x = mirror_x`` and a horizontal line ``y = mirror_y``;
    each axis adds its own count.
    """
    count = 0
    if mirror_x is not None:
        offset = _mirror_offset(mirror_x, "mirror_x")
        count += sum(1 for x, y in cells if (offset - x, y) not in cells)
    if mirror_y is not None:
        offset = _mirror_offset(mirror_y, "mirror_y")
        count += sum(1 for x, y in cells if (x, offset - y) not in cells)
    return count

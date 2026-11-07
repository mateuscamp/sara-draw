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

# A step this long or longer may be abrupt; 2 against 1 is how any curve leaves a straight run.
_ABRUPT_FROM = 3
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


def _chains(across: dict[int, list[Run]]) -> list[list[Run]]:
    """The across runs, followed from line to line while they continue one another."""
    chains: list[list[Run]] = []
    tails: dict[Run, list[Run]] = {}
    for line in sorted(across):
        tails = _grow_chains(across[line], across.get(line - 1, []), tails, chains)
    return chains


def _grow_chains(
    current: list[Run], previous: list[Run], tails: dict[Run, list[Run]], chains: list[list[Run]]
) -> dict[Run, list[Run]]:
    """Add one line's runs to the chains they continue, or start new ones; return the tails."""
    next_tails: dict[Run, list[Run]] = {}
    for run in current:
        parent = _parent(run, previous, current)
        chain = tails.get(parent) if parent is not None else None
        if chain is None:
            chain = list[Run]()
            chains.append(chain)
        chain.append(run)
        next_tails[run] = chain
    return next_tails


def _turns_back(before: Run, middle: Run, after: Run) -> bool:
    """The line comes into ``middle`` and leaves it on the same side."""
    past_end = before[0] > middle[1] and after[0] > middle[1]
    past_start = before[1] < middle[0] and after[1] < middle[0]
    return past_end or past_start


def _bumps(chain: list[Run]) -> int:
    """Count the a, b, a triples: a width that changes and comes right back.

    A turn with no other beside it is the tip of a curve, not a swing (02/11): the midpoint
    ellipse and Zingl's draw a one-pixel tip between steps of 2, which read 2, 1, 2 through it.
    A turn next to another is a sawtooth, and counts (audit, 04/11).
    """
    middles = range(1, len(chain) - 1)
    turns = {i for i in middles if _turns_back(chain[i - 1], chain[i], chain[i + 1])}
    lengths = [last - first + 1 for first, last in chain]
    swings = [i for i in middles if lengths[i - 1] == lengths[i + 1] != lengths[i]]
    return sum(1 for i in swings if i not in turns or {i - 1, i + 1} & turns)


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


def _lines_of_runs(cells: Cells, *, by_rows: bool) -> dict[int, list[Run]]:
    per_line: dict[int, list[int]] = {}
    for x, y in cells:
        line, position = (y, x) if by_rows else (x, y)
        per_line.setdefault(line, []).append(position)
    return {line: _runs(positions) for line, positions in per_line.items()}


def _continues(first: Run, second: Run) -> bool:
    """``second``, on the next line, starts where ``first`` ends, corner to corner: a curve."""
    return second[0] == first[1] + 1 or second[1] == first[0] - 1


def _reach(run: Run, line: int, runs: dict[int, list[Run]]) -> float:
    """The length of a step; half of it on top of a round shape, shared by both sides."""
    near = {
        side: [other for other in runs.get(line + side, []) if _continues(run, other)]
        for side in (-1, 1)
    }
    length = run[1] - run[0] + 1
    shared = any(len(near[side]) > 1 and not near[-side] for side in (-1, 1))
    return length / 2 if shared else length


def _abrupt_on(cells: Cells, *, by_rows: bool) -> int:
    runs = _lines_of_runs(cells, by_rows=by_rows)
    count = 0
    for line, here in runs.items():
        for run, below in itertools.product(here, runs.get(line + 1, [])):
            if not _continues(run, below):
                continue
            longer, shorter = sorted((_reach(run, line, runs), _reach(below, line + 1, runs)))[::-1]
            count += longer > 2 * shorter and longer >= _ABRUPT_FROM
    return count


def abrupt_steps(cells: Cells) -> int:
    """Count where a curve's step is more than twice the next: the octagon look.

    A step is a run along a row (or a column); the next one starts corner to corner from it.
    The top of a round shape, shared by its two sides, counts half its length. A corner, where
    the next run starts right under the end of the step, and a straight line, whose steps
    differ by one at most, never count. Meant for round shapes: a long straight side that
    meets a small rounded corner counts too.

    >>> from ai_draw.grid.rows import from_rows
    >>> flat_then_steep = from_rows(["#########...", ".........##."], {"#": (0, 0, 0, 255)})
    >>> abrupt_steps(cells_of(flat_then_steep))
    1
    """
    return _abrupt_on(cells, by_rows=True) + _abrupt_on(cells, by_rows=False)

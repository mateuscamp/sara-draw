# SPDX-License-Identifier: GPL-3.0-only
"""Even out the steps of a one-pixel line: a curve's steps change length in one direction.

A line is read as runs (straight stretches of cells) separated by diagonal steps. Along a
quarter circle the runs go from long and flat to long and steep without turning back; a run
out of that order is the jaggy a pixel artist fixes by hand. Swapping two neighboring runs
between equal diagonals keeps both ends of the stretch in place and the line connected. A
block of runs of three lengths or more is a curve and is sorted at once; a straight line has
two lengths at most, and their rhythm stays.

    >>> jagged = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (5, 2), (6, 2), (7, 3)]
    >>> even_out_steps(jagged, closed=False)[5]
    (5, 1)
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

Cell = tuple[int, int]
Step = tuple[int, int]

_NO_CELLS: frozenset[Cell] = frozenset()
# The shortest run that may be over twice its neighbor; 2 against 1 is how a curve leaves a row.
_ABRUPT_FROM = 3


def _steps(cells: list[Cell], *, closed: bool) -> list[Step]:
    ends = [*cells[1:], cells[0]] if closed else cells[1:]
    return [(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(cells, ends, strict=False)]


def _is_diagonal(step: Step) -> bool:
    return step[0] != 0 and step[1] != 0


def _split(steps: list[Step]) -> tuple[list[list[Step]], list[Step]]:
    """Runs of side steps, and the diagonal steps between them: one more run than diagonals."""
    runs: list[list[Step]] = [[]]
    diagonals: list[Step] = []
    for step in steps:
        if _is_diagonal(step):
            diagonals.append(step)
            runs.append([])
        else:
            runs[-1].append(step)
    return runs, diagonals


def _slope(run: list[Step]) -> float | None:
    """Rise over run of a stretch; None for a kept corner, which mixes directions."""
    if not run:
        return 1.0
    if any(step != run[0] for step in run):
        return None
    length = len(run) + 1
    return 1 / length if run[0][1] == 0 else float(length)


class _Stretch:
    """The runs of one line with the diagonals between them; open or closed."""

    def __init__(self, runs: list[list[Step]], diagonals: list[Step], *, closed: bool) -> None:
        self.runs: list[list[Step]] = runs
        self.diagonals: list[Step] = diagonals
        self.closed: bool = closed

    def diagonal_before(self, index: int) -> Step | None:
        if index == 0:
            return self.diagonals[-1] if self.closed else None
        return self.diagonals[index - 1]

    def fits(self, run: list[Step], diagonal: Step) -> bool:
        return all(step in {(diagonal[0], 0), (0, diagonal[1])} for step in run)

    def swappable(self, first: int, second: int) -> bool:
        """Two neighbors that lie between three equal diagonals, both plain runs."""
        before, between = self.diagonal_before(first), self.diagonals[first]
        after = self.diagonals[second] if second < len(self.diagonals) else None
        if before is None or after is None or not before == between == after:
            return False
        return all(
            _slope(self.runs[i]) is not None and self.fits(self.runs[i], between)
            for i in (first, second)
        )

    def neighbors(self, index: int) -> tuple[int, int] | None:
        count = len(self.runs)
        if self.closed:
            return (index - 1) % count, (index + 1) % count
        return (index - 1, index + 1) if 0 < index < count - 1 else None


def _proposal(stretch: _Stretch, index: int) -> tuple[int, int] | None:
    """The swap that puts run ``index`` back in the order of its neighbors, if it is out."""
    around = stretch.neighbors(index)
    if around is None:
        return None
    slopes = [_slope(stretch.runs[i]) for i in (around[0], index, around[1])]
    if None in slopes:
        return None
    a, b, c = (slope or 0.0 for slope in slopes)
    if a == c or min(a, c) <= b <= max(a, c):
        return None
    target = around[1] if (b > c) == (c > a) else around[0]
    pair = (min(index, target), max(index, target))
    if stretch.closed and {index, target} == {0, len(stretch.runs) - 1}:
        pair = (len(stretch.runs) - 1, 0)
    return pair if stretch.swappable(*pair) else None


def _out_of_order(stretch: _Stretch) -> int:
    """How many runs sit outside the range of their two neighbors."""
    count = 0
    for index in range(len(stretch.runs)):
        around = stretch.neighbors(index)
        if around is None:
            continue
        slopes = [_slope(stretch.runs[i]) for i in (around[0], index, around[1])]
        if None in slopes:
            continue
        a, b, c = (slope or 0.0 for slope in slopes)
        count += a != c and not min(a, c) <= b <= max(a, c)
    return count


def _swap(stretch: _Stretch, pairs: list[tuple[int, int]]) -> None:
    for first, second in pairs:
        stretch.runs[first], stretch.runs[second] = stretch.runs[second], stretch.runs[first]


def _settle(stretch: _Stretch) -> None:
    """Swap runs while it puts more of them in the order of their neighbors.

    Each pass decides all its swaps before making any, and drops the swaps that share a run,
    so the result does not depend on which end the line was drawn from. A pass that does not
    lower the count of runs out of order is undone and ends the settling: some lines swap two
    runs back and forth forever, and the count can only go down so many times (audit G1).
    """
    disorder = _out_of_order(stretch)
    while disorder:
        proposals = {pair for i in range(len(stretch.runs)) if (pair := _proposal(stretch, i))}
        used = [i for pair in proposals for i in pair]
        swaps = [pair for pair in proposals if used.count(pair[0]) == used.count(pair[1]) == 1]
        _swap(stretch, swaps)
        after = _out_of_order(stretch)
        if not swaps or after >= disorder:
            _swap(stretch, swaps)  # each swap undoes itself
            return
        disorder = after


def _curve_blocks(stretch: _Stretch, held: list[bool]) -> list[list[int]]:
    """The runs between equal diagonals, in blocks broken at every turn, kept corner or held run."""
    blocks: list[list[int]] = [[]]
    for index, run in enumerate(stretch.runs):
        before = stretch.diagonal_before(index)
        after = stretch.diagonals[index] if index < len(stretch.diagonals) else None
        if (
            not held[index]
            and after is not None
            and before == after
            and _slope(run) is not None
            and stretch.fits(run, after)
        ):
            blocks[-1].append(index)
        elif blocks[-1]:
            blocks.append([])
    blocks = [block for block in blocks if block]
    last = len(stretch.runs) - 1
    if stretch.closed and len(blocks) > 1 and blocks[0][0] == 0 and blocks[-1][-1] == last:
        blocks[0] = blocks.pop() + blocks[0]  # one block across the seam of a closed line
    return blocks


def _sort_curves(stretch: _Stretch, held: list[bool]) -> None:
    """Order the runs of each curved block from one end's slope to the other's.

    A straight line has runs of at most two lengths, in a rhythm that must stay (2, 3, 2, 3).
    A block with three or more is a curve, whose runs grow or shrink without turning back; a
    run out of that order is the jaggy (2, 2, 1, 1, 2, 1, 1). Sorting keeps the block's runs and
    so both its ends in place. A ``held`` run, on a straight side of the path, never moves.
    """
    for block in _curve_blocks(stretch, held):
        slopes = [_slope(stretch.runs[i]) or 0.0 for i in block]
        if len(set(slopes)) < 3:  # noqa: PLR2004  # motivo: a straight line has two run lengths
            continue
        half = len(block) // 2
        first, last = sum(slopes[:half]), sum(slopes[-half:])
        if first == last:
            continue
        rising = first < last
        runs = sorted(
            (stretch.runs[i] for i in block), key=lambda run: _slope(run) or 0.0, reverse=not rising
        )
        for i, run in zip(block, runs, strict=True):
            stretch.runs[i] = run


def _held_runs(cells: list[Cell], steps: list[Step], straight: AbstractSet[Cell]) -> list[bool]:
    """Per run, whether it touches a cell of ``straight``; ``cells[i]`` starts ``steps[i]``."""
    held = [False]
    for cell, step in zip(cells, steps, strict=False):
        held[-1] = held[-1] or cell in straight
        if _is_diagonal(step):
            held.append(False)
    return held


def _cells_along(run: list[Step], axis: int) -> int | None:
    """The cells ``run`` lays along ``axis`` (0 a row, 1 a column); None if it runs across."""
    if any(step[1 - axis] for step in run):
        return None
    return len(run) + 1


def _reach(stretch: _Stretch, index: int, axis: int) -> float | None:
    """A run's length as the eye reads it: half of it on top of a round shape.

    The top is the run whose diagonals turn back across ``axis``: both sides share it.
    """
    length = _cells_along(stretch.runs[index], axis)
    before = stretch.diagonal_before(index)
    after = stretch.diagonals[index] if index < len(stretch.diagonals) else None
    if length is None or before is None or after is None:
        return None
    if before == after:
        return length
    turns_back = before[axis] == after[axis] and before[1 - axis] != after[1 - axis]
    return length / 2 if turns_back else None


def _gentler(stretch: _Stretch, index: int, held: list[bool]) -> list[tuple[int, int, Step]]:
    """The step that run ``index`` and the next should trade, if one is over twice the other.

    It goes from the longer to the shorter, along the axis both lie on: (giver, taker, step).
    """
    after = (index + 1) % len(stretch.runs) if stretch.closed else index + 1
    if after >= len(stretch.runs) or index >= len(stretch.diagonals) or held[index] or held[after]:
        return []
    diagonal = stretch.diagonals[index]
    for axis in (0, 1):
        first, second = _reach(stretch, index, axis), _reach(stretch, after, axis)
        if first is None or second is None:
            continue
        longer, shorter = max(first, second), min(first, second)
        if longer > 2 * shorter and longer >= _ABRUPT_FROM:
            step = (diagonal[0], 0) if axis == 0 else (0, diagonal[1])
            giver, taker = (index, after) if first > second else (after, index)
            return [(giver, taker, step)]
    return []


def _unmixed(stretch: _Stretch, trades: list[tuple[int, int, Step]]) -> list[tuple[int, int, Step]]:
    """The trades that leave every run going one way.

    Between two tops, a one-cell run is wanted by both, across and down: it would become a
    corner. Every trade it takes part in is dropped, and the corner of the shape stays as it is.
    """
    ways: dict[int, set[Step]] = {}
    for giver, taker, step in trades:
        ways.setdefault(taker, set(stretch.runs[taker])).add(step)
        _ = ways.setdefault(giver, set(stretch.runs[giver]))
    mixed = {index for index, steps in ways.items() if len(steps) > 1}
    return [trade for trade in trades if not mixed & {trade[0], trade[1]}]


def _swings(runs: list[list[Step]], *, closed: bool) -> set[int]:
    """The runs in an a, b, a of short runs on one axis: the stroke that swells and thins.

    Read across the line, a 1 between two 2s (or a 2 between two 1s) is the wobble the detector
    counts. A run across the axis lays one cell on each line of it, so it reads as 1.
    """
    count, found = len(runs), set[int]()
    middles = range(count) if closed else range(1, count - 1)
    for middle, axis in itertools.product(middles, (0, 1)):
        trio = [(middle + offset) % count for offset in (-1, 0, 1)]
        first, second, third = (_cells_along(runs[i], axis) or 1 for i in trio)
        if first == third != second and max(first, second) <= 2:  # noqa: PLR2004  # motivo: the one-pixel line's swing
            found.update(trio)
    return found


def _no_new_swing(
    stretch: _Stretch, trades: list[tuple[int, int, Step]]
) -> list[tuple[int, int, Step]]:
    """The trades, unless together they make a swing that was not there (``_swings``).

    The side of a narrow shape is long next to a tip of one cell: passing a cell to the runs
    beside the tip makes 2, 1, 2 across it, a wobble worse than the step it smooths.
    """
    after = [list(run) for run in stretch.runs]
    for giver, taker, step in trades:
        after[giver].remove(step)
        after[taker].append(step)
    new = _swings(after, closed=stretch.closed) - _swings(stretch.runs, closed=stretch.closed)
    return [trade for trade in trades if not new & {trade[0], trade[1]}]


def _soften(stretch: _Stretch, held: list[bool]) -> Step:
    """Pass a step from a run to its neighbor while one is over twice the other.

    The flat top of a large circle reads as an octagon when the next run is a third of it
    (``abrupt_steps``); a pixel artist shortens the top and lengthens the runs after it. Every
    pass decides its trades before making any, so both sides of a top give at once and a
    mirrored shape stays mirrored. A trade always goes from longer to shorter, so it ends.

    Returns how far the first cell moves: a closed line is rebuilt from the start of its first
    run, and a trade across that seam carries the start with it.
    """
    start = (0, 0)
    while trades := _no_new_swing(
        stretch,
        _unmixed(
            stretch, [t for i in range(len(stretch.runs)) for t in _gentler(stretch, i, held)]
        ),
    ):
        for giver, taker, step in trades:
            stretch.runs[giver].remove(step)
            stretch.runs[taker].append(step)
            sign = (giver == 0 and taker != 1) - (taker == 0 and giver != 1)
            start = (start[0] + sign * step[0], start[1] + sign * step[1])
    return start


def _rebuild(start: Cell, stretch: _Stretch) -> list[Cell]:
    cells = [start]
    for index, run in enumerate(stretch.runs):
        steps = [*run, *stretch.diagonals[index : index + 1]]
        for dx, dy in steps:
            cells.append((cells[-1][0] + dx, cells[-1][1] + dy))
    return cells


def even_out_steps(
    cells: list[Cell],
    *,
    closed: bool,
    straight: AbstractSet[Cell] = _NO_CELLS,
    sort_curves: bool = True,
) -> list[Cell]:
    """Put the runs of a one-pixel line back in order, each between its neighbors' lengths.

    A run that is not straight (a corner the line keeps) and the runs at an open line's ends
    never move. ``closed`` lines are read around the seam. The cells in ``straight`` lie on a
    straight side of the path: a curve's order never reaches the runs through them, whose
    rhythm is the side's own (``_sort_curves``). Without ``sort_curves`` the steps are only
    settled: sorting takes a stretch that bends both ways for one curve, and moves it.
    """
    steps = _steps(cells, closed=closed)
    diagonal_at = [i for i, step in enumerate(steps) if _is_diagonal(step)]
    if len(cells) < 3 or not diagonal_at:  # noqa: PLR2004  # motivo: a line needs three cells to bend
        return list(cells)
    shift = (diagonal_at[-1] + 1) % len(steps) if closed else 0
    runs, diagonals = _split(steps[shift:] + steps[:shift])
    stretch = _Stretch(runs[:-1] if closed else runs, diagonals, closed=closed)
    rotated = cells[shift:] + cells[:shift]
    held = _held_runs(rotated, steps[shift:] + steps[:shift], straight)
    if sort_curves:
        _sort_curves(stretch, held)
    _settle(stretch)
    moved = _soften(stretch, held)
    rebuilt = _rebuild((cells[shift][0] + moved[0], cells[shift][1] + moved[1]), stretch)
    if not closed:
        return rebuilt
    del rebuilt[-1]
    return rebuilt[-shift:] + rebuilt[:-shift] if shift else rebuilt

# SPDX-License-Identifier: GPL-3.0-only
"""Even out the steps of a one-pixel line: a curve's steps change length in one direction.

A line is read as runs (straight stretches of cells) separated by diagonal steps. Along a
quarter circle the runs go from long and flat to long and steep without turning back; a run
out of that order is the jaggy a pixel artist fixes by hand. Swapping two neighboring runs
between equal diagonals keeps both ends of the stretch in place and the line connected.

    >>> jagged = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (5, 2), (6, 2), (7, 3)]
    >>> even_out_steps(jagged, closed=False)[5]
    (5, 1)
"""

from __future__ import annotations

Cell = tuple[int, int]
Step = tuple[int, int]


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

    def _diagonal_before(self, index: int) -> Step | None:
        if index == 0:
            return self.diagonals[-1] if self.closed else None
        return self.diagonals[index - 1]

    def _fits(self, run: list[Step], diagonal: Step) -> bool:
        return all(step in {(diagonal[0], 0), (0, diagonal[1])} for step in run)

    def swappable(self, first: int, second: int) -> bool:
        """Two neighbors that lie between three equal diagonals, both plain runs."""
        before, between = self._diagonal_before(first), self.diagonals[first]
        after = self.diagonals[second] if second < len(self.diagonals) else None
        if before is None or after is None or not before == between == after:
            return False
        return all(
            _slope(self.runs[i]) is not None and self._fits(self.runs[i], between)
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


def _settle(stretch: _Stretch) -> None:
    """Swap runs until every one sits in the order of its neighbors.

    Each pass decides all its swaps before making any, and drops the swaps that share a run,
    so the result does not depend on which end the line was drawn from.
    """
    for _ in range(len(stretch.runs) ** 2):
        proposals = {pair for i in range(len(stretch.runs)) if (pair := _proposal(stretch, i))}
        used = [i for pair in proposals for i in pair]
        swaps = [pair for pair in proposals if used.count(pair[0]) == used.count(pair[1]) == 1]
        if not swaps:
            return
        for first, second in swaps:
            stretch.runs[first], stretch.runs[second] = stretch.runs[second], stretch.runs[first]


def _rebuild(start: Cell, stretch: _Stretch) -> list[Cell]:
    cells = [start]
    for index, run in enumerate(stretch.runs):
        steps = [*run, *stretch.diagonals[index : index + 1]]
        for dx, dy in steps:
            cells.append((cells[-1][0] + dx, cells[-1][1] + dy))
    return cells


def even_out_steps(cells: list[Cell], *, closed: bool) -> list[Cell]:
    """Put the runs of a one-pixel line back in order, each between its neighbors' lengths.

    A run that is not straight (a corner the line keeps) and the runs at an open line's ends
    never move. ``closed`` lines are read around the seam.
    """
    steps = _steps(cells, closed=closed)
    diagonal_at = [i for i, step in enumerate(steps) if _is_diagonal(step)]
    if len(cells) < 3 or not diagonal_at:  # noqa: PLR2004 - a line needs three cells to bend
        return list(cells)
    shift = (diagonal_at[-1] + 1) % len(steps) if closed else 0
    runs, diagonals = _split(steps[shift:] + steps[:shift])
    stretch = _Stretch(runs[:-1] if closed else runs, diagonals, closed=closed)
    _settle(stretch)
    rebuilt = _rebuild(cells[shift], stretch)
    if not closed:
        return rebuilt
    del rebuilt[-1]
    return rebuilt[-shift:] + rebuilt[:-shift] if shift else rebuilt

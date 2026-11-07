# SPDX-License-Identifier: GPL-3.0-only
"""The change cycle's rule on commits (ADR-0007): what a commit must bring for what it touches.

Kept apart from architecture_rules.py, which checks the tree; this one reads the history.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

EVIDENCE = (re.compile(r"\bComando\b"), re.compile(r"\bVermelho\b"), re.compile(r"\bVerde\b"))
# What a rename leaves as it was: strings, numbers and symbols. A name may change, these may not.
MEANING = re.compile(r"""\"[^\"]*\"|'[^']*'|\d[\d_.]*|[^\w\s]""")
# The commits that break no rule in src/: refactor and the two kinds the cycle covers.
CHANGE_KINDS = frozenset({"fix", "feat"})
SOURCE_KINDS = CHANGE_KINDS | {"refactor"}


@dataclass(frozen=True, slots=True)
class Commit:
    """What the change cycle reads of one commit (ADR-0007)."""

    subject: str
    body: str
    files: tuple[str, ...]
    test_diff: str


def commit_violations(commit: Commit) -> list[str]:
    """ADR-0007: what ``commit`` breaks of the change cycle."""
    kind = re.split(r"\W", commit.subject, maxsplit=1)[0]
    if kind == "refactor":
        return _changed_expectations(commit)
    if not any(name.startswith("src/") for name in commit.files):
        return []
    if kind not in SOURCE_KINDS:
        return [f"{commit.subject!r}: src/ changes as fix, feat or refactor (ADR-0007)"]
    missing = [rule.pattern.strip("\\b") for rule in EVIDENCE if not rule.search(commit.body)]
    if not any(_is_test(name) for name in commit.files):
        missing.append("a test in the same commit")
    return [f"{commit.subject!r} lacks {item} (ADR-0007)" for item in missing]


def _is_test(name: str) -> bool:
    return name.startswith("tests/") and name.endswith(".py")


def _tokens(line: str) -> list[str]:
    found: list[str] = MEANING.findall(line)
    return found


def _meaning(lines: list[str]) -> Counter[str]:
    return Counter(token for line in lines for token in _tokens(line))


def _changed_expectations(commit: Commit) -> list[str]:
    """A refactor changes no test: names may follow a rename, and nothing else may differ."""
    lines = [line for line in commit.test_diff.splitlines() if line[:3] not in {"---", "+++"}]
    removed = [line[1:] for line in lines if line.startswith("-")]
    added = [line[1:] for line in lines if line.startswith("+")]
    if _meaning(removed) == _meaning(added):
        return []
    return [f"{commit.subject!r} changes what a test expects (AGENTS.md, ADR-0007)"]


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # motivo: fixed git arguments, no shell
        ["git", *arguments],  # noqa: S607  # motivo: git from PATH, as the gate runs it
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _read_commit(root: Path, revision: str) -> Commit:
    return Commit(
        subject=_git(root, "log", "-1", "--format=%s", revision).stdout.strip(),
        body=_git(root, "log", "-1", "--format=%b", revision).stdout,
        files=tuple(
            _git(root, "show", "--no-color", "--format=", "--name-only", revision).stdout.split()
        ),
        test_diff=_git(root, "show", "--no-color", "--format=", revision, "--", "tests").stdout,
    )


def cycle_violations(root: Path) -> list[str]:
    """ADR-0007: what the commits not yet on origin/main break, and always the last one.

    The fix and the docs commit after it go up together, so the last one alone would hide the
    fix (audit, 04/11). The CI's checkout is at origin/main, so it sees only the last one.
    """
    unpushed = _git(root, "rev-list", "origin/main..HEAD").stdout.split()
    revisions = dict.fromkeys(["HEAD", *unpushed])
    return [item for name in revisions for item in commit_violations(_read_commit(root, name))]

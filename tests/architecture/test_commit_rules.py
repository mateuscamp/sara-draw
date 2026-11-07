# SPDX-License-Identifier: GPL-3.0-only
"""Fitness function of ADR-0007: every commit keeps the change cycle."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from architecture_rules import ROOT
from commit_rules import Commit, commit_violations, cycle_violations

if TYPE_CHECKING:
    from pathlib import Path

_EVIDENCE = "Comando: uv run pytest\nVermelho: assert 1 == 0\nVerde: 10 passed"
_SOURCE = "src/ai_draw/pixel/line.py"
_TEST = "tests/pixel/test_line.py"


@pytest.mark.parametrize("kind", ["fix", "feat", "fix(line)", "fix!"])
def test_commit_rule_flags_a_source_change_without_a_test(kind: str) -> None:
    assert commit_violations(Commit(f"{kind}: x", _EVIDENCE, (_SOURCE,), "")) != []


@pytest.mark.parametrize(
    "body",
    [
        "Comando: x\nVerde: 10 passed",
        "Comando: x\nVermelho: 1 == 0",
        "Vermelho: 1 == 0\nVerde: 10 passed",
        "Comando: x\nVermelhou\nVerde: 10 passed",
        "Comando: x\nVermelho: 1 == 0\nVerdemar",
    ],
    ids=["no_red", "no_green", "no_command", "red_inside_a_word", "green_inside_a_word"],
)
def test_commit_rule_flags_a_source_change_without_evidence(body: str) -> None:
    assert commit_violations(Commit("fix: x", body, (_SOURCE, _TEST), "")) != []


@pytest.mark.parametrize("kind", ["perf", "style", "chore", "docs", "bugfix", "Update"])
def test_commit_rule_flags_any_other_kind_of_commit_in_the_source(kind: str) -> None:
    assert commit_violations(Commit(f"{kind}: x", _EVIDENCE, (_SOURCE, _TEST), "")) != []


def test_commit_rule_takes_a_capitalized_kind_for_another_kind() -> None:
    assert commit_violations(Commit("Fix: x", _EVIDENCE, (_SOURCE,), "")) != []
    diff = "--- a/tests/a.py\n+++ b/tests/a.py\n-x = 1\n+x = 2\n"
    assert commit_violations(Commit("Refactor: x", "", (_SOURCE, _TEST), diff)) != []


def test_commit_rule_wants_a_test_file_not_any_file_under_tests() -> None:
    score = "tests/bench/score.json"
    assert commit_violations(Commit("fix: x", _EVIDENCE, (_SOURCE, score), "")) != []


def test_commit_rule_accepts_a_source_change_with_test_and_evidence() -> None:
    assert commit_violations(Commit("fix: x", _EVIDENCE, (_SOURCE, _TEST), "")) == []


def test_commit_rule_ignores_a_fix_outside_the_source() -> None:
    assert commit_violations(Commit("fix: x", "", ("README.md",), "")) == []


@pytest.mark.parametrize("line", ["-    assert x == 1", "+    assert x == 2"])
def test_commit_rule_flags_a_refactor_that_changes_an_assertion(line: str) -> None:
    diff = f"--- a/tests/a.py\n+++ b/tests/a.py\n{line}\n"
    assert commit_violations(Commit("refactor: x", "", (_SOURCE, _TEST), diff)) != []


@pytest.mark.parametrize(
    "changed",
    ['-EXPECTED = ["##"]\n+EXPECTED = ["#."]\n', "-    pytest.param(1),\n+    pytest.param(2),\n"],
    ids=["expected_rows", "parameter"],
)
def test_commit_rule_flags_a_refactor_that_changes_what_a_test_expects(changed: str) -> None:
    diff = f"--- a/tests/a.py\n+++ b/tests/a.py\n{changed}"
    assert commit_violations(Commit("refactor: x", "", (_SOURCE, _TEST), diff)) != []


def test_commit_rule_flags_a_refactor_that_deletes_a_test() -> None:
    diff = "--- a/tests/a.py\n+++ b/tests/a.py\n-def test_a() -> None:\n-    assert f() == 1\n"
    assert commit_violations(Commit("refactor: x", "", (_SOURCE, _TEST), diff)) != []


def test_commit_rule_accepts_a_refactor_that_only_renames() -> None:
    diff = "--- a/tests/a.py\n+++ b/tests/a.py\n-    assert old(1) == 2\n+    assert new(1) == 2\n"
    assert commit_violations(Commit("refactor: x", "", (_SOURCE, _TEST), diff)) == []


def _run_git(root: Path, *arguments: str) -> None:
    _ = subprocess.run(  # noqa: S603  # motivo: fixed git arguments, no shell
        [  # noqa: S607  # motivo: git from PATH, as the gate runs it
            "git",
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "core.hooksPath=/dev/null",
            *arguments,
        ],
        cwd=root,
        capture_output=True,
        check=True,
    )


def _commit(root: Path, name: str, subject: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(f"# {subject}\n", encoding="utf-8")
    _run_git(root, "add", ".")
    _run_git(root, "commit", "-m", subject)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    _run_git(tmp_path, "init", "-q")
    _commit(tmp_path, "README.md", "docs: start")
    return tmp_path


@pytest.fixture
def exported_git_dir(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    _run_git(elsewhere, "init", "-q")
    monkeypatch.setenv("GIT_DIR", str(elsewhere / ".git"))


@pytest.mark.usefixtures("exported_git_dir")
def test_the_repository_fixture_stays_in_its_folder(repository: Path) -> None:
    # Regression (audit, 04/11): a GIT_DIR in the environment took its commits to that repository.
    assert (repository / ".git").is_dir()


def test_cycle_sees_a_bad_commit_under_a_later_one_not_yet_pushed(repository: Path) -> None:
    # Regression (audit, 04/11): the fix, then the docs commit that follows it, as here.
    _run_git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    _commit(repository, "src/a.py", "fix: no test")
    _commit(repository, "PLANO.md", "docs: plan")
    assert len(cycle_violations(repository)) >= 1


def test_cycle_reads_a_refactor_with_colors_on(repository: Path) -> None:
    # Regression (audit, 04/11): with color.ui=always the diff came colored, and no line matched.
    _run_git(repository, "config", "color.ui", "always")
    _commit(repository, "tests/a.py", "docs: 1")
    _commit(repository, "tests/a.py", "refactor: 2")
    assert cycle_violations(repository) != []


def test_cycle_leaves_what_is_already_pushed_alone(repository: Path) -> None:
    _commit(repository, "src/a.py", "fix: no test")
    _commit(repository, "PLANO.md", "docs: plan")
    _run_git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    _commit(repository, "NOTES.md", "docs: notes")
    assert cycle_violations(repository) == []


def test_cycle_reads_the_last_commit_with_no_origin(repository: Path) -> None:
    _commit(repository, "src/a.py", "fix: no test")
    assert len(cycle_violations(repository)) >= 1


def test_commits_not_yet_pushed_keep_the_change_cycle() -> None:
    assert cycle_violations(ROOT) == []

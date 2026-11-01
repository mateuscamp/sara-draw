# SPDX-License-Identifier: GPL-3.0-only
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-score",
        action="store_true",
        default=False,
        help="rewrite tests/bench/score.json, refused if any metric got worse",
    )

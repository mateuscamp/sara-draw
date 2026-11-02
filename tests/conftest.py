# SPDX-License-Identifier: GPL-3.0-only
import pytest
from hypothesis import settings

# ADR-0006: property tests draw the same examples on every machine and save none, and the
# machine's speed never decides a verdict. "explore" is for a session hunting further, with
# --hypothesis-profile=explore; what it finds comes back as an @example.
settings.register_profile(
    "ai-draw", derandomize=True, database=None, deadline=None, max_examples=100
)
settings.register_profile("explore", database=None, deadline=None, max_examples=2000)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-score",
        action="store_true",
        default=False,
        help="rewrite tests/bench/score.json, refused if any metric got worse",
    )


def pytest_configure(config: pytest.Config) -> None:
    # Loaded here and only without --hypothesis-profile: loaded on import, it would run after
    # Hypothesis's own plugin and undo the profile asked for on the command line.
    chosen: object = config.getoption("hypothesis_profile")
    if chosen is None:
        settings.load_profile("ai-draw")

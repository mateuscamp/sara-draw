# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
from typing import cast

import pytest
from bench_cases import Score, differences, measure, worse

SCORE = Path(__file__).with_name("score.json")
UPDATE_HINT = "if it only got better: uv run pytest tests/bench --update-score"


def recorded_score() -> dict[str, Score]:
    if not SCORE.exists():
        return {}
    return cast("dict[str, Score]", json.loads(SCORE.read_text(encoding="utf-8")))


def test_bench_matches_the_recorded_score(request: pytest.FixtureRequest) -> None:
    recorded, measured = recorded_score(), measure()
    if request.config.getoption("--update-score") is True:
        refused = worse(recorded, measured)
        assert not refused, "the score only goes down:\n" + "\n".join(refused)
        text = json.dumps(measured, indent=2, sort_keys=True) + "\n"
        _ = SCORE.write_text(text, encoding="utf-8")
        recorded = measured
    changes = "\n".join(differences(recorded, measured))
    assert measured == recorded, f"bench differs from score.json:\n{changes}\n{UPDATE_HINT}"


def test_bench_is_deterministic() -> None:
    assert measure() == measure()


def test_differences_say_worse_and_better() -> None:
    recorded = {"star": {"orphans": 2, "l_corners": 1}}
    measured = {"star": {"orphans": 3, "l_corners": 0}}
    assert differences(recorded, measured) == [
        "star.l_corners: 1 -> 0 (better)",
        "star.orphans: 2 -> 3 (worse)",
    ]


def test_the_ratchet_refuses_only_what_got_worse() -> None:
    recorded = {"star": {"orphans": 2}, "wave": {"thickness": 5}}
    measured = {"star": {"orphans": 1}, "wave": {"thickness": 6}, "new": {"orphans": 0}}
    assert worse(recorded, measured) == ["wave.thickness: 5 -> 6 (worse)"]


def test_a_metric_that_did_not_exist_is_new_not_worse() -> None:
    assert differences({}, {"star": {"orphans": 4}}) == ["star.orphans: None -> 4 (new)"]
    assert worse({}, {"star": {"orphans": 4}}) == []

import json
from pathlib import Path

from sqlalchemy import Engine, text

from atlas.evaluation.fixtures import fixture_names
from atlas.evaluation.runner import run_eval
from atlas.settings import get_settings


def test_oracle_run_meets_every_target_and_cleans_up(tmp_path: Path, owner_engine: Engine) -> None:
    history = tmp_path / "history.jsonl"
    outcome = run_eval(get_settings(), fixture_names(), live=False, history=history)

    assert outcome.all_met and not outcome.failed, outcome.scorecard
    assert outcome.results["statement_recall"] == 1.0
    assert outcome.results["diagnosis_rule_violations"] == 0
    assert set(outcome.per_fixture) == set(fixture_names())
    line = json.loads(history.read_text().splitlines()[-1])
    assert line["providers"] == "oracle" and line["all_met"] is True
    assert line["prompt_versions"] == ["concepts_v1", "statements_v1"]
    assert line["schema_version"] == 1
    with owner_engine.connect() as connection:
        left = connection.execute(
            text("SELECT count(*) FROM users WHERE email LIKE '%@eval.invalid'")
        )
        assert left.scalar_one() == 0

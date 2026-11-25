"""Run the extraction pipeline over the synthetic fixtures and score it.

Each fixture is processed in its own throwaway user, so fixtures do not see each
other's concepts. The users are deleted afterwards.
"""

import datetime
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from atlas.db.models import Evidence, Node, Run, Source, Statement
from atlas.db.seed import create_user
from atlas.db.session import get_engine, user_session
from atlas.domain.generated.vocabulary import VOCABULARY_VERSION, NodeType, RecordState
from atlas.evaluation.fixtures import Fixture, ingest, load_fixture
from atlas.evaluation.oracle import oracle_handlers
from atlas.evaluation.scorecard import Tally, render, score_fixture
from atlas.pipeline.handlers import HANDLERS
from atlas.pipeline.runner import drain
from atlas.pipeline.stages import PIPELINE_VERSION
from atlas.providers.base import Providers, TextBlock, ToolCall
from atlas.providers.fakes import FakeBlobStore, FakeEmbedder, FakeExtractionModel, FakeTranscriber
from atlas.providers.registry import build_providers
from atlas.settings import REPO_ROOT, Settings

EVAL_EMAIL_SUFFIX = "@eval.invalid"
HISTORY = REPO_ROOT / "evals" / "history.jsonl"
JUDGE_SAMPLE = 40

JUDGE_PROMPT = (
    "You are checking one entry in a personal atlas built from what a person and their "
    "therapist said. Decide whether the cited statements support the entry: a reader who "
    "saw only these statements would agree the entry is a fair reading of them. An entry "
    "marked as inferred needs real grounds in the statements, not certainty. Answer that it "
    "is not supported if it adds something the statements do not say or imply."
)
JUDGE_TOOL: dict[str, Any] = {
    "name": "judge_support",
    "description": "Say whether the statements support the atlas entry.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["supported", "reason"],
        "properties": {"supported": {"type": "boolean"}, "reason": {"type": "string"}},
    },
}


@dataclass
class EvalResult:
    results: dict[str, float | None]
    per_fixture: dict[str, dict[str, float | None]]
    usage: dict[str, int]
    failed: list[str]
    scorecard: str
    all_met: bool


def oracle_providers(fixtures: list[Fixture]) -> Providers:
    return Providers(
        blobs=FakeBlobStore(),
        transcriber=FakeTranscriber(),
        extraction=FakeExtractionModel(oracle_handlers(fixtures)),
        embedder=FakeEmbedder(),
    )


def judge(
    session: Session, source_id: uuid.UUID, providers: Providers, model: str
) -> dict[uuid.UUID, bool]:
    """Ask the model whether each stored concept is supported by the statements it cites."""
    statement_ids = select(Statement.id).where(Statement.source_id == source_id)
    nodes = session.scalars(
        select(Node)
        .where(
            Node.id.in_(
                select(Evidence.target_id).where(
                    Evidence.target_kind == "node", Evidence.statement_id.in_(statement_ids)
                )
            ),
            Node.state == RecordState.ACTIVE.value,
            Node.type != NodeType.UNSORTED.value,
            Node.is_system.is_(False),
        )
        .order_by(Node.id)
        .limit(JUDGE_SAMPLE)
    ).all()
    verdicts: dict[uuid.UUID, bool] = {}
    for node in nodes:
        cited = session.execute(
            select(Statement.speaker_role, Statement.text, Evidence.basis, Evidence.stance)
            .join(Evidence, Evidence.statement_id == Statement.id)
            .where(Evidence.target_kind == "node", Evidence.target_id == node.id)
        ).all()
        entry = {
            "entry": {
                "type": node.type,
                "kind": node.kind,
                "name": node.name,
                "status": node.status,
            },
            "statements": [
                {"speaker": role, "statement": said, "marked": basis, "stance": stance}
                for role, said, basis, stance in cited
            ],
        }
        answer = providers.extraction.call(
            ToolCall(
                model, [TextBlock(JUDGE_PROMPT)], [TextBlock(json.dumps(entry, indent=1))],
                JUDGE_TOOL, max_tokens=400, purpose="judge_support",
            )
        )  # fmt: skip
        verdicts[node.id] = bool(answer.data.get("supported"))
    return verdicts


def delete_eval_users(settings: Settings) -> int:
    engine = create_engine(settings.database_owner_url.get_secret_value())
    with engine.begin() as connection:
        deleted = connection.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": f"%{EVAL_EMAIL_SUFFIX}"},
        ).rowcount
    engine.dispose()
    return int(deleted)


def run_eval(
    settings: Settings, fixture_names: list[str], *, live: bool, history: Path | None = HISTORY
) -> EvalResult:
    fixtures = [load_fixture(name) for name in fixture_names]
    providers = build_providers(settings) if live else oracle_providers(fixtures)
    total = Tally()
    per_fixture: dict[str, dict[str, float | None]] = {}
    usage: dict[str, int] = {}
    failed: list[str] = []
    models: set[str] = set()
    prompts: set[str] = set()
    try:
        for fixture in fixtures:
            with Session(get_engine()) as session, session.begin():
                user_id = create_user(
                    session, f"{fixture.name}-{uuid.uuid4().hex[:8]}{EVAL_EMAIL_SUFFIX}"
                )
            with user_session(user_id) as session:
                source_id = ingest(session, user_id, fixture)
            drain(HANDLERS, providers, settings)
            with user_session(user_id) as session:
                source = session.get(Source, source_id)
                if source is None or source.status != "ready":
                    failed.append(fixture.name)
                    continue
                verdicts = (
                    judge(session, source_id, providers, settings.extraction_model)
                    if live
                    else None
                )
                tally = score_fixture(session, source_id, fixture, verdicts)
                for run in session.scalars(select(Run).where(Run.source_id == source_id)):
                    for key, value in (run.usage or {}).items():
                        if key.endswith("_tokens"):
                            usage[key] = usage.get(key, 0) + int(value)
                    if run.model:
                        models.add(run.model)
                    if run.prompt_version:
                        prompts.add(run.prompt_version)
            per_fixture[fixture.name] = tally.results()
            total.merge(tally)
    finally:
        delete_eval_users(settings)

    results = total.results()
    scorecard, all_met = render(results)
    all_met = all_met and not failed
    if history is not None:
        history.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            "providers": "live" if live else "oracle",
            "models": sorted(models),
            "prompt_versions": sorted(prompts),
            "schema_version": VOCABULARY_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "thresholds": {
                "accept": settings.match_accept_threshold,
                "review": settings.match_review_threshold,
            },
            "fixtures": fixture_names,
            "failed": failed,
            "results": results,
            "usage": usage,
            "all_met": all_met,
        }
        with history.open("a") as handle:
            handle.write(json.dumps(line, sort_keys=True) + "\n")
    return EvalResult(results, per_fixture, usage, failed, scorecard, all_met)

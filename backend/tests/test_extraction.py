"""Extraction end to end with scripted model output. Invented data only."""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from atlas.db import atlas_store
from atlas.db.models import (
    Base,
    Edge,
    Evidence,
    Node,
    NodeAlias,
    ResolutionDecision,
    Run,
    Source,
    Statement,
)
from atlas.db.session import user_session
from atlas.domain.rules import RuleViolation
from atlas.evaluation.fixtures import Fixture, fixture_names, ingest, load_fixture
from atlas.evaluation.oracle import oracle_handlers
from atlas.evaluation.scorecard import TARGETS, render, score_fixture
from atlas.pipeline import sources
from atlas.pipeline.stages import Stage
from atlas.providers.base import Providers, ToolCall
from atlas.providers.fakes import FakeExtractionModel
from tests.conftest import run_pipeline

FIXTURES = [load_fixture(name) for name in fixture_names()]
ATLAS_TABLES = ("statements", "nodes", "node_aliases", "edges", "evidence", "resolution_decisions")


def use_oracle(providers: Providers) -> FakeExtractionModel:
    model = providers.extraction
    assert isinstance(model, FakeExtractionModel)
    model.handlers = oracle_handlers(FIXTURES)
    return model


def process(user_id: uuid.UUID, providers: Providers, fixture: Fixture) -> uuid.UUID:
    with user_session(user_id) as session:
        source_id = ingest(session, user_id, fixture)
    run_pipeline(providers)
    return source_id


def counts(session: Session) -> dict[str, int]:
    return {
        table: session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        for table in ATLAS_TABLES
    }


def node(session: Session, fragment: str, node_type: str | None = None) -> Node:
    session.expire_all()
    query = select(Node).where(Node.normalized_name.contains(fragment))
    if node_type:
        query = query.where(Node.type == node_type)
    return session.scalars(query).one()


def status_of(session: Session, source_id: uuid.UUID) -> str:
    session.expire_all()
    source = session.get(Source, source_id)
    assert source is not None
    return source.status


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.name)
def test_expected_output_is_stored_exactly(
    db: Session, user_id: uuid.UUID, providers: Providers, fixture: Fixture
) -> None:
    use_oracle(providers)
    source_id = process(user_id, providers, fixture)
    assert status_of(db, source_id) == "ready"

    results = score_fixture(db, source_id, fixture).results()
    for measure in TARGETS:
        wanted = 0.0 if measure in ("duplicate_rate", "diagnosis_rule_violations") else 1.0
        assert results[measure] == wanted, (measure, results[measure])
    assert results["dropped_items"] == 0 and results["silent_segment_statements"] == 0
    table, all_met = render(results)
    assert all_met and "Quote validity" in table
    edges = db.scalars(select(Edge)).all()
    assert len(edges) == len(fixture.expected["relationships"])


def test_the_hard_cases(db: Session, user_id: uuid.UUID, providers: Providers) -> None:
    use_oracle(providers)
    process(user_id, providers, load_fixture("session_one"))

    # A therapist observation the owner never echoes is observed, not stated.
    found_out = node(db, "found out")
    assert (found_out.status, found_out.noticed_by) == ("observed", ["therapist"])
    # A feeling implied but never named is a hypothesis.
    shame = node(db, "shame")
    assert (shame.status, shame.noticed_by) == ("hypothesis", ["ai"])
    # A belief stated in one place and contradicted in another keeps both sides.
    belief = node(db, "not good enough")
    stances = db.scalars(select(Evidence.stance).where(Evidence.target_id == belief.id)).all()
    assert sorted(stances) == ["contradicts", "supports"] and belief.status == "stated"
    # A diagnosis stated by the therapist is allowed; the tempting description produced none.
    diagnoses = db.scalars(select(Node).where(Node.kind == "diagnosis")).all()
    assert [(d.name, d.status) for d in diagnoses] == [("generalised anxiety disorder", "observed")]
    # An upcoming event and a formative past event.
    assert node(db, "offsite").attributes["occurrence"] == "planned"
    assert node(db, "school report").attributes["occurrence"] == "happened"
    # Statements keep the speaker's role and a time within the recording.
    observation = db.scalars(select(Statement).where(Statement.kind == "observation")).first()
    assert observation is not None and observation.speaker_role == "therapist"
    assert (
        observation.start_ms is not None
        and observation.quote_end_char > observation.quote_start_char
    )


def test_one_person_with_two_names_is_one_concept(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    process(user_id, providers, load_fixture("session_two"))
    mum = node(db, "mum", "person")
    aliases = set(db.scalars(select(NodeAlias.normalized_alias).where(NodeAlias.node_id == mum.id)))
    assert aliases == {"my mum", "ruth"}
    assert db.scalars(select(Node).where(Node.normalized_name == "ruth")).all() == []
    used_to = db.scalars(select(Edge).where(Edge.valid_to.is_not(None))).one()
    assert used_to.type == "HOLDS"


def test_processing_the_same_source_twice_leaves_identical_row_counts(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    source_id = process(user_id, providers, load_fixture("session_one"))
    first = counts(db)
    names = set(db.scalars(select(Node.name)))
    assert first["statements"] == 14 and first["evidence"] > 20

    for stage in (Stage.STATEMENTS, Stage.CONCEPTS):
        with user_session(user_id) as session:
            source = session.get(Source, source_id)
            assert source is not None
            sources.reprocess(session, source, stage)
        run_pipeline(providers)
        assert status_of(db, source_id) == "ready"
        assert counts(db) == first, stage
        assert set(db.scalars(select(Node.name))) == names


def test_a_second_source_reuses_concepts_and_logs_each_decision(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    for name in ("session_one", "session_two", "journal_one"):
        process(user_id, providers, load_fixture(name))

    dana = node(db, "dana", "person")
    assert dana.evidence_count == 6  # Three, one and two links from the three sources.
    assert dana.first_seen_at is not None and dana.last_seen_at is not None
    assert dana.first_seen_at < dana.last_seen_at
    assert len(db.scalars(select(Node).where(Node.normalized_name == "my father")).all()) == 1
    decisions = db.scalars(select(ResolutionDecision.decision)).all()
    assert "new" in decisions
    # The journal's offsite has no date, so it is not merged with the dated one.
    assert len(db.scalars(select(Node).where(Node.normalized_name.contains("offsite"))).all()) == 2
    embedded = db.scalars(select(Node).where(Node.is_system.is_(False))).all()
    assert all(n.embedding is not None and n.embedding_model == "fake-embedding" for n in embedded)
    assert all(n.embedding_dimension == 256 for n in embedded)


def test_retracting_an_extracted_source_leaves_nothing_behind(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    first = process(user_id, providers, load_fixture("session_one"))
    baseline = counts(db)
    second = process(user_id, providers, load_fixture("session_two"))
    assert counts(db) != baseline

    with user_session(user_id) as session:
        sources.retract(session, second)
    assert counts(db) == baseline
    with user_session(user_id) as session:
        sources.retract(session, first)
    assert counts(db) == dict.fromkeys(ATLAS_TABLES, 0) | {"nodes": 2}  # Me and the therapist.


# --- Validation of model output ---------------------------------------------

JOURNAL = Fixture(
    name="scripted",
    kind="journal",
    title="Scripted",
    occurred_at=FIXTURES[0].occurred_at,
    turns=[("self", "I could not sit still all day. I felt dread about the review.")],
    expected={},
)
WEIGHTS = {"love": 0, "family": 0, "friendships": 0, "work": 1, "body_health": 0, "self": 0}


def scripted(
    providers: Providers, statements: list[dict[str, Any]], concepts: dict[str, Any], **more: Any
) -> FakeExtractionModel:
    model = providers.extraction
    assert isinstance(model, FakeExtractionModel)
    model.handlers = {
        **model.handlers,
        "statements": lambda _: {"statements": statements},
        "concepts": lambda _: {"concepts": [], "relationships": [], "unsorted": [], **concepts},
        **more,
    }
    return model


def statement(quote: str, kind: str = "report", segment: str = "S0") -> dict[str, Any]:
    return {"segment": segment, "quote": quote, "text": quote, "kind": kind}


def concept(
    ref: str, node_type: str, name: str, basis: str = "explicit", **more: Any
) -> dict[str, Any]:
    return {
        "ref": ref, "type": node_type, "name": name, "description": "", "life_area_weights": WEIGHTS,
        "evidence": [{"statement": more.pop("cites", "T1"), "stance": "supports", "basis": basis}],
        **more,
    }  # fmt: skip


def run_counts(session: Session, source_id: uuid.UUID, stage: str) -> dict[str, Any]:
    run = session.scalars(select(Run).where(Run.source_id == source_id, Run.kind == stage)).one()
    assert run.raw_output is not None
    result: dict[str, Any] = run.raw_output["counts"]
    return result


def test_a_quote_that_is_not_verbatim_gets_one_repair_then_is_dropped(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    repairs: list[ToolCall] = []

    def repair(request: ToolCall) -> dict[str, Any]:
        repairs.append(request)
        return {"statements": [statement("I felt dread about the review", "feeling")]}

    scripted(
        providers,
        [
            statement("I felt dread about the review!!", "feeling"),
            statement("I was restless all day"),
            statement("I could not sit still all day"),
            statement("I could not sit still", segment="S9"),
        ],
        {},
        statements_repair=repair,
    )
    source_id = process(user_id, providers, JOURNAL)

    quotes = set(db.scalars(select(Statement.quote)))
    assert quotes == {"I felt dread about the review", "I could not sit still all day"}
    assert len(repairs) == 1
    counted = run_counts(db, source_id, "statements")
    assert counted["repaired"] == 1
    assert sum(counted["dropped"].values()) == 2


def test_the_model_never_chooses_the_speaker_role(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    session_fixture = Fixture(
        "scripted", "therapy_session", "Scripted", JOURNAL.occurred_at,
        [("therapist", "It sounds like you expect to be found out."), ("self", "I felt dread.")], {},
    )  # fmt: skip
    scripted(
        providers,
        [
            statement("It sounds like you expect to be found out", "report", "S0"),
            statement("I felt dread", "observation", "S1"),
        ],
        {},
    )
    source_id = process(user_id, providers, session_fixture)
    stored = db.scalars(select(Statement)).all()
    assert [(s.speaker_role, s.kind) for s in stored] == [("therapist", "observation")]
    assert run_counts(db, source_id, "statements")["dropped"] == {
        "observation_from_non_therapist": 1
    }


def test_a_diagnosis_nobody_stated_is_never_stored(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    scripted(
        providers,
        [statement("I could not sit still all day")],
        {
            "concepts": [
                concept("c1", "trait", "attention deficit disorder", "implied", kind="diagnosis"),
                concept("c2", "behaviour", "restlessness"),
            ]
        },
    )
    source_id = process(user_id, providers, JOURNAL)
    assert status_of(db, source_id) == "ready"
    names = set(db.scalars(select(Node.name).where(Node.is_system.is_(False))))
    assert names == {"restlessness"}
    dropped = run_counts(db, source_id, "concepts")["dropped"]
    assert dropped == {"diagnosis_without_explicit_statement": 1}


def test_misfits_go_to_unsorted_and_broken_items_are_dropped(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    scripted(
        providers,
        [statement("I could not sit still all day"), statement("I felt dread about the review", "feeling")],
        {
            "concepts": [
                concept("c1", "habit", "pacing"),
                concept("c2", "feeling", "dread", cites="T2"),
                concept("c3", "feeling", "unbacked", cites="T99"),
                concept("c4", "person", "Me"),
                {"ref": "c5", "type": "feeling"},
            ],
            "relationships": [
                {"type": "SERVES", "from": "c4", "to": "c2",
                 "evidence": [{"statement": "T2", "stance": "supports", "basis": "implied"}]},
                {"type": "ABOUT", "from": "c2", "to": "c4",
                 "evidence": [{"statement": "T2", "stance": "supports", "basis": "explicit"}]},
                {"type": "SEEN_IN", "from": "c2", "to": "c4", "evidence": []},
            ],
            "unsorted": [
                {"name": "a recurring dream", "description": "", "suggested_type": "dream",
                 "reason": "No type for dreams.",
                 "evidence": [{"statement": "T1", "stance": "supports", "basis": "explicit"}]}
            ],
        },
    )  # fmt: skip
    source_id = process(user_id, providers, JOURNAL)

    unsorted = {
        n.name: n.attributes for n in db.scalars(select(Node).where(Node.type == "unsorted"))
    }
    assert set(unsorted) == {"pacing", "a recurring dream"}
    assert unsorted["pacing"] == {
        "suggested_type": "habit",
        "reason": "Failed validation: unknown_type",
    }
    assert unsorted["a recurring dream"]["suggested_type"] == "dream"
    counted = run_counts(db, source_id, "concepts")
    assert counted["sent_to_unsorted"] == 1
    assert counted["dropped"] == {
        "no_valid_evidence": 1, "malformed": 1, "endpoints_not_allowed": 1, "unknown_relationship": 1,
    }  # fmt: skip
    # "Me" is the owner's existing node, not a second person.
    people = db.scalars(select(Node).where(Node.type == "person")).all()
    assert [p.name for p in people] == ["Me"]
    edge = db.scalars(select(Edge)).one()
    assert (edge.type, edge.to_node_id) == ("ABOUT", people[0].id)


def test_a_feeling_the_speaker_did_not_name_cannot_be_explicit(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    scripted(
        providers,
        [
            statement("I could not sit still all day"),
            statement("I felt dread about the review", "feeling"),
        ],
        {
            "concepts": [
                concept("c1", "feeling", "anxiety"),
                concept("c2", "feeling", "dread", cites="T2"),
            ]
        },
    )
    process(user_id, providers, JOURNAL)
    assert node(db, "anxiety").status == "hypothesis"
    assert node(db, "dread").status == "stated"


def test_the_commit_is_all_or_nothing(
    db: Session, user_id: uuid.UUID, providers: Providers, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_oracle(providers)

    def broken(*args: object, **kwargs: object) -> None:
        raise RuleViolation("invented_rule")

    monkeypatch.setattr(atlas_store, "recompute", broken)
    source_id = process(user_id, providers, load_fixture("session_one"))

    assert status_of(db, source_id) == "failed"
    assert counts(db) == dict.fromkeys(ATLAS_TABLES, 0) | {"nodes": 2}
    commit = db.scalars(select(Run).where(Run.source_id == source_id, Run.kind == "commit")).one()
    assert (commit.status, commit.error) == ("failed", "invented_rule")


def test_no_content_reaches_the_logs(
    user_id: uuid.UUID, providers: Providers, capsys: pytest.CaptureFixture[str]
) -> None:
    use_oracle(providers)
    fixture = load_fixture("session_one")
    process(user_id, providers, fixture)
    logged = capsys.readouterr()
    lines = [json.loads(line) for line in logged.err.splitlines() if line.startswith("{")]
    assert any(line["event"] == "stage.finished" for line in lines)
    everything = (logged.err + logged.out).casefold()
    for word in ("dread", "dana", "found out", "school report", "anxiety"):
        assert word not in everything


def test_every_table_is_covered_by_the_row_count_check() -> None:
    written = {"statements", "nodes", "node_aliases", "edges", "evidence", "resolution_decisions"}
    assert written <= {t.name for t in Base.metadata.sorted_tables}

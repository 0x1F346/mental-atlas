"""Retraction removes exactly what was written and recomputes what remains."""

import datetime
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from atlas.db import atlas_store
from atlas.db.models import Base, Run
from atlas.domain.rules import RuleViolation
from tests.support import Builder, build_first_session, build_second_session, node_named

UTC = datetime.UTC
JAN = datetime.datetime(2026, 1, 5, 9, tzinfo=UTC)
FEB = datetime.datetime(2026, 2, 9, 9, tzinfo=UTC)


def row_counts(session: Session) -> dict[str, int]:
    session.flush()
    return {
        table.name: session.execute(text(f"SELECT count(*) FROM {table.name}")).scalar_one()
        for table in Base.metadata.sorted_tables
    }


def test_graph_can_be_inserted_and_retracted_with_nothing_left_behind(
    db: Session, user_id: uuid.UUID
) -> None:
    baseline = row_counts(db)
    first = build_first_session(Builder(db, user_id))
    grown = row_counts(db)
    assert grown["statements"] == 3 and grown["nodes"] == baseline["nodes"] + 5
    assert grown["edges"] == 3 and grown["evidence"] == 9

    source_id = first.source.id
    result = atlas_store.retract_source(db, source_id)

    assert row_counts(db) == baseline
    assert (result.statements, result.evidence) == (3, 9)
    assert (result.nodes_deleted, result.edges_deleted) == (5, 3)
    assert result.storage_keys == [f"media/{source_id}/original"]


def test_computed_fields_come_from_the_evidence(db: Session, user_id: uuid.UUID) -> None:
    build_first_session(Builder(db, user_id))
    dread = node_named(db, "dread")
    belief = node_named(db, "I will be found out")
    assert dread is not None and belief is not None
    assert (dread.status, dread.noticed_by, dread.evidence_count) == ("stated", ["self"], 1)
    assert (belief.status, belief.noticed_by) == ("observed", ["therapist", "ai"])
    assert dread.first_seen_at == JAN and dread.last_seen_at == JAN
    assert dread.life_area_weights == {"work": 0.8, "self": 0.2}
    area = db.execute(
        text("SELECT key FROM life_areas WHERE id = :id"), {"id": dread.life_area_id}
    ).scalar_one()
    assert area == "work"


def test_retracting_a_later_source_recomputes_counts_dates_and_status(
    db: Session, user_id: uuid.UUID
) -> None:
    builder = Builder(db, user_id)
    build_first_session(builder)
    after_first = row_counts(db)
    second = build_second_session(builder)

    dread = node_named(db, "dread")
    belief = node_named(db, "I will be found out")
    assert dread is not None and belief is not None
    assert (dread.evidence_count, dread.first_seen_at, dread.last_seen_at) == (2, JAN, FEB)
    assert belief.status == "stated"

    atlas_store.retract_source(db, second.source.id)

    dread = node_named(db, "dread")
    belief = node_named(db, "I will be found out")
    assert dread is not None and belief is not None
    assert (dread.evidence_count, dread.first_seen_at, dread.last_seen_at) == (1, JAN, JAN)
    assert (belief.status, belief.noticed_by, belief.evidence_count) == (
        "observed",
        ["therapist", "ai"],
        2,
    )
    assert row_counts(db) == after_first


def test_retracting_the_creating_source_keeps_concepts_other_sources_support(
    db: Session, user_id: uuid.UUID
) -> None:
    builder = Builder(db, user_id)
    first = build_first_session(builder)
    second = build_second_session(builder)

    second_run_id = second.run.id
    atlas_store.retract_source(db, first.source.id)

    dread = node_named(db, "dread")
    assert dread is not None
    assert (dread.state, dread.evidence_count, dread.first_seen_at) == ("active", 1, FEB)
    assert dread.run_id == second_run_id
    assert node_named(db, "going quiet") is None
    assert node_named(db, "Dana") is None
    assert db.execute(text("SELECT count(*) FROM edges")).scalar_one() == 0


def test_retract_run_marks_rows_another_run_created(db: Session, user_id: uuid.UUID) -> None:
    builder = Builder(db, user_id)
    first = builder.source("Invented one", JAN)
    first.node("feeling", "relief")
    second = builder.source("Invented two", FEB)
    second.link(second.say("self", "I felt relief."), builder.nodes["relief"])
    second.commit()
    assert builder.nodes["relief"].state == "active"

    run_id = second.run.id
    result = atlas_store.retract_run(db, run_id)

    relief = node_named(db, "relief")
    assert relief is not None and relief.state == "retracted" and relief.evidence_count == 0
    assert result.nodes_marked == 1 and result.nodes_deleted == 0
    run = db.get(Run, run_id)
    assert run is not None and run.status == "retracted"


def test_commit_rejects_a_diagnosis_nobody_stated(db: Session, user_id: uuid.UUID) -> None:
    session = Builder(db, user_id).source("Invented", JAN)
    statement = session.say("self", "I can never sit still in meetings.")
    session.link(statement, session.node("trait", "restlessness disorder", "diagnosis"), "implied")
    with pytest.raises(RuleViolation):
        session.commit()


def test_a_diagnosis_is_retracted_when_its_explicit_statement_goes(
    db: Session, user_id: uuid.UUID
) -> None:
    builder = Builder(db, user_id)
    first = builder.source("Invented one", JAN)
    told = first.say("therapist", "Your doctor diagnosed this last year.")
    first.link(told, first.node("trait", "an invented diagnosis", "diagnosis"))
    first.commit()
    second = builder.source("Invented two", FEB)
    second.link(
        second.say("self", "It was a hard week."), builder.nodes["an invented diagnosis"], "implied"
    )
    second.commit()
    node = node_named(db, "an invented diagnosis")
    assert node is not None and (node.status, node.state) == ("observed", "active")

    atlas_store.retract_source(db, first.source.id)

    node = node_named(db, "an invented diagnosis")
    assert node is not None and node.state == "retracted"


def test_the_owners_own_node_is_never_retracted(db: Session, user_id: uuid.UUID) -> None:
    builder = Builder(db, user_id)
    me = node_named(db, "Me")
    assert me is not None
    builder.nodes["Me"] = me
    session = builder.source("Invented", JAN)
    session.link(session.say("self", "I am the eldest."), me)
    session.commit()
    assert me.evidence_count == 1

    atlas_store.retract_source(db, session.source.id)

    me = node_named(db, "Me")
    assert me is not None
    assert (me.state, me.status, me.evidence_count) == ("active", "stated", 0)

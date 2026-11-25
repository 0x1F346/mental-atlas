"""Row-level security: a user can read and write only their own rows."""

import datetime
import uuid

import pytest
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from atlas.db.generated.constraints import CHECK_CONSTRAINTS
from atlas.db.models import Base, LifeArea, Node, Source, User
from atlas.db.session import anonymous_session, user_session

NOW = datetime.datetime(2026, 1, 5, tzinfo=datetime.UTC)


def _add_source(session: Session, user_id: uuid.UUID, title: str = "Invented session") -> Source:
    source = Source(user_id=user_id, kind="journal", title=title, occurred_at=NOW)
    session.add(source)
    session.flush()
    return source


def test_second_user_cannot_read_first_users_rows(
    user_id: uuid.UUID, other_user_id: uuid.UUID
) -> None:
    with user_session(user_id) as session:
        source_id = _add_source(session, user_id).id

    with user_session(other_user_id) as session:
        assert session.get(Source, source_id) is None
        assert session.scalars(select(Source)).all() == []
        assert [u.id for u in session.scalars(select(User))] == [other_user_id]
        assert len(session.scalars(select(LifeArea)).all()) == 6
        assert len(session.scalars(select(Node)).all()) == 1

    with user_session(user_id) as session:
        assert session.get(Source, source_id) is not None


def test_second_user_cannot_change_or_delete_first_users_rows(
    user_id: uuid.UUID, other_user_id: uuid.UUID
) -> None:
    with user_session(user_id) as session:
        source_id = _add_source(session, user_id).id
    with user_session(other_user_id) as session:
        changed = session.execute(
            text("UPDATE sources SET title = 'x' WHERE id = :id"), {"id": source_id}
        )
        deleted = session.execute(text("DELETE FROM sources WHERE id = :id"), {"id": source_id})
        assert changed.rowcount == 0  # type: ignore[attr-defined]
        assert deleted.rowcount == 0  # type: ignore[attr-defined]
    with user_session(user_id) as session:
        source = session.get(Source, source_id)
        assert source is not None and source.title == "Invented session"


def test_cannot_write_a_row_for_another_user(user_id: uuid.UUID, other_user_id: uuid.UUID) -> None:
    with pytest.raises(DBAPIError), user_session(user_id) as session:
        _add_source(session, other_user_id)


def test_session_without_a_user_sees_nothing() -> None:
    with anonymous_session() as session:
        for table in Base.metadata.sorted_tables:
            count = session.execute(text(f"SELECT count(*) FROM {table.name}")).scalar_one()
            assert count == 0, table.name


def test_application_role_cannot_bypass_row_level_security(engine: Engine) -> None:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        assert tuple(row) == (False, False)


def test_every_table_has_user_id_and_a_policy(owner_engine: Engine) -> None:
    inspector = inspect(owner_engine)
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert tables == {t.name for t in Base.metadata.sorted_tables}
    with owner_engine.connect() as connection:
        secured = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT c.relname FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid "
                    "WHERE c.relrowsecurity"
                )
            )
        }
    assert secured == tables
    for table in tables:
        columns = {column["name"] for column in inspector.get_columns(table)}
        assert {"id", "user_id", "created_at"} <= columns, table


def test_models_match_the_migrated_columns(owner_engine: Engine) -> None:
    inspector = inspect(owner_engine)
    for table in Base.metadata.sorted_tables:
        migrated = {column["name"] for column in inspector.get_columns(table.name)}
        assert migrated == {column.name for column in table.columns}, table.name


def test_generated_check_constraints_are_applied(owner_engine: Engine) -> None:
    inspector = inspect(owner_engine)
    for table, constraints in CHECK_CONSTRAINTS.items():
        applied = {c["name"] for c in inspector.get_check_constraints(table)}
        assert set(constraints) <= applied, table


def test_vocabulary_is_enforced_by_the_database(db: Session, user_id: uuid.UUID) -> None:
    def node(node_type: str, kind: str | None = None) -> Node:
        return Node(
            user_id=user_id,
            type=node_type,
            name="n",
            normalized_name="n",
            kind=kind,
            status="stated",
            schema_version=1,
        )

    for bad in (node("mood"), node("trait"), node("feeling", "strength")):
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(bad)
            db.flush()

    with pytest.raises(DBAPIError), db.begin_nested():
        inferred_diagnosis = node("trait", "diagnosis")
        inferred_diagnosis.status = "hypothesis"
        db.add(inferred_diagnosis)
        db.flush()

    feeling, need, person = node("feeling"), node("need"), node("person")
    db.add_all([feeling, need, person])
    db.flush()

    def edge(edge_type: str, from_id: uuid.UUID, to_id: uuid.UUID) -> None:
        db.execute(
            text(
                "INSERT INTO edges (id, user_id, type, from_node_id, to_node_id, status) "
                "VALUES (:id, :user_id, :type, :f, :t, 'stated')"
            ),
            {"id": uuid.uuid4(), "user_id": user_id, "type": edge_type, "f": from_id, "t": to_id},
        )

    edge("SERVES", feeling.id, need.id)
    with pytest.raises(DBAPIError), db.begin_nested():
        edge("SERVES", person.id, need.id)

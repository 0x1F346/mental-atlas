"""Database sessions. Every unit of work runs as one user (design rule 2).

`user_session` opens a transaction and sets `atlas.user_id` for it, which the
row-level security policies read. The application role cannot bypass those
policies, so a session with no user set sees no rows at all.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from atlas.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url.get_secret_value(), pool_pre_ping=True)


def set_current_user(session: Session, user_id: uuid.UUID) -> None:
    """Scope the current transaction to one user."""
    session.execute(
        text("SELECT set_config('atlas.user_id', :user_id, true)"), {"user_id": str(user_id)}
    )


@contextmanager
def user_session(user_id: uuid.UUID, engine: Engine | None = None) -> Iterator[Session]:
    """One transaction scoped to `user_id`. Commits on success, rolls back on error."""
    with Session(engine or get_engine(), expire_on_commit=False) as session, session.begin():
        set_current_user(session, user_id)
        yield session


@contextmanager
def anonymous_session(engine: Engine | None = None) -> Iterator[Session]:
    """A transaction with no user set. It can call the sign-in lookups and nothing else."""
    with Session(engine or get_engine(), expire_on_commit=False) as session, session.begin():
        yield session

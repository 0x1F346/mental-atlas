"""Test set-up. Tests use the atlas_test database and invented data only."""

import os
import uuid
from collections.abc import Iterator

TEST_DB = "localhost:54329/atlas_test"
os.environ["ATLAS_ENVIRONMENT"] = "test"
os.environ["ATLAS_PROVIDERS"] = "fake"
os.environ["ATLAS_DATABASE_URL"] = f"postgresql+psycopg://atlas_app:atlas_app@{TEST_DB}"
os.environ["ATLAS_DATABASE_OWNER_URL"] = f"postgresql+psycopg://atlas_owner:atlas_owner@{TEST_DB}"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import Engine, create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from atlas.db.seed import create_user  # noqa: E402
from atlas.db.session import get_engine, user_session  # noqa: E402
from atlas.settings import REPO_ROOT, get_settings  # noqa: E402


@pytest.fixture(scope="session")
def owner_engine() -> Iterator[Engine]:
    """An engine for the owner role, for set-up and for checks that must see every row."""
    engine = create_engine(get_settings().database_owner_url.get_secret_value())
    yield engine
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(owner_engine: Engine) -> None:
    """Rebuild the test database from migrations once per test run."""
    with owner_engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))
    config = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture
def engine() -> Engine:
    return get_engine()


def make_user(email: str | None = None) -> uuid.UUID:
    with Session(get_engine()) as session, session.begin():
        return create_user(session, email or f"user-{uuid.uuid4().hex[:12]}@example.com")


@pytest.fixture
def user_id() -> uuid.UUID:
    return make_user()


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return make_user()


@pytest.fixture
def db(user_id: uuid.UUID) -> Iterator[Session]:
    with user_session(user_id) as session:
        yield session

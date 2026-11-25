"""Test set-up. Tests use the atlas_test database and invented data only."""

import os
import subprocess
import uuid
from collections.abc import Iterator

TEST_DB = "localhost:54329/atlas_test"
os.environ["ATLAS_ENVIRONMENT"] = "test"
os.environ["ATLAS_PROVIDERS"] = "fake"
os.environ["ATLAS_BLOB_STORE"] = "memory"
os.environ["ATLAS_DATABASE_URL"] = f"postgresql+psycopg://atlas_app:atlas_app@{TEST_DB}"
os.environ["ATLAS_DATABASE_OWNER_URL"] = f"postgresql+psycopg://atlas_owner:atlas_owner@{TEST_DB}"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from atlas.api.app import create_app  # noqa: E402
from atlas.api.routes.auth import login_limiter  # noqa: E402
from atlas.api.security import hash_password  # noqa: E402
from atlas.db.seed import create_user  # noqa: E402
from atlas.db.session import get_engine, user_session  # noqa: E402
from atlas.pipeline.fake_extraction import default_handlers  # noqa: E402
from atlas.pipeline.handlers import HANDLERS  # noqa: E402
from atlas.pipeline.runner import drain  # noqa: E402
from atlas.providers.base import Providers  # noqa: E402
from atlas.providers.fakes import (  # noqa: E402
    FakeBlobStore,
    FakeEmbedder,
    FakeExtractionModel,
    FakeTranscriber,
)
from atlas.providers.registry import set_providers  # noqa: E402
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


@pytest.fixture(scope="session")
def audio_bytes(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    """Two seconds of an invented tone, standing in for a recording."""
    path = tmp_path_factory.mktemp("audio") / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "sine=frequency=440:duration=2", str(path)],
        check=True,
    )  # fmt: skip
    return path.read_bytes()


@pytest.fixture
def providers() -> Iterator[Providers]:
    """Fresh fake providers for each test, installed where the API and worker look."""
    bundle = Providers(
        blobs=FakeBlobStore(),
        transcriber=FakeTranscriber(),
        extraction=FakeExtractionModel(default_handlers()),
        embedder=FakeEmbedder(),
    )
    set_providers(bundle)
    yield bundle
    set_providers(None)


def run_pipeline(providers: Providers, limit: int = 100) -> int:
    """Run queued jobs until none is ready, as the worker would."""
    return drain(HANDLERS, providers, get_settings(), limit)


PASSWORD = "an-invented-test-password"


@pytest.fixture
def account(owner_engine: Engine) -> tuple[uuid.UUID, str]:
    """A user who can sign in: (user id, email)."""
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    new_user_id = make_user(email)
    with owner_engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET password_hash = :hash WHERE id = :id"),
            {"hash": hash_password(PASSWORD), "id": new_user_id},
        )
    return new_user_id, email


@pytest.fixture
def client(providers: Providers) -> Iterator[TestClient]:
    login_limiter.reset()
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def signed_in(client: TestClient, account: tuple[uuid.UUID, str]) -> TestClient:
    """A client signed in as `account`, sending the CSRF header on every request."""
    response = client.post("/api/v1/auth/login", json={"email": account[1], "password": PASSWORD})
    assert response.status_code == 200
    client.headers["x-csrf-token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def db(user_id: uuid.UUID) -> Iterator[Session]:
    with user_session(user_id) as session:
        yield session

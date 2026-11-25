"""Sign-in, sign-out, the session cookie and GET /auth/me."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from atlas.api.app import create_app
from atlas.api.routes.auth import login_limiter
from atlas.api.security import hash_password
from tests.conftest import make_user

PASSWORD = "an-invented-test-password"


@pytest.fixture
def client() -> Iterator[TestClient]:
    login_limiter.reset()
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def account(owner_engine: Engine) -> tuple[uuid.UUID, str]:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    user_id = make_user(email)
    with owner_engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET password_hash = :hash WHERE id = :id"),
            {"hash": hash_password(PASSWORD), "id": user_id},
        )
    return user_id, email


def sign_in(client: TestClient, email: str, password: str = PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.json()
    return str(response.json()["csrf_token"])


def test_me_requires_sign_in(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "not_signed_in", "message": "Sign in to continue."}
    }


def test_sign_in_sets_a_locked_down_cookie(
    client: TestClient, account: tuple[uuid.UUID, str]
) -> None:
    user_id, email = account
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(user_id)
    assert me.json()["email"] == email
    assert me.json()["csrf_token"] == response.json()["csrf_token"]


def test_email_is_case_insensitive(client: TestClient, account: tuple[uuid.UUID, str]) -> None:
    sign_in(client, account[1].upper())


@pytest.mark.parametrize("password", ["wrong-password", ""])
def test_wrong_password_is_refused(
    client: TestClient, account: tuple[uuid.UUID, str], password: str
) -> None:
    response = client.post("/api/v1/auth/login", json={"email": account[1], "password": password})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert "set-cookie" not in response.headers


def test_unknown_user_and_locked_seed_user_are_refused(client: TestClient) -> None:
    locked = f"user-{uuid.uuid4().hex[:12]}@example.com"
    make_user(locked)
    for email, password in (("nobody@example.com", PASSWORD), (locked, "!"), (locked, "")):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401


def test_sign_out_ends_the_session(client: TestClient, account: tuple[uuid.UUID, str]) -> None:
    csrf = sign_in(client, account[1])
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"x-csrf-token": "wrong"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"x-csrf-token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_a_stolen_cookie_value_must_match_a_stored_session(client: TestClient) -> None:
    client.cookies.set("atlas_session", "not-a-real-token")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_only_a_hash_of_the_token_is_stored(
    client: TestClient, account: tuple[uuid.UUID, str], owner_engine: Engine
) -> None:
    sign_in(client, account[1])
    token = client.cookies.get("atlas_session")
    assert token
    with owner_engine.connect() as connection:
        stored = connection.execute(
            text("SELECT token_hash FROM sessions WHERE user_id = :id"), {"id": account[0]}
        ).scalar_one()
    assert stored != token and len(stored) == 64


def test_login_is_rate_limited(client: TestClient, account: tuple[uuid.UUID, str]) -> None:
    statuses = [
        client.post(
            "/api/v1/auth/login", json={"email": account[1], "password": "wrong"}
        ).status_code
        for _ in range(7)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5:] == [429, 429]


def test_validation_errors_never_echo_what_was_sent(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "a private sentence"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "private" not in response.text
    assert "password" in response.json()["error"]["message"]


def test_unknown_routes_use_the_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"

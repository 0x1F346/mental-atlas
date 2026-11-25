"""The sources API. Invented data only."""

import uuid

from fastapi.testclient import TestClient

from atlas.providers.base import Providers
from atlas.providers.fakes import FakeBlobStore, FakeTranscriber
from tests.conftest import PASSWORD, make_user, run_pipeline
from tests.test_ingestion import JOURNAL, UNCLEAR_SCRIPT

API = "/api/v1"
ENTRY = {"kind": "journal", "title": "Invented entry", "occurred_at": "2026-03-02T18:00:00Z"}
SESSION = {
    "kind": "therapy_session",
    "title": "Invented session",
    "occurred_at": "2026-03-02T18:00:00Z",
    "content_type": "audio/wav",
}


def create_text(client: TestClient, text: str = JOURNAL) -> str:
    response = client.post(f"{API}/sources", json={**ENTRY, "text": text})
    assert response.status_code == 201, response.json()
    assert response.json()["upload"] is None
    return str(response.json()["source"]["id"])


def upload_session(client: TestClient, providers: Providers, data: bytes) -> str:
    response = client.post(f"{API}/sources", json=SESSION)
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["upload"]["method"] == "PUT" and body["upload"]["expires_in"] <= 300
    assert body["upload"]["headers"] == {"Content-Type": "audio/wav"}
    source_id = str(body["source"]["id"])
    key = body["upload"]["url"].removeprefix("memory://upload/").split("?")[0]
    providers.blobs.put(key, data, "audio/wav")  # What the browser's PUT does.
    return source_id


def test_sources_require_sign_in(client: TestClient) -> None:
    assert client.get(f"{API}/sources").status_code == 401
    assert client.post(f"{API}/sources", json={**ENTRY, "text": "x"}).status_code == 401


def test_writes_require_the_csrf_token(signed_in: TestClient) -> None:
    del signed_in.headers["x-csrf-token"]
    response = signed_in.post(f"{API}/sources", json={**ENTRY, "text": "x"})
    assert response.status_code == 403


def test_pasted_text_is_processed_and_shown(signed_in: TestClient, providers: Providers) -> None:
    source_id = create_text(signed_in)
    run_pipeline(providers)

    source = signed_in.get(f"{API}/sources/{source_id}").json()
    assert source["status"] == "ready"
    assert [s["stage"] for s in source["stages"]][:3] == ["media", "segment_text", "speakers"]
    assert all(s["status"] == "succeeded" and s["error"] is None for s in source["stages"])

    transcript = signed_in.get(f"{API}/sources/{source_id}/transcript").json()
    assert [s["text"] for s in transcript["segments"]] == JOURNAL.split("\n\n")
    assert [s["role"] for s in transcript["speakers"]] == ["self"]
    assert [s["id"] for s in signed_in.get(f"{API}/sources").json()] == [source_id]


def test_a_duplicate_is_refused_with_a_link_to_the_original(signed_in: TestClient) -> None:
    source_id = create_text(signed_in)
    response = signed_in.post(f"{API}/sources", json={**ENTRY, "text": JOURNAL})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_source"
    assert response.json()["error"]["source_id"] == source_id
    assert len(signed_in.get(f"{API}/sources").json()) == 1


def test_file_upload_flow(signed_in: TestClient, providers: Providers, audio_bytes: bytes) -> None:
    response = signed_in.post(f"{API}/sources", json=SESSION)
    source_id = response.json()["source"]["id"]
    early = signed_in.post(f"{API}/sources/{source_id}/complete")
    assert early.status_code == 409 and early.json()["error"]["code"] == "upload_missing"

    key = response.json()["upload"]["url"].removeprefix("memory://upload/").split("?")[0]
    providers.blobs.put(key, audio_bytes, "audio/wav")
    done = signed_in.post(f"{API}/sources/{source_id}/complete")
    assert done.status_code == 200 and done.json()["status"] == "transcribing"
    assert signed_in.post(f"{API}/sources/{source_id}/complete").status_code == 409
    run_pipeline(providers)

    source = signed_in.get(f"{API}/sources/{source_id}").json()
    assert source["status"] == "ready" and source["duration_ms"] > 1500
    link = signed_in.get(f"{API}/media/{source['audio_media_id']}/link").json()
    assert link["url"].startswith("memory://download/") and link["expires_in"] <= 300
    assert link["mime_type"] == "audio/mp4"

    # The same bytes again: the second source is dropped and its file deleted.
    second = upload_session(signed_in, providers, audio_bytes)
    duplicate = signed_in.post(f"{API}/sources/{second}/complete")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["source_id"] == source_id
    assert signed_in.get(f"{API}/sources/{second}").status_code == 404
    assert isinstance(providers.blobs, FakeBlobStore)
    assert not [k for k in providers.blobs.objects if second in k]


def test_unsupported_uploads_are_refused(signed_in: TestClient) -> None:
    response = signed_in.post(f"{API}/sources", json={**SESSION, "content_type": "application/zip"})
    assert response.status_code == 415
    both = signed_in.post(f"{API}/sources", json={**SESSION, "text": "x"})
    neither = signed_in.post(f"{API}/sources", json=ENTRY)
    assert both.status_code == neither.status_code == 422


def test_validation_errors_do_not_echo_pasted_text(signed_in: TestClient) -> None:
    response = signed_in.post(
        f"{API}/sources", json={"kind": "diary", "text": "a very private sentence", "title": "t"}
    )
    assert response.status_code == 422
    assert "private" not in response.text


def test_the_owner_settles_unclear_speaker_roles(
    signed_in: TestClient, providers: Providers, audio_bytes: bytes
) -> None:
    assert isinstance(providers.transcriber, FakeTranscriber)
    providers.transcriber.script = UNCLEAR_SCRIPT
    source_id = upload_session(signed_in, providers, audio_bytes)
    signed_in.post(f"{API}/sources/{source_id}/complete")
    run_pipeline(providers)
    assert signed_in.get(f"{API}/sources/{source_id}").json()["status"] == "needs_speaker_check"

    speakers = signed_in.get(f"{API}/sources/{source_id}/transcript").json()["speakers"]
    assert all(s["first_start_ms"] is not None for s in speakers)
    first, second = speakers[0]["id"], speakers[1]["id"]
    for bad in (
        {first: "self"},
        {first: "self", second: "self"},
        {first: "other", second: "therapist"},
    ):
        refused = signed_in.put(f"{API}/sources/{source_id}/speakers", json={"roles": bad})
        assert refused.status_code == 422 and refused.json()["error"]["code"] == "invalid_roles"

    answered = signed_in.put(
        f"{API}/sources/{source_id}/speakers", json={"roles": {first: "self", second: "therapist"}}
    )
    assert answered.status_code == 200 and answered.json()["status"] == "extracting"
    run_pipeline(providers)
    assert signed_in.get(f"{API}/sources/{source_id}").json()["status"] == "ready"
    roles = signed_in.get(f"{API}/sources/{source_id}/transcript").json()["speakers"]
    assert {s["id"]: (s["role"], s["method"]) for s in roles} == {
        first: ("self", "owner"),
        second: ("therapist", "owner"),
    }


def test_swapping_roles_later_reprocesses_from_the_statement_stage(
    signed_in: TestClient, providers: Providers, audio_bytes: bytes
) -> None:
    source_id = upload_session(signed_in, providers, audio_bytes)
    signed_in.post(f"{API}/sources/{source_id}/complete")
    run_pipeline(providers)
    speakers = signed_in.get(f"{API}/sources/{source_id}/transcript").json()["speakers"]
    swapped = {s["id"]: "self" if s["role"] == "therapist" else "therapist" for s in speakers}

    response = signed_in.put(f"{API}/sources/{source_id}/speakers", json={"roles": swapped})
    assert response.status_code == 200 and response.json()["status"] == "extracting"
    run_pipeline(providers)
    assert signed_in.get(f"{API}/sources/{source_id}").json()["status"] == "ready"
    assert isinstance(providers.transcriber, FakeTranscriber)
    assert len(providers.transcriber.submissions) == 1


def test_reprocess_from_a_named_stage(signed_in: TestClient, providers: Providers) -> None:
    source_id = create_text(signed_in)
    run_pipeline(providers)
    response = signed_in.post(
        f"{API}/sources/{source_id}/reprocess", json={"stage": "segment_text"}
    )
    assert response.status_code == 200 and response.json()["status"] == "transcribing"
    run_pipeline(providers)
    source = signed_in.get(f"{API}/sources/{source_id}").json()
    assert source["status"] == "ready"
    assert len(signed_in.get(f"{API}/sources/{source_id}/transcript").json()["segments"]) == 2
    bad = signed_in.post(f"{API}/sources/{source_id}/reprocess", json={"stage": "everything"})
    assert bad.status_code == 422


def test_deleting_a_source_removes_its_rows_and_files(
    signed_in: TestClient, providers: Providers, audio_bytes: bytes
) -> None:
    source_id = upload_session(signed_in, providers, audio_bytes)
    signed_in.post(f"{API}/sources/{source_id}/complete")
    run_pipeline(providers)
    assert isinstance(providers.blobs, FakeBlobStore)
    assert len(providers.blobs.objects) == 3  # original, derived audio, raw transcript

    assert signed_in.delete(f"{API}/sources/{source_id}").status_code == 204
    assert providers.blobs.objects == {}
    assert signed_in.get(f"{API}/sources/{source_id}").status_code == 404
    assert signed_in.get(f"{API}/sources").json() == []
    assert signed_in.delete(f"{API}/sources/{source_id}").status_code == 404
    # The same file can be uploaded again after a retraction.
    again = upload_session(signed_in, providers, audio_bytes)
    assert signed_in.post(f"{API}/sources/{again}/complete").status_code == 200


def test_another_users_sources_are_invisible(
    signed_in: TestClient, client: TestClient, providers: Providers, account: tuple[uuid.UUID, str]
) -> None:
    source_id = create_text(signed_in)
    run_pipeline(providers)
    signed_in.post(f"{API}/auth/logout")

    other_email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    make_user(other_email)
    assert account[1] != other_email
    from sqlalchemy import create_engine, text

    from atlas.api.security import hash_password
    from atlas.settings import get_settings

    engine = create_engine(get_settings().database_owner_url.get_secret_value())
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET password_hash = :hash WHERE email = :email"),
            {"hash": hash_password(PASSWORD), "email": other_email},
        )
    engine.dispose()
    login = client.post(f"{API}/auth/login", json={"email": other_email, "password": PASSWORD})
    client.headers["x-csrf-token"] = login.json()["csrf_token"]

    assert client.get(f"{API}/sources").json() == []
    assert client.get(f"{API}/sources/{source_id}").status_code == 404
    assert client.get(f"{API}/sources/{source_id}/transcript").status_code == 404
    assert client.delete(f"{API}/sources/{source_id}").status_code == 404

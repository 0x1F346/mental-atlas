"""Test data uploaded as JSON. Invented data only."""

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from atlas.pipeline.test_data import BlobError, parse_test_data
from atlas.providers.base import Providers
from atlas.settings import REPO_ROOT
from tests.conftest import run_pipeline

API = "/api/v1"
EXAMPLE: dict[str, Any] = json.loads(
    (REPO_ROOT / "evals/fixtures/synthetic/test_data.example.json").read_text()
)
META = {"kind": "archive", "title": "Invented test data", "occurred_at": "2026-03-02T18:00:00Z"}


def upload(client: TestClient, blob: dict[str, Any], title: str = "Invented test data") -> str:
    response = client.post(f"{API}/sources", json={**META, "title": title, "test_data": blob})
    assert response.status_code == 201, response.json()
    return str(response.json()["source"]["id"])


def landmarks(client: TestClient) -> dict[str, dict[str, Any]]:
    return {mark["name"]: mark for mark in client.get(f"{API}/map").json()["landmarks"]}


def test_the_example_blob_becomes_an_atlas(signed_in: TestClient, providers: Providers) -> None:
    source_id = upload(signed_in, EXAMPLE)
    run_pipeline(providers)
    source = signed_in.get(f"{API}/sources/{source_id}").json()
    assert source["status"] == "ready"
    assert [s["stage"] for s in source["stages"]] == ["media", "import", "embed", "place"]

    marks = landmarks(signed_in)
    expected = sum(len(v) for key, v in EXAMPLE.items() if key != "relationships")
    assert len(marks) == expected + 2  # Plus the owner and the therapist.
    assert (marks["Dana"]["type"], marks["Dana"]["life_area"], marks["Dana"]["evidence_count"]) == (
        "person",
        "work",
        4,
    )
    assert marks["dread"]["evidence_count"] == 5 and marks["dread"]["status"] == "stated"
    assert (marks["relief"]["status"], marks["relief"]["noticed_by"]) == ("observed", ["therapist"])
    assert marks["shame"]["is_hypothesis"] and marks["shame"]["noticed_by"] == ["ai"]
    assert marks["loneliness"]["life_area"] == "self"  # A bare string is a name with defaults.
    assert marks["going for a run"]["kind"] == "coping_tool"

    dread = signed_in.get(f"{API}/nodes/{marks['dread']['id']}").json()
    relations = {(r["type"], r["other"]["name"]): r for r in dread["relationships"]}
    assert set(relations) == {
        ("OCCURRED_IN", "Review with Dana, January 2026"),
        ("LED_TO", "going quiet"),
    }
    assert relations[("LED_TO", "going quiet")]["is_hypothesis"]
    mum = signed_in.get(f"{API}/nodes/{marks['my mum']['id']}").json()
    assert mum["aliases"] == ["Ruth"] and mum["attributes"] == {"relationship_to_owner": "mother"}
    # "me" is the owner's existing node, and "Ruth" resolves to "my mum".
    me = signed_in.get(f"{API}/nodes/{marks['Me']['id']}").json()
    assert {r["type"] for r in me["relationships"]} == {"HOLDS", "ABOUT", "HAS"}
    assert any(r["other"]["name"] == "the reliable one" for r in mum["relationships"])

    # Every item is traceable to a quote, given or generated.
    quotes = signed_in.get(f"{API}/nodes/{marks['dread']['id']}/evidence").json()["items"]
    assert len(quotes) == 5 and quotes[0]["quote"] == "I felt dread for days before the review."
    assert quotes[1]["quote"] == 'Test data: feeling "dread" (2)'
    assert quotes[0]["source_title"] == "Invented test data"


def test_test_data_can_be_reprocessed_and_removed(
    signed_in: TestClient,
    providers: Providers,
    owner_engine: Engine,
    account: tuple[uuid.UUID, str],
) -> None:
    def rows() -> tuple[int, ...]:
        with owner_engine.connect() as connection:
            return tuple(
                connection.execute(
                    text(f"SELECT count(*) FROM {t} WHERE user_id = :u"), {"u": account[0]}
                ).scalar_one()
                for t in ("statements", "nodes", "edges", "evidence", "map_positions")
            )

    baseline = rows()
    source_id = upload(signed_in, EXAMPLE)
    run_pipeline(providers)
    loaded = rows()
    assert loaded[2] == len(EXAMPLE["relationships"])

    # "Extract again" on a test-data source runs the import again, not the model.
    again = signed_in.post(f"{API}/sources/{source_id}/reprocess", json={"stage": "statements"})
    assert again.status_code == 200
    run_pipeline(providers)
    assert signed_in.get(f"{API}/sources/{source_id}").json()["status"] == "ready"
    assert rows() == loaded

    assert signed_in.delete(f"{API}/sources/{source_id}").status_code == 204
    after = rows()
    assert after[:4] == (
        baseline[0],
        baseline[1] + 1,
        baseline[2],
        baseline[3],
    )  # The therapist node stays.


def test_test_data_extends_what_is_already_in_the_atlas(
    signed_in: TestClient, providers: Providers
) -> None:
    upload(
        signed_in,
        {"person": [{"name": "Dana", "life_area": "work"}], "feeling": ["dread"]},
        "First",
    )
    run_pipeline(providers)
    upload(
        signed_in,
        {"person": ["dana"], "belief": ["I will be found out"],
         "relationships": [{"type": "ABOUT", "from": "I will be found out", "to": "Dana"}]},
        "Second",
    )  # fmt: skip
    run_pipeline(providers)
    marks = landmarks(signed_in)
    assert marks["Dana"]["evidence_count"] == 2 and len(marks["Dana"]["source_ids"]) == 2
    assert "dana" not in marks


def test_plural_keys_are_accepted() -> None:
    data = parse_test_data({"people": ["Sam"], "feelings": ["calm"], "beliefs": []})
    assert [(key, item.name) for key, item in data.items()] == [
        ("person", "Sam"),
        ("feeling", "calm"),
    ]


@pytest.mark.parametrize(
    ("blob", "message"),
    [
        ({}, "no concepts"),
        ({"mood": ["x"]}, "invalid test data at: mood"),
        ({"feeling": [{"description": "nameless"}]}, "feeling.0.name"),
        ({"feeling": [{"name": "dread", "kind": "strength"}]}, "feeling.0.kind is not allowed"),
        ({"trait": ["persistence"]}, "trait.0.kind is required"),
        (
            {
                "trait": [
                    {"name": "an invented condition", "kind": "diagnosis", "status": "hypothesis"}
                ]
            },
            "diagnosis cannot have status hypothesis",
        ),
        (
            {"feeling": [{"name": "dread", "body_area": "chest"}]},
            "feeling.0: unknown or invalid fields: body_area",
        ),
        (
            {"event": [{"name": "A day", "when": "not a date"}]},
            "event.0: unknown or invalid fields: when",
        ),
        ({"feeling": ["dread", "Dread"]}, "feeling.1: the same name appears twice"),
        (
            {
                "feeling": ["dread"],
                "relationships": [{"type": "ABOUT", "from": "dread", "to": "nobody"}],
            },
            "relationships.0.to names a concept that is not in the blob",
        ),
        (
            {
                "feeling": ["dread"],
                "need": ["rest"],
                "relationships": [{"type": "HOLDS", "from": "dread", "to": "rest"}],
            },
            "relationships.0.from has a type HOLDS does not allow",
        ),
        (
            {
                "feeling": ["dread"],
                "event": ["A day"],
                "relationships": [{"type": "SEEN_IN", "from": "dread", "to": "A day"}],
            },
            "relationships.0.type is written only by analysis jobs",
        ),
        ({"feeling": [{"name": "dread", "count": 500}]}, "feeling.0.count"),
    ],
)
def test_invalid_blobs_are_refused_with_the_place_at_fault(
    blob: dict[str, Any], message: str
) -> None:
    with pytest.raises(BlobError) as error:
        parse_test_data(blob)
    assert message in str(error.value)


def test_the_api_refuses_an_invalid_blob_without_echoing_it(signed_in: TestClient) -> None:
    blob = {"feeling": [{"name": "a private feeling", "kind": "secretkind"}]}
    response = signed_in.post(f"{API}/sources", json={**META, "test_data": blob})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_test_data"
    assert "feeling.0.kind" in response.json()["error"]["message"]
    assert "private" not in response.text and "secretkind" not in response.text
    assert signed_in.get(f"{API}/sources").json() == []
    both = signed_in.post(
        f"{API}/sources", json={**META, "test_data": {"feeling": ["x"]}, "text": "y"}
    )
    assert both.status_code == 422


def test_the_same_blob_twice_is_a_duplicate(signed_in: TestClient) -> None:
    first = upload(signed_in, {"feeling": ["dread"]})
    response = signed_in.post(f"{API}/sources", json={**META, "test_data": {"feeling": ["dread"]}})
    assert response.status_code == 409 and response.json()["error"]["source_id"] == first

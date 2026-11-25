"""The layout stage, GraphStore and the map read API. Invented data only."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import MapLayout, MapPosition, Node, Source
from atlas.db.session import user_session
from atlas.evaluation.fixtures import ingest, load_fixture
from atlas.graph.geometry import CENTRE, Geometry
from atlas.graph.layout import MIN_DISTANCE, inside
from atlas.graph.store import load_graph
from atlas.pipeline import sources
from atlas.pipeline.place import home_of, layout_seed
from atlas.pipeline.stages import Stage
from atlas.providers.base import Providers
from tests.conftest import run_pipeline
from tests.test_extraction import process, use_oracle

API = "/api/v1"


def positions(session: Session) -> dict[str, tuple[float, float]]:
    session.expire_all()
    rows = session.execute(
        select(Node.type, Node.normalized_name, MapPosition.x, MapPosition.y).join(
            MapPosition, MapPosition.node_id == Node.id
        )
    )
    return {f"{node_type}:{name}": (x, y) for node_type, name, x, y in rows}


def test_every_active_concept_sits_inside_its_home_region(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    for name in ("session_one", "session_two", "journal_one"):
        process(user_id, providers, load_fixture(name))

    layout = db.scalars(select(MapLayout)).one()
    assert layout.version == 1 and layout.parameters["seed"] == layout_seed(user_id)
    geometry = Geometry(layout.parameters["seed"])
    graph = load_graph(db)
    placed = {row.node_id: (row.x, row.y) for row in db.scalars(select(MapPosition))}
    assert set(placed) == {node.id for node in graph.nodes()} and len(placed) > 25
    for node in graph.nodes():
        if node.is_self:
            assert placed[node.id] == CENTRE
        else:
            assert inside(geometry, placed[node.id], home_of(node)), node.name
    points = list(placed.values())
    gaps = [
        ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        for i, a in enumerate(points)
        for b in points[i + 1 :]
    ]
    assert min(gaps) >= MIN_DISTANCE - 0.01


def test_adding_a_second_source_moves_no_existing_landmark(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    process(user_id, providers, load_fixture("session_one"))
    before = positions(db)
    homes = {n.id: n.life_area_id for n in db.scalars(select(Node))}

    process(user_id, providers, load_fixture("session_two"))
    after = positions(db)

    assert len(after) > len(before)
    changed_home = {
        f"{n.type}:{n.normalized_name}"
        for n in db.scalars(select(Node))
        if n.id in homes and homes[n.id] != n.life_area_id
    }
    for key, point in before.items():
        if key not in changed_home:
            assert after[key] == point, key


def test_reprocessing_puts_concepts_back_where_they_were(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    source_id = process(user_id, providers, load_fixture("session_one"))
    before = positions(db)
    with user_session(user_id) as session:
        source = session.get(Source, source_id)
        assert source is not None
        sources.reprocess(session, source, Stage.STATEMENTS)
    run_pipeline(providers)
    assert positions(db) == before


def test_unsorted_and_retracted_concepts_are_kept_off_the_map(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    use_oracle(providers)
    source_id = process(user_id, providers, load_fixture("journal_one"))
    assert len(positions(db)) > 5
    with user_session(user_id) as session:
        sources.retract(session, source_id)
    # Only the owner and the therapist are left, and no positions for anything else.
    left = positions(db)
    assert set(left) <= {"person:me", "person:my therapist"}


def sign_in_and_load(
    signed_in: TestClient, providers: Providers, account: tuple[uuid.UUID, str]
) -> None:
    use_oracle(providers)
    for name in ("session_one", "session_two"):
        with user_session(account[0]) as session:
            ingest(session, account[0], load_fixture(name))
        run_pipeline(providers)


def test_map_document(
    signed_in: TestClient, providers: Providers, account: tuple[uuid.UUID, str]
) -> None:
    sign_in_and_load(signed_in, providers, account)
    document = signed_in.get(f"{API}/map").json()

    assert document["layout_version"] == 1 and document["size"] == 1000
    assert [r["key"] for r in document["regions"]] == [
        "love", "family", "friendships", "work", "body_health", "self",
    ]  # fmt: skip
    assert document["regions"][4]["name"] == "Body and health"
    assert all(len(r["polygon"]) > 20 for r in document["regions"])
    by_name = {mark["name"]: mark for mark in document["landmarks"]}
    assert {"Me", "Dana", "dread", "shame", "I will be found out"} <= set(by_name)
    assert (by_name["Me"]["x"], by_name["Me"]["y"], by_name["Me"]["is_self"]) == (500, 500, True)
    assert by_name["dread"]["life_area"] == "work" and by_name["dread"]["type"] == "feeling"
    assert len(by_name["Dana"]["source_ids"]) == 2 and by_name["Dana"]["evidence_count"] == 4
    # Every hypothesis is labelled as one, and nothing else is.
    for mark in document["landmarks"]:
        assert mark["is_hypothesis"] == (mark["status"] == "hypothesis")
        assert mark["status_line"]
        if mark["is_hypothesis"]:
            assert mark["status_line"].startswith("Hypothesis")
    assert by_name["shame"]["is_hypothesis"] and by_name["shame"]["noticed_by"] == ["ai"]
    assert by_name["I will be found out"]["status"] == "observed"


def test_node_detail_and_evidence(
    signed_in: TestClient, providers: Providers, account: tuple[uuid.UUID, str]
) -> None:
    sign_in_and_load(signed_in, providers, account)
    marks = {m["name"]: m for m in signed_in.get(f"{API}/map").json()["landmarks"]}

    dread = signed_in.get(f"{API}/nodes/{marks['dread']['id']}").json()
    assert dread["status_line"].startswith("Stated") and dread["life_area"] == "work"
    relations = {(r["type"], r["direction"], r["other"]["name"]): r for r in dread["relationships"]}
    assert ("LED_TO", "out", "going quiet and not replying") in relations
    assert ("OCCURRED_IN", "out", "Review with Dana, January 2026") in relations
    led_to = relations[("LED_TO", "out", "going quiet and not replying")]
    assert led_to["is_hypothesis"] and led_to["status_line"].startswith("Hypothesis")
    mum = signed_in.get(f"{API}/nodes/{marks['my mum']['id']}").json()
    assert mum["aliases"] == ["Ruth"]

    belief = signed_in.get(
        f"{API}/nodes/{marks['I am not good enough for this job']['id']}/evidence"
    ).json()
    assert belief["title"] == "I am not good enough for this job" and not belief["is_hypothesis"]
    assert [(i["stance"], i["basis"], i["speaker_role"]) for i in belief["items"]] == [
        ("contradicts", "explicit", "self"),
        ("supports", "explicit", "self"),
    ]
    item = belief["items"][1]
    assert item["quote"] == "in the review I kept thinking I am not good enough for this job"
    assert item["source_title"] == "Synthetic session one" and item["start_ms"] is not None
    assert item["segment_id"] and item["audio_media_id"] is None

    edge = signed_in.get(f"{API}/edges/{led_to['edge_id']}/evidence").json()
    assert edge["title"] == "dread led to going quiet and not replying"
    assert edge["is_hypothesis"] and [i["basis"] for i in edge["items"]] == ["implied"]

    missing = uuid.uuid4()
    for path in (f"nodes/{missing}", f"nodes/{missing}/evidence", f"edges/{missing}/evidence"):
        assert signed_in.get(f"{API}/{path}").status_code == 404


def test_the_map_is_empty_but_drawn_before_any_source(signed_in: TestClient) -> None:
    document = signed_in.get(f"{API}/map").json()
    assert len(document["regions"]) == 6
    assert document["landmarks"] == []
    assert signed_in.get(f"{API}/map").json()["regions"] == document["regions"]


def test_map_requires_sign_in(client: TestClient) -> None:
    assert client.get(f"{API}/map").status_code == 401

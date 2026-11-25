"""An extraction model that answers with a fixture's expected output.

It proves the pipeline and the scorecard mechanics with no outside call: fed the
expected answers, the pipeline should store exactly what the fixture expects. It
says nothing about how well a real model extracts.
"""

from typing import Any

from atlas.domain.text import normalize_name
from atlas.evaluation.fixtures import Fixture
from atlas.pipeline.fake_extraction import default_handlers
from atlas.providers.base import ToolCall
from atlas.providers.fakes import Handler

AREAS = ("love", "family", "friendships", "work", "body_health", "self")


def oracle_handlers(fixtures: list[Fixture]) -> dict[str, Handler]:
    by_first_text = {fixture.turns[0][1]: fixture for fixture in fixtures}

    def fixture_for_segments(request: ToolCall) -> Fixture:
        # The cached transcript block names every segment; find the fixture it came from.
        transcript = request.system[-1].text
        for first, fixture in by_first_text.items():
            if first in transcript:
                return fixture
        raise LookupError("no fixture matches this transcript")

    def statements(request: ToolCall) -> dict[str, Any]:
        fixture = fixture_for_segments(request)
        handles = {segment["handle"] for segment in request.context["segments"]}
        return {
            "statements": [
                {"segment": f"S{s['segment']}", "quote": s["quote"], "text": s["text"],
                 "kind": s["kind"], "about_time_text": s.get("about"), "about_from": None,
                 "about_to": None, "confidence": 0.9}
                for s in fixture.expected["statements"]
                if f"S{s['segment']}" in handles
            ]
        }  # fmt: skip

    def concepts(request: ToolCall) -> dict[str, Any]:
        fixture = fixture_for_segments(request)
        expected = fixture.expected
        by_quote = {s["quote"]: s["key"] for s in expected["statements"]}
        in_window = {by_quote[s["quote"]]: s["handle"] for s in request.context["statements"]}
        shortlist: list[dict[str, Any]] = request.context["shortlist"]
        owner = next((entry["handle"] for entry in shortlist if entry["is_self"]), None)

        def cite(evidence: list[list[str]]) -> list[dict[str, str]]:
            return [
                {"statement": in_window[key], "basis": basis, "stance": stance}
                for key, basis, stance in evidence
                if key in in_window
            ]

        def shortlisted(concept: dict[str, Any]) -> str | None:
            names = {normalize_name(n) for n in [concept["name"], *concept.get("aliases", [])]}
            for entry in shortlist:
                if entry["type"] == concept["type"] and names & set(entry["aliases"]):
                    return str(entry["handle"])
            return None

        refs: dict[str, str] = {"me": owner} if owner else {}
        mentions: list[dict[str, Any]] = []
        for concept in expected["concepts"]:
            evidence = cite(concept["evidence"])
            known = shortlisted(concept)
            if known:
                refs[concept["key"]] = known
            if not evidence:
                continue
            refs[concept["key"]] = concept["key"]
            mentions.append(
                {"ref": concept["key"], "existing_id": known, "type": concept["type"],
                 "name": concept["name"], "also_called": concept.get("aliases", []),
                 "description": "", "kind": concept.get("kind"),
                 "attributes": concept.get("attributes", {}),
                 "life_area_weights": {a: concept["weights"].get(a, 0.0) for a in AREAS},
                 "evidence": evidence, "confidence": 0.9}
            )  # fmt: skip
        relationships = [
            {"type": r["type"], "from": refs[r["from"]], "to": refs[r["to"]],
             "context_event": None, "attributes": r.get("attributes", {}), "valid_from": None,
             "valid_to": r.get("valid_to"), "evidence": cite(r["evidence"]), "confidence": 0.9}
            for r in expected["relationships"]
            if r["from"] in refs and r["to"] in refs and cite(r["evidence"])
        ]  # fmt: skip
        return {"concepts": mentions, "relationships": relationships, "unsorted": []}

    return {**default_handlers(), "statements": statements, "concepts": concepts}

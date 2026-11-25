"""Default answers for the fake extraction model.

Deterministic stand-ins for model output, so the whole pipeline runs with no outside
call. They are keyword rules of thumb and say nothing about extraction quality;
quality is measured by `make eval` against the live model.
"""

import re
from typing import Any

from atlas.domain.text import normalize_name
from atlas.providers.base import ToolCall
from atlas.providers.fakes import Handler

_SENTENCE = re.compile(r"[^.!?]+[.!?]*")
_SMALL_TALK = re.compile(
    r"thank|good to see|parking|same time|next week|at time|stop there|let us meet|works\.?$",
    re.IGNORECASE,
)
_OBSERVATION = re.compile(r"sounds like|strikes me|you sound|you seem|diagnosed", re.IGNORECASE)
_FEELING_WORDS = re.compile(r"\bfelt\b|\bfeel|afraid|scared|breathe|in knots", re.IGNORECASE)
_INTENTION = re.compile(r"\bI want to\b|\bI will\b|going to\b", re.IGNORECASE)
_REFLECTION = re.compile(r"\bI think\b|\bI know\b|\bI value\b|\bI believe\b|probably|used to")

FEELINGS = {
    "dread": "dread", "relieved": "relief", "relief": "relief", "felt small": "small",
    "calms": "calm", "anxious": "anxiety", "ashamed": "shame", "angry": "anger",
    "afraid": "fear", "scared": "fear", "lonely": "loneliness",
}  # fmt: skip
BEHAVIOURS = {
    "went quiet": "going quiet", "stopped replying": "going quiet",
    "went for a run": "going for a run", "running calms": "going for a run",
    "checking": "checking repeatedly", "rewrote": "rewriting the same thing",
}  # fmt: skip
SENSATIONS = {"could not breathe": ("not being able to breathe", "chest"),
              "stomach": ("stomach in knots", "stomach")}  # fmt: skip
_RELATIVE = re.compile(r"\bmy (mum|mother|father|dad|manager|partner|sister|brother)\b", re.I)
_NAME = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,})\b")
_NOT_NAMES = frozenset(
    [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "Tomorrow",
        "The",
        "Now",
        "After",
        "When",
        "Your",
    ]
)
_WORK = re.compile(r"review|job|work|roadmap|offsite|manager|slide|dana", re.IGNORECASE)
_FAMILY = re.compile(r"mum|mother|father|dad|dinner|ruth", re.IGNORECASE)


def fake_speaker_roles(request: ToolCall) -> dict[str, Any]:
    """The voice that asks more questions is the therapist."""
    turns: dict[str, list[str]] = request.context["turns"]
    if len(turns) < 2:
        return {
            "assignments": [{"label": label, "role": "self"} for label in turns],
            "confidence": 0.99,
        }
    questions = {
        label: sum(text.count("?") for text in texts) / max(len(texts), 1)
        for label, texts in turns.items()
    }
    ranked = sorted(questions, key=lambda label: (-questions[label], label))
    therapist, owner = ranked[0], ranked[1]
    gap = questions[therapist] - questions[owner]
    assignments = [{"label": therapist, "role": "therapist"}, {"label": owner, "role": "self"}]
    assignments += [{"label": label, "role": "other"} for label in ranked[2:]]
    return {"assignments": assignments, "confidence": 0.95 if gap >= 0.3 else 0.6}


def fake_statements(request: ToolCall) -> dict[str, Any]:
    """One statement per sentence that is not small talk or a plain question."""
    statements: list[dict[str, Any]] = []
    for segment in request.context["segments"]:
        therapist = segment["role"] == "therapist"
        for match in _SENTENCE.finditer(segment["text"]):
            sentence = match.group().strip()
            words = sentence.split()
            if len(words) < 2 or _SMALL_TALK.search(sentence):
                continue
            if therapist and not _OBSERVATION.search(sentence):
                continue
            if not therapist and (
                sentence.endswith("?") or (len(words) < 3 and len(sentence) < 14)
            ):
                continue
            if therapist:
                kind = "observation"
            elif _INTENTION.search(sentence):
                kind = "intention"
            elif _FEELING_WORDS.search(sentence):
                kind = "feeling"
            elif _REFLECTION.search(sentence):
                kind = "reflection"
            else:
                kind = "report"
            statements.append(
                {"segment": segment["handle"], "quote": sentence.rstrip(".!?"), "text": sentence,
                 "kind": kind, "about_time_text": None, "about_from": None, "about_to": None,
                 "confidence": 0.7}
            )  # fmt: skip
    return {"statements": statements}


def _weights(text: str, body: bool = False) -> dict[str, float]:
    empty = {
        "love": 0.0,
        "family": 0.0,
        "friendships": 0.0,
        "work": 0.0,
        "body_health": 0.0,
        "self": 0.0,
    }
    if body:
        return {**empty, "body_health": 0.6, "self": 0.4}
    if _WORK.search(text):
        return {**empty, "work": 0.8, "self": 0.2}
    if _FAMILY.search(text):
        return {**empty, "family": 0.8, "self": 0.2}
    return {**empty, "self": 1.0}


def fake_concepts(request: ToolCall) -> dict[str, Any]:
    """Keyword-spotted concepts, each citing the statement it was spotted in."""
    shortlist: list[dict[str, Any]] = request.context["shortlist"]
    owner = next((entry["handle"] for entry in shortlist if entry["is_self"]), None)
    concepts: dict[tuple[str, str], dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []

    def existing(node_type: str, name: str) -> str | None:
        wanted = normalize_name(name)
        for entry in shortlist:
            if entry["type"] == node_type and wanted in entry["aliases"]:
                return str(entry["handle"])
        return None

    def mention(
        node_type: str, name: str, statement: dict[str, Any], basis: str = "explicit",
        kind: str | None = None, attributes: dict[str, Any] | None = None, body: bool = False,
    ) -> str:  # fmt: skip
        key = (node_type, normalize_name(name))
        if key not in concepts:
            concepts[key] = {
                "ref": f"c{len(concepts) + 1}", "existing_id": existing(node_type, name),
                "type": node_type, "name": name, "description": "", "kind": kind,
                "attributes": attributes or {}, "evidence": [], "confidence": 0.6,
                "life_area_weights": _weights(statement["text"], body),
            }  # fmt: skip
        concepts[key]["evidence"].append(
            {"statement": statement["handle"], "stance": "supports", "basis": basis}
        )
        return str(concepts[key]["ref"])

    def relate(rel: str, source: str, target: str, statement: dict[str, Any], basis: str) -> None:
        relationships.append(
            {"type": rel, "from": source, "to": target, "context_event": None, "attributes": {},
             "valid_from": None, "valid_to": None, "confidence": 0.5,
             "evidence": [{"statement": statement["handle"], "stance": "supports", "basis": basis}]}
        )  # fmt: skip

    for statement in request.context["statements"]:
        text: str = statement["text"]
        lowered = text.casefold()
        feelings = [
            mention("feeling", name, statement)
            for word, name in FEELINGS.items()
            if word in lowered
        ]
        behaviours = [
            mention("behaviour", name, statement,
                    kind="coping_tool" if "calms" in lowered and "run" in name else None)
            for word, name in BEHAVIOURS.items()
            if word in lowered
        ]  # fmt: skip
        for word, (name, area) in SENSATIONS.items():
            if word in lowered:
                mention("sensation", name, statement, attributes={"body_area": area}, body=True)
        _ = [
            mention("person", f"my {m.group(1).lower()}", statement)
            for m in _RELATIVE.finditer(text)
        ]
        _ = [
            mention("person", name, statement)
            for name in _NAME.findall(text)
            if name not in _NOT_NAMES
        ]
        if "expect to be found out" in lowered:
            mention("belief", "I will be found out", statement)
        if thinking := re.search(r"kept thinking (I .+?)[.!?]?$", text):
            belief = mention("belief", thinking.group(1), statement)
            if owner:
                relate("HOLDS", owner, belief, statement, "explicit")
        if diagnosed := re.search(r"diagnosed (?:with )?([a-z ]+?)(?: last| in |,|\.|$)", text):
            trait = mention("trait", diagnosed.group(1).strip(), statement, kind="diagnosis")
            if owner:
                relate("HAS", owner, trait, statement, "explicit")
        if wanted := re.search(r"\bI (?:want to|will) (.+?)[.!?]?$", text):
            goal = mention("goal", wanted.group(1)[:80], statement, attributes={"progress": "open"})
            if owner:
                relate("HOLDS", owner, goal, statement, "explicit")
        if valued := re.search(r"\bI value (\w+)", text):
            value = mention("value", valued.group(1), statement)
            if owner:
                relate("HOLDS", owner, value, statement, "explicit")
        if needed := re.search(r"\bI need to (.+?)[.!?]?$", text):
            need = mention("need", f"to {needed.group(1)[:80]}", statement)
            if owner:
                relate("HAS", owner, need, statement, "explicit")
        for feeling in feelings:
            for behaviour in behaviours:
                relate("LED_TO", feeling, behaviour, statement, "implied")
    return {"concepts": list(concepts.values()), "relationships": relationships, "unsorted": []}


def fake_match_decision(request: ToolCall) -> dict[str, Any]:
    """Two names are the same concept when most of their words are shared."""
    proposed = {
        word for name in request.context["proposed"] for word in normalize_name(name).split()
    }
    candidate = {word for name in request.context["candidate"] for word in name.split()}
    shared = len(proposed & candidate) / max(len(proposed | candidate), 1)
    return {"same": shared >= 0.6, "reason": "Shared words in the two names."}


def fake_empty_repair(request: ToolCall) -> dict[str, Any]:
    """The fake never repairs: failed items are settled as they stand."""
    if request.purpose == "statements_repair":
        return {"statements": []}
    return {"concepts": [], "relationships": [], "unsorted": []}


def default_handlers() -> dict[str, Handler]:
    return {
        "speaker_roles": fake_speaker_roles,
        "statements": fake_statements,
        "statements_repair": fake_empty_repair,
        "concepts": fake_concepts,
        "concepts_repair": fake_empty_repair,
        "match_decision": fake_match_decision,
    }

"""Matching new concepts against existing ones, so the same thing is not stored twice.

When unsure, the pipeline creates a new node. Two nodes for one concept can be
merged later; one node standing for two concepts corrupts every count built on it.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from atlas.domain.generated.vocabulary import NodeType
from atlas.domain.text import normalize_name


@dataclass
class Candidate:
    """An existing node a new concept might be the same as."""

    id: str
    type: str
    name: str
    description: str | None
    attributes: dict[str, Any]
    aliases: set[str]  # Normalised names, including the node's own.
    embedding: list[float] | None = None
    is_system: bool = False
    involved: set[str] = field(default_factory=set)  # For events: ids of the people involved.


@dataclass
class Proposed:
    type: str
    name: str
    description: str
    attributes: dict[str, Any]
    names: list[str]
    involved: set[str] = field(default_factory=set)


@dataclass
class Decision:
    """One row of the decisions log."""

    proposed: dict[str, Any]
    candidate_ids: list[str]
    decision: str
    matched_node_id: str | None
    reason: str | None = None
    similarity: float | None = None


# Asks the model whether two entries are the same concept: (same, reason).
Decide = Callable[[Proposed, Candidate], tuple[bool, str]]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def events_agree(proposed: Proposed, candidate: Candidate) -> bool:
    """Events match only when the date and the people involved agree."""
    when_a, when_b = proposed.attributes.get("when"), candidate.attributes.get("when")
    if not when_a or not when_b or str(when_a) != str(when_b):
        return False
    return not (proposed.involved and candidate.involved) or bool(
        proposed.involved & candidate.involved
    )


def resolve(
    proposed: Proposed,
    candidates: Sequence[Candidate],
    vector: Sequence[float] | None,
    *,
    accept: float,
    review: float,
    decide: Decide,
    nearest: int = 5,
) -> Decision:
    """Decide whether `proposed` is an existing node, in the plan's three steps."""
    summary = {"type": proposed.type, "name": proposed.name}
    same_type = [c for c in candidates if c.type == proposed.type]
    is_event = proposed.type == NodeType.EVENT.value
    is_person = proposed.type == NodeType.PERSON.value

    # 1. An exact match on the normalised name or an alias, within the same type.
    names = {normalize_name(name) for name in proposed.names if name.strip()}
    for candidate in same_type:
        if names & candidate.aliases and (not is_event or events_agree(proposed, candidate)):
            return Decision(summary, [candidate.id], "exact_name", candidate.id)

    # 2. Otherwise the nearest existing nodes of that type, by embedding similarity.
    scored = sorted(
        (
            (cosine(vector, c.embedding), c)
            for c in same_type
            if vector is not None and c.embedding is not None and not c.is_system
        ),
        key=lambda pair: (-pair[0], pair[1].id),
    )[:nearest]
    listed = [candidate.id for _, candidate in scored]
    if not scored:
        return Decision(summary, [], "new", None)
    best_score, best = scored[0]

    if is_event and not events_agree(proposed, best):
        return Decision(summary, listed, "new", None, "event_date_or_people_differ", best_score)
    if best_score < review:
        return Decision(summary, listed, "new", None, None, best_score)
    # 3. At or above the accept threshold it is the same concept, except for people,
    #    who never match on similarity alone. In between, one model call decides.
    if best_score >= accept and not is_person:
        return Decision(summary, listed, "similar", best.id, None, best_score)
    same, reason = decide(proposed, best)
    if same:
        return Decision(summary, listed, "model_same", best.id, reason, best_score)
    return Decision(summary, listed, "model_different", None, reason, best_score)

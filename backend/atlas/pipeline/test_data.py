"""Test data: concepts and relationships uploaded as JSON, with no model involved.

The blob lists concepts by type (`person`, `feeling`, ...) and, optionally,
relationships between them. It becomes an ordinary source: every item is given
statements and evidence, so it obeys the same rules as extracted data. Each item is
traceable to a quote, computed fields come from evidence, and retracting the source
removes everything it added.

    {
      "person":  [{"name": "Dana", "relationship_to_owner": "manager", "life_area": "work"}],
      "feeling": ["dread", {"name": "shame", "status": "hypothesis", "count": 3}],
      "relationships": [{"type": "ABOUT", "from": "dread", "to": "Dana"}]
    }
"""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import delete

from atlas.db.ids import new_id
from atlas.db.models import Segment, Speaker
from atlas.domain.generated.vocabulary import (
    CORE_TYPES,
    ENDPOINTS,
    KIND_REQUIRED,
    NODE_ATTRIBUTE_MODELS,
    NODE_KINDS,
    RELATIONSHIP_PHASE,
    EvidenceBasis,
    LifeArea,
    NodeType,
    RelationshipType,
    SpeakerRole,
    StatementKind,
    Status,
)
from atlas.domain.rules import DIAGNOSIS_KIND
from atlas.domain.text import collapse_whitespace, normalize_name
from atlas.pipeline.commit import write_proposal
from atlas.pipeline.concepts import OWNER_NAMES, load_existing
from atlas.pipeline.ingest import original_media
from atlas.pipeline.runner import StageContext
from atlas.pipeline.speakers import apply_roles
from atlas.pipeline.stages import Outcome, StageError

MAX_ITEMS = 2000
MAX_COUNT = 50
TYPE_KEYS = tuple(t.value for t in NodeType if t in CORE_TYPES)
# Who says it, and how directly, for each status an item can ask for.
VOICE: dict[Status, tuple[SpeakerRole, EvidenceBasis]] = {
    Status.STATED: (SpeakerRole.SELF, EvidenceBasis.EXPLICIT),
    Status.OBSERVED: (SpeakerRole.THERAPIST, EvidenceBasis.EXPLICIT),
    Status.HYPOTHESIS: (SpeakerRole.SELF, EvidenceBasis.IMPLIED),
}


class BlobError(ValueError):
    """The blob is not valid test data. The message names the place, never the content."""


class Item(BaseModel):
    """One concept. Any other field is a type-specific attribute, such as `body_area`."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    kind: str | None = None
    status: Status = Status.STATED
    life_area: LifeArea | None = None
    # How many statements back it; more evidence draws a bigger landmark.
    count: int = Field(default=1, ge=1, le=MAX_COUNT)
    quotes: list[str] = Field(default_factory=list, max_length=MAX_COUNT)
    aliases: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def from_name(cls, value: object) -> object:
        return {"name": value} if isinstance(value, str) else value


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: RelationshipType
    source: str = Field(alias="from", min_length=1)
    target: str = Field(alias="to", min_length=1)
    status: Status = Status.STATED
    quotes: list[str] = Field(default_factory=list, max_length=MAX_COUNT)


class DataBlob(BaseModel):
    """Concepts by type, as arrays, plus optional relationships."""

    model_config = ConfigDict(extra="forbid")

    person: list[Item] = Field(default_factory=list)
    group: list[Item] = Field(default_factory=list)
    situation: list[Item] = Field(default_factory=list)
    event: list[Item] = Field(default_factory=list)
    feeling: list[Item] = Field(default_factory=list)
    sensation: list[Item] = Field(default_factory=list)
    belief: list[Item] = Field(default_factory=list)
    behaviour: list[Item] = Field(default_factory=list)
    need: list[Item] = Field(default_factory=list)
    value: list[Item] = Field(default_factory=list)
    goal: list[Item] = Field(default_factory=list)
    trait: list[Item] = Field(default_factory=list)
    role: list[Item] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    def items(self) -> list[tuple[str, Item]]:
        return [(key, item) for key in TYPE_KEYS for item in getattr(self, key)]


def _where(error: Any) -> str:
    return ".".join(str(part) for part in error["loc"]) or "the blob"


def _check_item(node_type: str, index: int, item: Item) -> dict[str, Any]:
    """Vocabulary checks for one concept. Returns its type-specific attributes."""
    where = f"{node_type}.{index}"
    kinds = NODE_KINDS.get(NodeType(node_type), frozenset())
    if item.kind is not None and item.kind not in kinds:
        allowed = ", ".join(sorted(kinds)) or "none"
        raise BlobError(f"{where}.kind is not allowed for {node_type} (allowed: {allowed})")
    if item.kind is None and NodeType(node_type) in KIND_REQUIRED:
        raise BlobError(f"{where}.kind is required (one of: {', '.join(sorted(kinds))})")
    if item.kind == DIAGNOSIS_KIND and item.status is Status.HYPOTHESIS:
        # The same rule the pipeline enforces: a diagnosis must have been stated.
        raise BlobError(f"{where}: a diagnosis cannot have status hypothesis")
    extra = {k: v for k, v in (item.model_extra or {}).items() if v not in (None, "")}
    extra.pop("is_self", None)
    try:
        model = NODE_ATTRIBUTE_MODELS[NodeType(node_type)]
        return dict(model(**extra).model_dump(mode="json", exclude_none=True))
    except ValidationError as error:
        fields = ", ".join(sorted({_where(e) for e in error.errors()}))
        raise BlobError(f"{where}: unknown or invalid fields: {fields}") from error


def parse_test_data(raw: object) -> DataBlob:
    """Validate a blob against the vocabulary. Raises BlobError naming the place at fault."""
    if isinstance(raw, dict):
        # Be forgiving about plural keys: "feelings" for "feeling", "people" for "person".
        plural = {f"{key}s": key for key in TYPE_KEYS} | {"people": "person"}
        raw = {plural.get(key, key): value for key, value in raw.items()}
    try:
        data = DataBlob.model_validate(raw)
    except ValidationError as error:
        places = sorted({_where(e) for e in error.errors()})[:8]
        raise BlobError(f"invalid test data at: {', '.join(places)}") from error

    items = data.items()
    if not items:
        raise BlobError(
            "the blob has no concepts; add at least one array such as person or feeling"
        )
    if len(items) > MAX_ITEMS:
        raise BlobError(f"too many concepts (limit {MAX_ITEMS})")
    types_by_name: dict[str, set[str]] = {}
    seen: set[tuple[str, str]] = set()
    counters: dict[str, int] = {}
    for node_type, item in items:
        index = counters.get(node_type, 0)
        counters[node_type] = index + 1
        _check_item(node_type, index, item)
        key = (node_type, normalize_name(item.name))
        if key in seen:
            raise BlobError(f"{node_type}.{index}: the same name appears twice in {node_type}")
        seen.add(key)
        for name in (item.name, *item.aliases):
            types_by_name.setdefault(normalize_name(name), set()).add(node_type)

    for index, relationship in enumerate(data.relationships):
        where = f"relationships.{index}"
        if RELATIONSHIP_PHASE[relationship.type] != 1:
            raise BlobError(f"{where}.type is written only by analysis jobs")
        allowed_from, allowed_to = ENDPOINTS[relationship.type]
        for side, name, allowed in (
            ("from", relationship.source, allowed_from),
            ("to", relationship.target, allowed_to),
        ):
            normal = normalize_name(name)
            found = types_by_name.get(normal, set()) | (
                {"person"} if normal in OWNER_NAMES else set()
            )
            if not found:
                raise BlobError(f"{where}.{side} names a concept that is not in the blob")
            if not found & {t.value for t in allowed}:
                raise BlobError(
                    f"{where}.{side} has a type {relationship.type.value} does not allow"
                )
    return data


def _quotes(given: list[str], count: int, fallback: str) -> list[str]:
    quotes = [collapse_whitespace(q) for q in given if q.strip()]
    while len(quotes) < count:
        number = f" ({len(quotes) + 1})" if count > 1 or quotes else ""
        quotes.append(f"{fallback}{number}")
    return quotes


def import_stage(ctx: StageContext) -> Outcome:
    """Turn the stored blob into statements, concepts, relationships and evidence."""
    media = original_media(ctx)
    try:
        data = parse_test_data(json.loads(ctx.providers.blobs.get(media.storage_key)))
    except (ValueError, UnicodeDecodeError) as error:
        raise StageError("test_data_invalid") from error

    session = ctx.session
    session.execute(delete(Speaker).where(Speaker.source_id == ctx.source.id))
    speakers = {
        role: Speaker(
            user_id=ctx.user_id, source_id=ctx.source.id, provider_label=f"speaker_{role.value}"
        )
        for role in (SpeakerRole.SELF, SpeakerRole.THERAPIST)
    }
    session.add_all(speakers.values())
    session.flush()
    apply_roles(
        session,
        ctx.user_id,
        list(speakers.values()),
        {f"speaker_{role.value}": role for role in speakers},
        "test_data",
        1.0,
    )

    drafts: list[dict[str, Any]] = []
    offset = 0

    def say(text: str, status: Status) -> dict[str, Any]:
        """One segment holding one statement, in the voice the status calls for."""
        nonlocal offset
        role, basis = VOICE[status]
        segment = Segment(
            user_id=ctx.user_id,
            source_id=ctx.source.id,
            speaker_id=speakers[role].id,
            idx=len(drafts),
            start_char=offset,
            end_char=offset + len(text),
            text=text,
        )
        session.add(segment)
        session.flush()
        offset += len(text) + 1
        kind = StatementKind.OBSERVATION if role is SpeakerRole.THERAPIST else StatementKind.REPORT
        draft = {
            "id": str(new_id()),
            "segment_id": str(segment.id),
            "segment_idx": segment.idx,
            "speaker_role": role.value,
            "quote": text,
            "quote_start": 0,
            "quote_end": len(text),
            "text": text,
            "kind": kind.value,
            "about_time_text": None,
            "about_from": None,
            "about_to": None,
            "confidence": 1.0,
        }
        drafts.append(draft)
        return {
            "statement_id": draft["id"],
            "stance": "supports",
            "basis": basis.value,
            "confidence": 1.0,
        }

    # Match by exact name or alias against the atlas, so test data can extend what is there.
    existing = load_existing(session)
    owner = next((node.id for node in existing.values() if node.attributes.get("is_self")), None)

    def existing_id(node_type: str, names: list[str]) -> str | None:
        wanted = {normalize_name(name) for name in names}
        if node_type == NodeType.PERSON.value and wanted & OWNER_NAMES:
            return owner
        for node in existing.values():
            if node.type == node_type and wanted & node.aliases:
                return node.id
        return None

    by_name: dict[str, list[tuple[str, str]]] = {}  # normalised name -> [(type, node id)]
    nodes: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    for node_type, item in data.items():
        index = counters.get(node_type, 0)
        counters[node_type] = index + 1
        names = [item.name, *item.aliases]
        matched = existing_id(node_type, names)
        node_id = matched or str(new_id())
        weights = {(item.life_area or LifeArea.SELF).value: 1.0}
        fallback = f'Test data: {node_type} "{item.name}"'
        evidence = [
            {**say(quote, item.status), "life_area_weights": weights}
            for quote in _quotes(item.quotes, item.count, fallback)
        ]
        nodes.append(
            {
                "node_id": node_id,
                "is_new": matched is None,
                "type": node_type,
                "name": item.name,
                "description": item.description,
                "kind": item.kind,
                "attributes": _check_item(node_type, index, item),
                "names": names,
                "evidence": evidence,
            }
        )
        for name in names:
            by_name.setdefault(normalize_name(name), []).append((node_type, node_id))

    def resolve(name: str, allowed: frozenset[NodeType]) -> str:
        normal = normalize_name(name)
        for node_type, node_id in by_name.get(normal, []):
            if NodeType(node_type) in allowed:
                return node_id
        if normal in OWNER_NAMES and owner is not None:
            return owner
        raise StageError("test_data_invalid")

    edges: list[dict[str, Any]] = []
    for relationship in data.relationships:
        allowed_from, allowed_to = ENDPOINTS[relationship.type]
        source = resolve(relationship.source, allowed_from)
        target = resolve(relationship.target, allowed_to)
        verb = relationship.type.value.replace("_", " ").lower()
        fallback = f'Test data: "{relationship.source}" {verb} "{relationship.target}"'
        edges.append(
            {
                "type": relationship.type.value,
                "from_node_id": source,
                "to_node_id": target,
                "context_event_id": None,
                "attributes": {},
                "valid_from": None,
                "valid_to": None,
                "evidence": [
                    say(q, relationship.status) for q in _quotes(relationship.quotes, 1, fallback)
                ],
            }
        )
    if owner is not None and owner not in {node["node_id"] for node in nodes}:
        # The owner can be an endpoint without being listed in the blob.
        used = {edge["from_node_id"] for edge in edges} | {edge["to_node_id"] for edge in edges}
        if owner in used:
            nodes.append(
                {
                    "node_id": owner,
                    "is_new": False,
                    "type": "person",
                    "name": "Me",
                    "description": "",
                    "kind": None,
                    "attributes": {},
                    "names": [],
                    "evidence": [],
                }
            )

    proposal = {"nodes": nodes, "edges": edges, "decisions": []}
    # Statements, concepts and evidence all carry this run's id, so retracting it removes them.
    return write_proposal(ctx, ctx.run, ctx.run, drafts, proposal)

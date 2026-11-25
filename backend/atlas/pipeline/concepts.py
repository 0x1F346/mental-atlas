"""Pass B: concepts and relationships, validated in code and matched to existing concepts.

Nothing is written to the atlas here. The stage produces a proposal, kept on the
run, that the commit stage inserts in one transaction.
"""

import datetime
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.ids import new_id
from atlas.db.models import Edge, Node, NodeAlias, Run
from atlas.domain.generated.vocabulary import (
    CORE_TYPES,
    EDGE_ATTRIBUTE_MODELS,
    ENDPOINTS,
    KIND_REQUIRED,
    NODE_ATTRIBUTE_MODELS,
    NODE_KINDS,
    RELATIONSHIP_PHASE,
    EvidenceBasis,
    EvidenceStance,
    LifeArea,
    NodeType,
    RecordState,
    RelationshipType,
    SpeakerRole,
)
from atlas.domain.rules import DIAGNOSIS_KIND
from atlas.domain.text import collapse_whitespace, normalize_name
from atlas.pipeline.matching import Candidate, Decision, Proposed, cosine, resolve
from atlas.pipeline.prompts import load_prompt, prompt_version
from atlas.pipeline.runner import StageContext
from atlas.pipeline.stages import Next, Outcome, Stage, StageError
from atlas.pipeline.statements import (
    ROLE_LABELS,
    StatementDraft,
    add_usage,
    extraction_schema,
    load_segments,
    render_transcript,
)
from atlas.pipeline.windows import windows
from atlas.providers.base import TextBlock, ToolCall

PROMPT = "concepts"
PROMPT_VERSION = 1
MATCH_PROMPT = "match"
MATCH_PROMPT_VERSION = 1
SHORTLIST_SIZE = 20
MAX_NAME_CHARS = 200
OWNER_NAMES = frozenset({"me", "i", "myself", "the owner", "owner", "the client", "client", "self"})
EXPLICIT_STEM = 4

MATCH_TOOL: dict[str, Any] = {
    "name": "decide_same_concept",
    "description": "Say whether two atlas entries are the same concept.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["same", "reason"],
        "properties": {
            "same": {"type": "boolean"},
            "reason": {"type": "string", "description": "One short sentence."},
        },
    },
}


@dataclass
class EvidenceDraft:
    statement_id: str
    stance: str
    basis: str
    confidence: float | None = None
    life_area_weights: dict[str, float] | None = None


@dataclass
class Pending:
    """A concept proposed for this source, before it is matched to the atlas."""

    key: str
    type: str
    name: str
    description: str
    kind: str | None
    attributes: dict[str, Any]
    node_id: str | None = None  # Set when it is an existing node.
    names: list[str] = field(default_factory=list)
    evidence: list[EvidenceDraft] = field(default_factory=list)


@dataclass
class EdgeDraft:
    type: str
    from_key: str
    to_key: str
    context_key: str | None
    attributes: dict[str, Any]
    valid_from: str | None
    valid_to: str | None
    evidence: list[EvidenceDraft]


@dataclass
class Working:
    """State carried across the windows of one source."""

    statements: dict[str, StatementDraft]  # By handle (T1, T2, ...).
    existing: dict[str, Candidate]  # By node id.
    handles: dict[str, str] = field(default_factory=dict)  # N1 -> node id.
    pending: dict[str, Pending] = field(default_factory=dict)  # By key (P1, or node:<id>).
    by_name: dict[tuple[str, str], str] = field(default_factory=dict)  # (type, name) -> key.
    edges: list[EdgeDraft] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)
    to_unsorted: int = 0
    repaired: int = 0

    def drop(self, code: str) -> None:
        self.dropped[code] = self.dropped.get(code, 0) + 1

    def handle_for(self, node_id: str) -> str:
        for handle, known in self.handles.items():
            if known == node_id:
                return handle
        handle = f"N{len(self.handles) + 1}"
        self.handles[handle] = node_id
        return handle

    def existing_pending(self, node_id: str) -> Pending:
        key = f"node:{node_id}"
        if key not in self.pending:
            node = self.existing[node_id]
            self.pending[key] = Pending(
                key, node.type, node.name, node.description or "", None, {}, node_id=node_id
            )
        return self.pending[key]


# --- Loading ----------------------------------------------------------------


def _vector(value: object) -> list[float] | None:
    if value is None:
        return None
    return [float(x) for x in value]  # type: ignore[attr-defined]


def load_existing(session: Session) -> dict[str, Candidate]:
    """Every node of the user's atlas a new mention could be the same as."""
    types = [t.value for t in CORE_TYPES]
    nodes = [
        node
        for node in session.scalars(
            select(Node).where(Node.type.in_(types), Node.state != RecordState.MERGED.value)
        )
        # A retracted diagnosis must not come back by a later mention attaching to it.
        if not (node.state == RecordState.RETRACTED.value and node.kind == DIAGNOSIS_KIND)
    ]
    aliases: dict[str, set[str]] = {}
    for node_id, alias in session.execute(select(NodeAlias.node_id, NodeAlias.normalized_alias)):
        aliases.setdefault(str(node_id), set()).add(alias)
    involved: dict[str, set[str]] = {}
    for from_id, to_id in session.execute(
        select(Edge.from_node_id, Edge.to_node_id).where(
            Edge.type == RelationshipType.INVOLVES.value, Edge.state == RecordState.ACTIVE.value
        )
    ):
        involved.setdefault(str(from_id), set()).add(str(to_id))
    return {
        str(node.id): Candidate(
            id=str(node.id),
            type=node.type,
            name=node.name,
            description=node.description,
            attributes=dict(node.attributes),
            aliases=aliases.get(str(node.id), set()) | {node.normalized_name},
            embedding=_vector(node.embedding),
            is_system=node.is_system,
            involved=involved.get(str(node.id), set()),
        )
        for node in nodes
    }


def latest_run(session: Session, source_id: object, stage: Stage) -> Run:
    run = session.scalars(
        select(Run)
        .where(Run.source_id == source_id, Run.kind == stage.value, Run.status == "succeeded")
        .order_by(Run.started_at.desc(), Run.id.desc())
    ).first()
    if run is None or run.raw_output is None:
        raise StageError(f"{stage.value}_output_missing")
    return run


# --- Validation -------------------------------------------------------------


def _clean_weights(value: object) -> dict[str, float]:
    areas = {area.value for area in LifeArea}
    weights: dict[str, float] = {}
    if isinstance(value, dict):
        for key, weight in value.items():
            numeric = isinstance(weight, int | float) and not isinstance(weight, bool)
            if key in areas and numeric and weight > 0:
                weights[key] = float(weight)
    total = sum(weights.values())
    if total <= 0:
        return {LifeArea.SELF.value: 1.0}
    return {key: round(weight / total, 4) for key, weight in weights.items()}


def _clean_evidence(
    value: object, window: dict[str, StatementDraft], weights: dict[str, float] | None
) -> list[EvidenceDraft]:
    """Keep the citations that point at a statement in this window."""
    kept: dict[tuple[str, str], EvidenceDraft] = {}
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        statement = window.get(str(item.get("statement", "")).strip().strip("[]"))
        try:
            stance = EvidenceStance(str(item.get("stance")))
            basis = EvidenceBasis(str(item.get("basis")))
        except ValueError:
            continue
        if statement is None:
            continue
        kept.setdefault(
            (statement.id, stance.value),
            EvidenceDraft(statement.id, stance.value, basis.value, statement.confidence, weights),
        )
    return list(kept.values())


def _clean_attributes(model: Any, value: object, drop: tuple[str, ...] = ()) -> dict[str, Any]:
    """Keep known, non-empty fields and check them against the generated model."""
    raw = value if isinstance(value, dict) else {}
    known = {
        key: item
        for key, item in raw.items()
        if key in model.model_fields and key not in drop and item not in (None, "")
    }
    return dict(model(**known).model_dump(mode="json", exclude_none=True))


_WORD = re.compile(r"[a-z0-9']+")


def _names_it(name: str, statement: StatementDraft) -> bool:
    """Whether the speaker's own words (the verbatim quote) contain a word of the name.

    Only the quote counts: the restated text is written by the model. Words match by
    their opening letters, so "relief" is named by "relieved" but "joy" not by "enjoy".
    """
    said = _WORD.findall(statement.quote.casefold())
    stems = [word[:EXPLICIT_STEM] for word in normalize_name(name).split() if len(word) > 2]
    return any(word.startswith(stem) for stem in stems for word in said)


def validate_concept(
    item: object, window: dict[str, StatementDraft], by_id: dict[str, StatementDraft]
) -> Pending | str:
    """Check one concept mention against the vocabulary. Returns it, or an error code."""
    if not isinstance(item, dict):
        return "malformed"
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        return "malformed"
    name = collapse_whitespace(name)[:MAX_NAME_CHARS]
    description = item.get("description")
    description = collapse_whitespace(description) if isinstance(description, str) else ""
    weights = _clean_weights(item.get("life_area_weights"))
    evidence = _clean_evidence(item.get("evidence"), window, weights)
    if not evidence:
        return "no_valid_evidence"
    try:
        node_type = NodeType(str(item.get("type")))
    except ValueError:
        return "unknown_type"
    if node_type not in CORE_TYPES:
        return "unknown_type"

    kind = item.get("kind")
    kind = kind.strip() if isinstance(kind, str) and kind.strip() not in ("", "none") else None
    allowed = NODE_KINDS.get(node_type, frozenset())
    if kind is not None and kind not in allowed:
        return "kind_not_allowed"
    if kind is None and node_type in KIND_REQUIRED:
        return "kind_required"
    # The AI never creates a diagnosis: it needs a statement in which the owner or the
    # therapist names it. A feeling is explicit only if the speaker actually named it.
    for link in evidence:
        named = _names_it(name, by_id[link.statement_id])
        if (
            node_type is NodeType.FEELING
            and link.basis == EvidenceBasis.EXPLICIT.value
            and not named
        ):
            link.basis = EvidenceBasis.IMPLIED.value
    if node_type is NodeType.TRAIT and kind == DIAGNOSIS_KIND:
        stated = any(
            link.basis == EvidenceBasis.EXPLICIT.value
            and link.stance == EvidenceStance.SUPPORTS.value
            and by_id[link.statement_id].speaker_role
            in (SpeakerRole.SELF.value, SpeakerRole.THERAPIST.value)
            and _names_it(name, by_id[link.statement_id])
            for link in evidence
        )
        if not stated:
            return "diagnosis_without_explicit_statement"
    try:
        attributes = _clean_attributes(
            NODE_ATTRIBUTE_MODELS[node_type], item.get("attributes"), drop=("is_self",)
        )
    except ValidationError:
        return "invalid_attributes"

    also = item.get("also_called")
    names = [name] + [
        collapse_whitespace(other)[:MAX_NAME_CHARS]
        for other in (also if isinstance(also, list) else [])
        if isinstance(other, str) and other.strip()
    ]
    return Pending("", node_type.value, name, description, kind, attributes, None, names, evidence)


def validate_unsorted(item: object, window: dict[str, StatementDraft]) -> Pending | str:
    if not isinstance(item, dict):
        return "malformed"
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        return "malformed"
    evidence = _clean_evidence(item.get("evidence"), window, None)
    if not evidence:
        return "no_valid_evidence"
    attributes = {
        "suggested_type": collapse_whitespace(str(item.get("suggested_type") or ""))[:80],
        "reason": collapse_whitespace(str(item.get("reason") or ""))[:400],
    }
    description = collapse_whitespace(str(item.get("description") or ""))
    name = collapse_whitespace(name)[:MAX_NAME_CHARS]
    return Pending(
        "", NodeType.UNSORTED.value, name, description, None, attributes, None, [name], evidence
    )


def _iso_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def validate_relationship(
    item: object,
    window: dict[str, StatementDraft],
    targets: dict[str, tuple[str, str]],
) -> EdgeDraft | str:
    """Check one relationship. `targets` maps a ref or handle to (pending key, node type)."""
    if not isinstance(item, dict):
        return "malformed"
    try:
        rel = RelationshipType(str(item.get("type")))
    except ValueError:
        return "unknown_relationship"
    if RELATIONSHIP_PHASE[rel] != 1:
        return "unknown_relationship"
    source = targets.get(str(item.get("from", "")).strip().strip("[]"))
    target = targets.get(str(item.get("to", "")).strip().strip("[]"))
    if source is None or target is None:
        return "unknown_endpoint"
    if source[0] == target[0]:
        return "self_relationship"
    allowed_from, allowed_to = ENDPOINTS[rel]
    if source[1] not in allowed_from or target[1] not in allowed_to:
        return "endpoints_not_allowed"
    evidence = _clean_evidence(item.get("evidence"), window, None)
    if not evidence:
        return "no_valid_evidence"
    context = targets.get(str(item.get("context_event") or "").strip().strip("[]"))
    context_key = context[0] if context and context[1] == NodeType.EVENT.value else None
    try:
        attributes = _clean_attributes(EDGE_ATTRIBUTE_MODELS[rel], item.get("attributes"))
    except ValidationError:
        attributes = {}
    return EdgeDraft(
        rel.value,
        source[0],
        target[0],
        context_key,
        attributes,
        _iso_date(item.get("valid_from")),
        _iso_date(item.get("valid_to")),
        evidence,
    )


# --- Folding one window's output into the working state ---------------------


def _resolve_existing(work: Working, item: dict[str, Any], node_type: str) -> str | None:
    """The pending key a mention's `existing_id` names, when it is valid and the type agrees."""
    handle = str(item.get("existing_id") or "").strip().strip("[]")
    if handle in work.handles:
        node = work.existing[work.handles[handle]]
        return work.existing_pending(node.id).key if node.type == node_type else None
    if handle in work.pending and work.pending[handle].type == node_type:
        return handle
    return None


def _self_key(work: Working) -> str | None:
    for node in work.existing.values():
        if node.attributes.get("is_self"):
            return work.existing_pending(node.id).key
    return None


def add_concept(work: Working, mention: Pending, item: dict[str, Any]) -> str:
    """Merge a validated mention into the pending set. Returns its key."""
    key: str | None = _resolve_existing(work, item, mention.type)
    is_owner = normalize_name(mention.name) in OWNER_NAMES
    if key is None and mention.type == NodeType.PERSON.value and is_owner:
        key = _self_key(work)
    name_key = (mention.type, normalize_name(mention.name))
    if key is None:
        key = work.by_name.get(name_key)
    if key is None:
        key = f"P{sum(1 for k in work.pending if k.startswith('P')) + 1}"
        mention.key = key
        work.pending[key] = mention
        work.by_name[name_key] = key
        return key
    target = work.pending[key]
    work.by_name.setdefault(name_key, key)
    if normalize_name(mention.name) not in {normalize_name(n) for n in target.names}:
        target.names.append(mention.name)
    if target.node_id is None:
        target.kind = target.kind or mention.kind
        target.attributes = {**mention.attributes, **target.attributes}
        target.description = target.description or mention.description
    seen = {(e.statement_id, e.stance) for e in target.evidence}
    target.evidence += [e for e in mention.evidence if (e.statement_id, e.stance) not in seen]
    return key


def fold(
    work: Working,
    data: dict[str, Any],
    window: dict[str, StatementDraft],
    refs: dict[str, tuple[str, str]],
    final: bool,
) -> list[dict[str, Any]]:
    """Validate one model answer and merge what passes. Returns the items that failed.

    On the final attempt a failed concept that is well-formed goes to unsorted with
    the reason, and anything else is dropped and counted.
    """
    by_id = {statement.id: statement for statement in work.statements.values()}
    failed: list[dict[str, Any]] = []

    def fail(section: str, item: object, code: str) -> None:
        if not final and code != "malformed":
            failed.append({"in": section, "item": item, "error": code})
            return
        vocabulary_misfit = code in (
            "unknown_type",
            "kind_not_allowed",
            "kind_required",
            "invalid_attributes",
        )
        is_diagnosis = isinstance(item, dict) and item.get("kind") == DIAGNOSIS_KIND
        if (
            section == "concepts"
            and vocabulary_misfit
            and isinstance(item, dict)
            and not is_diagnosis
        ):
            salvaged = validate_unsorted(
                {
                    **item,
                    "suggested_type": item.get("type"),
                    "reason": f"Failed validation: {code}",
                },
                window,
            )
            if isinstance(salvaged, Pending):
                add_concept(work, salvaged, {})
                work.to_unsorted += 1
                return
        work.drop(code)

    concepts = data.get("concepts")
    for item in concepts if isinstance(concepts, list) else []:
        checked = validate_concept(item, window, by_id)
        if isinstance(checked, str):
            fail("concepts", item, checked)
            continue
        key = add_concept(work, checked, item)
        ref = str(item.get("ref") or "").strip()
        if ref:
            refs[ref] = (key, work.pending[key].type)

    unsorted = data.get("unsorted")
    for item in unsorted if isinstance(unsorted, list) else []:
        checked = validate_unsorted(item, window)
        if isinstance(checked, str):
            fail("unsorted", item, checked)
        else:
            add_concept(work, checked, {})

    targets = dict(refs)
    for handle, node_id in work.handles.items():
        targets.setdefault(handle, (f"node:{node_id}", work.existing[node_id].type))
    for key, pending in work.pending.items():
        if key.startswith("P"):
            targets.setdefault(key, (key, pending.type))
    relationships = data.get("relationships")
    for item in relationships if isinstance(relationships, list) else []:
        edge = validate_relationship(item, window, targets)
        if isinstance(edge, str):
            fail("relationships", item, edge)
            continue
        for end in (edge.from_key, edge.to_key, edge.context_key):
            if end and end.startswith("node:"):
                work.existing_pending(end.removeprefix("node:"))
        work.edges.append(edge)
    return failed


# --- Shortlist --------------------------------------------------------------


def shortlist(
    work: Working, vectors: dict[str, list[float]], window: dict[str, StatementDraft]
) -> list[str]:
    """Existing concepts that might match: nearest by embedding, plus every person and group."""
    always = [
        node.id
        for node in work.existing.values()
        if node.type in (NodeType.PERSON.value, NodeType.GROUP.value)
    ]
    window_vectors = [vectors[s.id] for s in window.values() if s.id in vectors]
    scored = sorted(
        (
            (max((cosine(v, node.embedding) for v in window_vectors), default=0.0), node.id)
            for node in work.existing.values()
            if node.embedding is not None and node.id not in always
        ),
        key=lambda pair: (-pair[0], pair[1]),
    )
    return always + [node_id for _, node_id in scored[:SHORTLIST_SIZE]]


def render_window(
    work: Working, window: dict[str, StatementDraft], listed: list[str]
) -> tuple[str, dict[str, Any]]:
    lines = ["Statements in this window:"]
    for handle, s in window.items():
        about = f" (about: {s.about_time_text})" if s.about_time_text else ""
        lines.append(
            f"[{handle}] {ROLE_LABELS[s.speaker_role]}, {s.kind}{about}: {s.text}"
            f' | quote: "{s.quote}"'
        )
    lines += [
        "",
        "Shortlist of concepts that already exist or were proposed earlier for this source:",
    ]
    entries: list[dict[str, Any]] = []
    for node_id in listed:
        node = work.existing[node_id]
        handle = work.handle_for(node_id)
        owner = " (this is the owner)" if node.attributes.get("is_self") else ""
        also = sorted(node.aliases - {normalize_name(node.name)})
        known = f" Also known as: {', '.join(also)}." if also else ""
        lines.append(
            f"[{handle}] {node.type}: {node.name}{owner}. {node.description or ''}{known}".rstrip()
        )
        entries.append(
            {
                "handle": handle,
                "type": node.type,
                "name": node.name,
                "aliases": sorted(node.aliases),
                "is_self": bool(node.attributes.get("is_self")),
            }
        )
    for key, pending in work.pending.items():
        if key.startswith("P") and pending.type != NodeType.UNSORTED.value:
            lines.append(f"[{key}] {pending.type}: {pending.name}. {pending.description}".rstrip())
            entries.append(
                {
                    "handle": key,
                    "type": pending.type,
                    "name": pending.name,
                    "aliases": [normalize_name(n) for n in pending.names],
                    "is_self": False,
                }
            )
    if len(lines) == len(window) + 3:
        lines.append("(none yet)")
    lines += ["", "Record the concepts and relationships these statements support."]
    context = {
        "statements": [
            {
                "handle": handle,
                "role": s.speaker_role,
                "kind": s.kind,
                "text": s.text,
                "quote": s.quote,
            }
            for handle, s in window.items()
        ],
        "shortlist": entries,
    }
    return "\n".join(lines), context


# --- The stage --------------------------------------------------------------


def concepts_stage(ctx: StageContext) -> Outcome:
    statements_run = latest_run(ctx.session, ctx.source.id, Stage.STATEMENTS)
    assert statements_run.raw_output is not None
    drafts = [StatementDraft(**item) for item in statements_run.raw_output["statements"]]
    segments = load_segments(ctx.session, ctx.source.id)
    work = Working(
        statements={f"T{i + 1}": draft for i, draft in enumerate(drafts)},
        existing=load_existing(ctx.session),
    )
    embedder = ctx.providers.embedder
    vectors = dict(
        zip((d.id for d in drafts), embedder.embed([d.text for d in drafts]), strict=True)
    )

    system = [
        TextBlock(
            load_prompt(PROMPT, PROMPT_VERSION).replace("{vocabulary}", load_vocabulary_block())
        ),
        TextBlock(render_transcript(segments, ctx.source.occurred_at), cache=True),
    ]
    tool = extraction_schema()["record_concepts"]
    usage: dict[str, int] = {}
    raw_calls: list[dict[str, Any]] = []
    model = ctx.settings.extraction_model
    done: set[str] = set()

    for span in windows(len(segments)):
        window = {
            handle: s
            for handle, s in work.statements.items()
            if span.start <= s.segment_idx < span.end and handle not in done
        }
        if not window:
            continue
        done |= set(window)
        ask, context = render_window(work, window, shortlist(work, vectors, window))
        result = ctx.providers.extraction.call(
            ToolCall(model, system, [TextBlock(ask)], tool, purpose="concepts", context=context)
        )
        add_usage(usage, result.usage)
        model = result.model
        raw_calls.append({"window": [span.start, span.end], "output": result.data})
        refs: dict[str, tuple[str, str]] = {}
        failed = fold(work, result.data, window, refs, final=False)
        if failed:
            # One repair attempt with the errors attached.
            repair = ctx.providers.extraction.call(
                ToolCall(
                    model,
                    system,
                    [
                        TextBlock(ask),
                        TextBlock(
                            "These items failed validation against the vocabulary. Return "
                            "corrected versions of those you can fix and leave out the rest. "
                            "Keep each concept's name and ref unchanged.\n"
                            + json.dumps(failed, indent=1)
                        ),
                    ],
                    tool,
                    purpose="concepts_repair",
                    context={**context, "failed": failed},
                )
            )
            add_usage(usage, repair.usage)
            raw_calls.append({"window": [span.start, span.end], "repair": repair.data})
            returned = _item_keys(repair.data)
            fold(work, repair.data, window, refs, final=True)
            for failure in failed:
                if _item_key(failure["in"], failure["item"]) in returned:
                    work.repaired += 1
                else:
                    # The repair left it out: settle the original as it stands.
                    fold(work, {failure["in"]: [failure["item"]]}, window, refs, final=True)

    decisions = match_pending(ctx, work, model, usage)
    proposal = build_proposal(work, decisions)
    return Next(
        Stage.COMMIT,
        usage=usage,
        raw_output={
            "calls": raw_calls,
            "proposal": proposal,
            "counts": {
                "concepts": len(proposal["nodes"]),
                "relationships": len(proposal["edges"]),
                "unsorted": sum(
                    1 for n in proposal["nodes"] if n["type"] == NodeType.UNSORTED.value
                ),
                "sent_to_unsorted": work.to_unsorted,
                "repaired": work.repaired,
                "dropped": work.dropped,
            },
        },
        model=model,
        prompt_version=prompt_version(PROMPT, PROMPT_VERSION),
    )


def _item_key(section: str, item: object) -> tuple[str, ...]:
    if not isinstance(item, dict):
        return (section,)
    if section == "relationships":
        return (section, str(item.get("type")), str(item.get("from")), str(item.get("to")))
    return (section, normalize_name(str(item.get("name") or "")))


def _item_keys(data: dict[str, Any]) -> set[tuple[str, ...]]:
    keys: set[tuple[str, ...]] = set()
    for section in ("concepts", "relationships", "unsorted"):
        items = data.get(section)
        keys |= {_item_key(section, item) for item in (items if isinstance(items, list) else [])}
    return keys


def load_vocabulary_block() -> str:
    path = Path(__file__).resolve().parents[1] / "domain/generated/vocabulary_prompt.md"
    return path.read_text().strip()


# --- Matching and the proposal ----------------------------------------------


def match_pending(
    ctx: StageContext, work: Working, model: str, usage: dict[str, int]
) -> list[Decision]:
    """Resolve every new concept against the atlas and log each decision."""
    settings = ctx.settings
    fresh = [
        p for p in work.pending.values() if p.node_id is None and p.type != NodeType.UNSORTED.value
    ]
    vectors = ctx.providers.embedder.embed([f"{p.name}. {p.description}".strip() for p in fresh])
    involved: dict[str, set[str]] = {}
    for edge in work.edges:
        if edge.type == RelationshipType.INVOLVES.value:
            target = work.pending.get(edge.to_key)
            if target is not None and target.node_id is not None:
                involved.setdefault(edge.from_key, set()).add(target.node_id)

    def decide(proposed: Proposed, candidate: Candidate) -> tuple[bool, str]:
        described = json.dumps(
            {
                "new": {
                    "type": proposed.type,
                    "name": proposed.name,
                    "description": proposed.description,
                    **proposed.attributes,
                },
                "existing": {
                    "type": candidate.type,
                    "name": candidate.name,
                    "description": candidate.description,
                    **candidate.attributes,
                    "also_known_as": sorted(candidate.aliases),
                },
            },
            indent=1,
        )
        result = ctx.providers.extraction.call(
            ToolCall(
                settings.small_model,
                [TextBlock(load_prompt(MATCH_PROMPT, MATCH_PROMPT_VERSION))],
                [TextBlock(described)],
                MATCH_TOOL,
                max_tokens=400,
                purpose="match_decision",
                context={"proposed": proposed.names, "candidate": sorted(candidate.aliases)},
            )
        )
        add_usage(usage, result.usage)
        return bool(result.data.get("same")), str(result.data.get("reason") or "")[:400]

    decisions: list[Decision] = []
    candidates = list(work.existing.values())
    for pending, vector in zip(fresh, vectors, strict=True):
        proposed = Proposed(
            pending.type,
            pending.name,
            pending.description,
            pending.attributes,
            pending.names,
            involved.get(pending.key, set()),
        )
        decision = resolve(
            proposed,
            candidates,
            vector,
            accept=settings.match_accept_threshold,
            review=settings.match_review_threshold,
            decide=decide,
        )
        pending.node_id = decision.matched_node_id
        decisions.append(decision)
    return decisions


def build_proposal(work: Working, decisions: list[Decision]) -> dict[str, Any]:
    """Turn the working state into what the commit stage inserts."""
    node_ids: dict[str, str] = {}
    nodes: dict[str, dict[str, Any]] = {}
    for key, pending in work.pending.items():
        is_new = pending.node_id is None
        node_id = pending.node_id or str(new_id())
        node_ids[key] = node_id
        entry = nodes.get(node_id)
        if entry is None:
            entry = nodes[node_id] = {
                "node_id": node_id,
                "is_new": is_new,
                "type": pending.type,
                "name": pending.name,
                "description": pending.description,
                "kind": pending.kind,
                "attributes": pending.attributes,
                "names": [],
                "evidence": [],
            }
        entry["names"] += [n for n in pending.names if n not in entry["names"]]
        seen = {(e["statement_id"], e["stance"]) for e in entry["evidence"]}
        entry["evidence"] += [
            asdict(e) for e in pending.evidence if (e.statement_id, e.stance) not in seen
        ]

    edges: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for edge in work.edges:
        source, target = node_ids.get(edge.from_key), node_ids.get(edge.to_key)
        if source is None or target is None or source == target:
            work.drop("unknown_endpoint")
            continue
        context = node_ids.get(edge.context_key) if edge.context_key else None
        edge_key = (edge.type, source, target, context)
        entry = edges.setdefault(
            edge_key,
            {
                "type": edge.type,
                "from_node_id": source,
                "to_node_id": target,
                "context_event_id": context,
                "attributes": edge.attributes,
                "valid_from": edge.valid_from,
                "valid_to": edge.valid_to,
                "evidence": [],
            },
        )
        entry["valid_from"] = entry["valid_from"] or edge.valid_from
        entry["valid_to"] = entry["valid_to"] or edge.valid_to
        seen = {(e["statement_id"], e["stance"]) for e in entry["evidence"]}
        entry["evidence"] += [
            asdict(e) for e in edge.evidence if (e.statement_id, e.stance) not in seen
        ]

    # A node with no evidence is only there as an endpoint of a relationship.
    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "decisions": [asdict(decision) for decision in decisions],
    }

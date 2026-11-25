"""The commit transaction, and embedding after it.

Each source commits in one transaction: statements, new nodes, new relationships
and evidence links are inserted, computed fields are recomputed for everything
touched, and the hypothesis and diagnosis rules are enforced. If any step fails,
nothing from the source is written.
"""

import datetime
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.db import atlas_store
from atlas.db.models import (
    Edge,
    Evidence,
    Node,
    NodeAlias,
    ResolutionDecision,
    Run,
    Segment,
    Statement,
)
from atlas.domain import rules
from atlas.domain.generated.vocabulary import (
    VOCABULARY_VERSION,
    EvidenceBasis,
    EvidenceStance,
    RecordState,
    SpeakerRole,
)
from atlas.domain.rules import EvidenceFact
from atlas.domain.text import normalize_name
from atlas.pipeline.concepts import latest_run
from atlas.pipeline.runner import StageContext
from atlas.pipeline.segments import quote_time
from atlas.pipeline.stages import Next, Outcome, Stage

EMBED_BATCH = 64


def _date(value: object) -> datetime.date | None:
    return datetime.date.fromisoformat(value) if isinstance(value, str) else None


def insert_statements(
    ctx: StageContext, run: Run, drafts: list[dict[str, Any]]
) -> dict[str, tuple[str, datetime.datetime]]:
    """Insert the validated statements. Returns each one's speaker role and time."""
    segments = {
        str(s.id): s
        for s in ctx.session.scalars(select(Segment).where(Segment.source_id == ctx.source.id))
    }
    present = ctx.session.scalar(
        select(func.count()).select_from(Statement).where(Statement.run_id == run.id)
    )
    facts: dict[str, tuple[str, datetime.datetime]] = {}
    for draft in drafts:
        segment = segments[draft["segment_id"]]
        start_ms, end_ms = quote_time(segment.words, draft["quote_start"], draft["quote_end"])
        if start_ms is None:
            start_ms, end_ms = segment.start_ms, segment.end_ms
        said_at = ctx.source.occurred_at + datetime.timedelta(milliseconds=start_ms or 0)
        facts[draft["id"]] = (draft["speaker_role"], said_at)
        if present:
            continue
        ctx.session.add(
            Statement(
                id=uuid.UUID(draft["id"]),
                user_id=ctx.user_id,
                source_id=ctx.source.id,
                segment_id=segment.id,
                speaker_role=draft["speaker_role"],
                quote=draft["quote"],
                quote_start_char=segment.start_char + draft["quote_start"],
                quote_end_char=segment.start_char + draft["quote_end"],
                start_ms=start_ms,
                end_ms=end_ms,
                text=draft["text"],
                kind=draft["kind"],
                said_at=said_at,
                about_time_text=draft["about_time_text"],
                about_from=_date(draft["about_from"]),
                about_to=_date(draft["about_to"]),
                confidence=draft["confidence"],
                run_id=run.id,
            )
        )
    ctx.session.flush()
    return facts


def _facts(
    evidence: list[dict[str, Any]], statements: dict[str, tuple[str, datetime.datetime]]
) -> list[EvidenceFact]:
    return [
        EvidenceFact(
            speaker_role=SpeakerRole(statements[e["statement_id"]][0]),
            basis=EvidenceBasis(e["basis"]),
            stance=EvidenceStance(e["stance"]),
            said_at=statements[e["statement_id"]][1],
            confidence=e.get("confidence"),
            life_area_weights=e.get("life_area_weights"),
        )
        for e in evidence
    ]


def _canonical(session: Session, node_id: uuid.UUID) -> uuid.UUID:
    """Follow a soft merge to the node that now stands for this one."""
    for _ in range(10):
        merged_into = session.scalar(select(Node.merged_into_id).where(Node.id == node_id))
        if merged_into is None:
            return node_id
        node_id = merged_into
    return node_id


def commit_stage(ctx: StageContext) -> Outcome:
    session = ctx.session
    statements_run = latest_run(session, ctx.source.id, Stage.STATEMENTS)
    concepts_run = latest_run(session, ctx.source.id, Stage.CONCEPTS)
    assert statements_run.raw_output is not None and concepts_run.raw_output is not None
    proposal: dict[str, Any] = concepts_run.raw_output["proposal"]

    # Committing the same proposal again replaces what the earlier commit wrote.
    already = session.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.run_id == concepts_run.id)
    )
    if already:
        atlas_store.retract_run(session, concepts_run.id)
        concepts_run.status = "succeeded"

    # 1. Statements, new nodes, new relationships and evidence links.
    statements = insert_statements(ctx, statements_run, statements_run.raw_output["statements"])
    node_ids: dict[str, uuid.UUID] = {}
    touched_nodes: set[uuid.UUID] = set()
    for item in proposal["nodes"]:
        proposed_id = uuid.UUID(item["node_id"])
        if item["is_new"]:
            facts = _facts(item["evidence"], statements)
            # Enforced before anything is inserted, and again by a database constraint.
            rules.enforce_diagnosis_rule(item["type"], item["kind"], facts)
            computed = rules.compute(facts)
            session.add(
                Node(
                    id=proposed_id,
                    user_id=ctx.user_id,
                    type=item["type"],
                    name=item["name"],
                    normalized_name=normalize_name(item["name"]),
                    description=item["description"] or None,
                    kind=item["kind"],
                    attributes=item["attributes"],
                    noticed_by=computed.noticed_by,
                    status=computed.status.value,
                    schema_version=VOCABULARY_VERSION,
                    run_id=concepts_run.id,
                )
            )
            node_id = proposed_id
        else:
            node_id = _canonical(session, proposed_id)
        node_ids[item["node_id"]] = node_id
        session.flush()

        known = set(
            session.scalars(select(NodeAlias.normalized_alias).where(NodeAlias.node_id == node_id))
        )
        for name in item["names"]:
            normalized = normalize_name(name)
            if normalized and normalized not in known:
                known.add(normalized)
                session.add(
                    NodeAlias(
                        user_id=ctx.user_id,
                        node_id=node_id,
                        alias=name,
                        normalized_alias=normalized,
                        run_id=concepts_run.id,
                    )
                )
        for link in item["evidence"]:
            session.add(_evidence(ctx, concepts_run, "node", node_id, link))
        if item["evidence"] or item["is_new"]:
            touched_nodes.add(node_id)

    touched_edges: set[uuid.UUID] = set()
    for item in proposal["edges"]:
        source, target = node_ids[item["from_node_id"]], node_ids[item["to_node_id"]]
        context = node_ids.get(item["context_event_id"]) if item["context_event_id"] else None
        if source == target:
            continue
        edge = session.scalars(
            select(Edge).where(
                Edge.type == item["type"],
                Edge.from_node_id == source,
                Edge.to_node_id == target,
                Edge.context_event_id.is_(None)
                if context is None
                else Edge.context_event_id == context,
                Edge.state != RecordState.MERGED.value,
            )
        ).first()
        if edge is None:
            edge = Edge(
                user_id=ctx.user_id,
                type=item["type"],
                from_node_id=source,
                to_node_id=target,
                context_event_id=context,
                attributes=item["attributes"],
                status="hypothesis",
                valid_from=_date(item["valid_from"]),
                valid_to=_date(item["valid_to"]),
                run_id=concepts_run.id,
            )
            session.add(edge)
            session.flush()
        for link in item["evidence"]:
            session.add(_evidence(ctx, concepts_run, "edge", edge.id, link))
        touched_edges.add(edge.id)

    for decision in proposal["decisions"]:
        matched = decision["matched_node_id"]
        session.add(
            ResolutionDecision(
                user_id=ctx.user_id,
                run_id=concepts_run.id,
                proposed={**decision["proposed"], "similarity": decision.get("similarity")},
                candidate_ids=[uuid.UUID(c) for c in decision["candidate_ids"]],
                decision=decision["decision"],
                matched_node_id=uuid.UUID(matched) if matched else None,
                reason=decision.get("reason"),
            )
        )
    session.flush()

    # 2 and 3. Recompute everything touched; a broken rule rolls the whole source back.
    atlas_store.recompute(session, touched_nodes, touched_edges, strict=True)
    return Next(
        Stage.EMBED,
        usage={
            "statements": len(statements),
            "nodes": len(touched_nodes),
            "edges": len(touched_edges),
        },
    )


def _evidence(
    ctx: StageContext, run: Run, kind: str, target_id: uuid.UUID, link: dict[str, Any]
) -> Evidence:
    return Evidence(
        user_id=ctx.user_id,
        statement_id=uuid.UUID(link["statement_id"]),
        target_kind=kind,
        target_id=target_id,
        stance=link["stance"],
        basis=link["basis"],
        confidence=link.get("confidence"),
        life_area_weights=link.get("life_area_weights"),
        run_id=run.id,
    )


def embed_stage(ctx: StageContext) -> Outcome:
    """Embed new statements (their restated text) and new nodes (name plus description)."""
    embedder = ctx.providers.embedder
    statements = list(
        ctx.session.scalars(
            select(Statement).where(
                Statement.source_id == ctx.source.id, Statement.embedding.is_(None)
            )
        )
    )
    nodes = list(
        ctx.session.scalars(
            select(Node).where(Node.embedding.is_(None), Node.state == RecordState.ACTIVE.value)
        )
    )
    texts = [s.text for s in statements] + [
        f"{n.name}. {n.description or ''}".strip() for n in nodes
    ]
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        vectors += embedder.embed(texts[start : start + EMBED_BATCH])
    for statement, vector in zip(statements, vectors[: len(statements)], strict=True):
        statement.embedding = vector
        statement.embedding_model = embedder.model
        statement.embedding_dimension = len(vector)
    for node, vector in zip(nodes, vectors[len(statements) :], strict=True):
        node.embedding = vector
        node.embedding_model = embedder.model
        node.embedding_dimension = len(vector)
    ctx.session.flush()
    return Next(Stage.PLACE, usage={"embedded": len(vectors)}, model=embedder.model)

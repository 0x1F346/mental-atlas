"""Writes to the atlas that must stay exact: recomputing derived fields and retraction.

Everything here runs inside the caller's user-scoped transaction.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from atlas.db.models import (
    Edge,
    Evidence,
    LifeArea,
    MediaFile,
    Node,
    NodeAlias,
    ResolutionDecision,
    Run,
    Source,
    Statement,
    Transcript,
)
from atlas.domain import rules
from atlas.domain.generated.vocabulary import (
    EvidenceBasis,
    EvidenceStance,
    RecordState,
    SpeakerRole,
)
from atlas.domain.rules import EvidenceFact, RuleViolation

NODE = "node"
EDGE = "edge"


@dataclass
class Retraction:
    """What a retraction removed. Counts only; safe to log."""

    statements: int = 0
    evidence: int = 0
    nodes_deleted: int = 0
    edges_deleted: int = 0
    nodes_marked: int = 0
    edges_marked: int = 0
    storage_keys: list[str] = field(default_factory=list)


def _facts(
    session: Session, kind: str, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[EvidenceFact]]:
    ids = list(ids)
    facts: dict[uuid.UUID, list[EvidenceFact]] = defaultdict(list)
    if not ids:
        return facts
    rows = session.execute(
        select(
            Evidence.target_id,
            Statement.speaker_role,
            Evidence.basis,
            Evidence.stance,
            Statement.said_at,
            Evidence.confidence,
            Evidence.life_area_weights,
        )
        .join(Statement, Statement.id == Evidence.statement_id)
        .where(Evidence.target_kind == kind, Evidence.target_id.in_(ids))
    )
    for target_id, role, basis, stance, said_at, confidence, weights in rows:
        facts[target_id].append(
            EvidenceFact(
                speaker_role=SpeakerRole(role),
                basis=EvidenceBasis(basis),
                stance=EvidenceStance(stance),
                said_at=said_at,
                confidence=confidence,
                life_area_weights=weights,
            )
        )
    return facts


def recompute(
    session: Session,
    node_ids: Iterable[uuid.UUID] = (),
    edge_ids: Iterable[uuid.UUID] = (),
    *,
    strict: bool = True,
) -> None:
    """Recompute noticed_by, status, counts, dates and life-area weights from evidence.

    With `strict` (a commit), a diagnosis nobody stated raises RuleViolation, which
    rolls the whole source back. Without it (a retraction), such a node is marked
    retracted instead. A row with no evidence left is marked retracted unless the
    system created it.
    """
    session.flush()
    node_ids, edge_ids = set(node_ids), set(edge_ids)
    areas = {area.key: area.id for area in session.scalars(select(LifeArea))}

    node_facts = _facts(session, NODE, node_ids)
    for node in session.scalars(select(Node).where(Node.id.in_(node_ids))):
        facts = node_facts.get(node.id, [])
        computed = rules.compute(facts)
        unstated_diagnosis = (
            node.state != RecordState.MERGED.value
            and rules.is_diagnosis(node.type, node.kind)
            and not rules.diagnosis_allowed(facts)
        )
        already_retracted = node.state == RecordState.RETRACTED.value
        if unstated_diagnosis and strict and not already_retracted:
            raise RuleViolation("diagnosis_without_explicit_statement")
        if unstated_diagnosis:
            # Retract before the status changes, so an active diagnosis is never a hypothesis.
            node.state = RecordState.RETRACTED.value
        node.evidence_count = computed.evidence_count
        node.first_seen_at = computed.first_seen_at
        node.last_seen_at = computed.last_seen_at
        if node.is_system and not facts:
            continue  # A system node keeps its seeded status and place.
        node.noticed_by = computed.noticed_by
        node.status = computed.status.value
        node.confidence = computed.confidence
        if not node.is_system or computed.life_area_weights:
            node.life_area_weights = computed.life_area_weights
            node.life_area_id = areas.get(computed.home_area.value)
        if node.state == RecordState.MERGED.value or unstated_diagnosis:
            continue
        if not facts and not node.is_system:
            node.state = RecordState.RETRACTED.value
        elif node.state == RecordState.RETRACTED.value:
            node.state = RecordState.ACTIVE.value

    edge_facts = _facts(session, EDGE, edge_ids)
    for edge in session.scalars(select(Edge).where(Edge.id.in_(edge_ids))):
        facts = edge_facts.get(edge.id, [])
        computed = rules.compute(facts)
        edge.noticed_by = computed.noticed_by
        edge.status = computed.status.value
        edge.evidence_count = computed.evidence_count
        edge.first_seen_at = computed.first_seen_at
        edge.last_seen_at = computed.last_seen_at
        edge.confidence = computed.confidence
        if not facts:
            edge.state = RecordState.RETRACTED.value
        elif edge.state == RecordState.RETRACTED.value:
            edge.state = RecordState.ACTIVE.value
    session.flush()


def _evidence_counts(session: Session, kind: str, ids: set[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = session.execute(
        select(Evidence.target_id, func.count())
        .where(Evidence.target_kind == kind, Evidence.target_id.in_(ids))
        .group_by(Evidence.target_id)
    )
    return {target_id: count for target_id, count in rows}


def _adopt(
    session: Session, model: type[Node] | type[Edge], kind: str, ids: set[uuid.UUID]
) -> None:
    """Re-attribute surviving rows to the run of their earliest remaining evidence."""
    for row_id in ids:
        run_id = session.execute(
            select(Evidence.run_id)
            .join(Statement, Statement.id == Evidence.statement_id)
            .where(Evidence.target_kind == kind, Evidence.target_id == row_id)
            .order_by(Statement.said_at, Evidence.id)
            .limit(1)
        ).scalar_one()
        session.execute(update(model).where(model.id == row_id).values(run_id=run_id))


def retract_run(session: Session, run_id: uuid.UUID) -> Retraction:
    """Remove exactly what one run wrote, then recompute everything it touched."""
    session.flush()
    result = Retraction()

    statement_ids = select(Statement.id).where(Statement.run_id == run_id)
    touching = (Evidence.run_id == run_id) | Evidence.statement_id.in_(statement_ids)
    touched: dict[str, set[uuid.UUID]] = {NODE: set(), EDGE: set()}
    for kind, target_id in session.execute(
        select(Evidence.target_kind, Evidence.target_id).where(touching)
    ):
        touched[kind].add(target_id)
    created_nodes = set(session.scalars(select(Node.id).where(Node.run_id == run_id)))
    created_edges = set(session.scalars(select(Edge.id).where(Edge.run_id == run_id)))

    result.evidence = session.execute(delete(Evidence).where(touching)).rowcount  # type: ignore[attr-defined]
    result.statements = session.execute(
        delete(Statement).where(Statement.run_id == run_id)
    ).rowcount  # type: ignore[attr-defined]
    session.execute(delete(ResolutionDecision).where(ResolutionDecision.run_id == run_id))
    session.execute(delete(NodeAlias).where(NodeAlias.run_id == run_id))

    # Relationships first: deleting a node would take its relationships with it.
    edge_counts = _evidence_counts(session, EDGE, created_edges)
    dead_edges = {edge_id for edge_id in created_edges if not edge_counts.get(edge_id)}
    if dead_edges:
        session.execute(delete(Edge).where(Edge.id.in_(dead_edges)))
    _adopt(session, Edge, EDGE, created_edges - dead_edges)

    node_counts = _evidence_counts(session, NODE, created_nodes)
    in_use = set(
        session.scalars(select(Edge.from_node_id).where(Edge.from_node_id.in_(created_nodes)))
    ) | set(session.scalars(select(Edge.to_node_id).where(Edge.to_node_id.in_(created_nodes))))
    in_use |= {
        node_id
        for node_id in session.scalars(
            select(Edge.context_event_id).where(Edge.context_event_id.in_(created_nodes))
        )
        if node_id is not None
    }
    dead_nodes = {
        node_id
        for node_id in created_nodes
        if not node_counts.get(node_id) and node_id not in in_use
    }
    if dead_nodes:
        session.execute(delete(Node).where(Node.id.in_(dead_nodes)))
    _adopt(session, Node, NODE, {n for n in created_nodes - dead_nodes if node_counts.get(n)})
    result.nodes_deleted, result.edges_deleted = len(dead_nodes), len(dead_edges)

    session.expire_all()
    remaining_nodes = (touched[NODE] | created_nodes) - dead_nodes
    remaining_edges = (touched[EDGE] | created_edges) - dead_edges
    before_nodes = _retracted(session, Node, remaining_nodes)
    before_edges = _retracted(session, Edge, remaining_edges)
    recompute(session, remaining_nodes, remaining_edges, strict=False)
    result.nodes_marked = len(_retracted(session, Node, remaining_nodes) - before_nodes)
    result.edges_marked = len(_retracted(session, Edge, remaining_edges) - before_edges)

    session.execute(
        update(Run).where(Run.id == run_id).values(status="retracted", finished_at=func.now())
    )
    session.flush()
    return result


def _retracted(
    session: Session, model: type[Node] | type[Edge], ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    if not ids:
        return set()
    return set(
        session.scalars(
            select(model.id).where(model.id.in_(ids), model.state == RecordState.RETRACTED.value)
        )
    )


def retract_source(session: Session, source_id: uuid.UUID) -> Retraction:
    """Retract every run of a source, then delete the source and all that hangs from it.

    Returns the storage keys of its media; the caller deletes those objects after
    the transaction commits.
    """
    total = Retraction()
    runs = session.scalars(
        select(Run.id)
        .where(Run.source_id == source_id)
        .order_by(Run.started_at.desc(), Run.id.desc())
    ).all()
    for run_id in runs:
        part = retract_run(session, run_id)
        total.statements += part.statements
        total.evidence += part.evidence
        total.nodes_deleted += part.nodes_deleted
        total.edges_deleted += part.edges_deleted
        total.nodes_marked += part.nodes_marked
        total.edges_marked += part.edges_marked
    total.storage_keys = list(
        session.scalars(select(MediaFile.storage_key).where(MediaFile.source_id == source_id))
    ) + [
        key
        for key in session.scalars(
            select(Transcript.raw_response_key).where(Transcript.source_id == source_id)
        )
        if key
    ]
    session.execute(delete(Source).where(Source.id == source_id))
    session.flush()
    session.expire_all()
    return total

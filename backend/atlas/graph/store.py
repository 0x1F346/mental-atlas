"""GraphStore: the one interface every graph read goes through.

V1 has a single implementation, an in-memory copy of one user's graph loaded from
Postgres. One user's graph is small, so algorithms run on this copy. A second
implementation (for example a read-only Neo4j copy) can be added behind the same
interface without touching callers.
"""

import datetime
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Edge, LifeArea, Node
from atlas.domain.generated.vocabulary import CORE_TYPES, NodeType, RecordState

Direction = Literal["out", "in"]


@dataclass(frozen=True)
class GraphNode:
    id: uuid.UUID
    type: str
    kind: str | None
    name: str
    normalized_name: str
    description: str | None
    attributes: dict[str, Any]
    status: str
    noticed_by: tuple[str, ...]
    evidence_count: int
    first_seen_at: datetime.datetime | None
    last_seen_at: datetime.datetime | None
    life_area: str | None
    life_area_weights: dict[str, float]
    is_system: bool

    @property
    def is_self(self) -> bool:
        return bool(self.attributes.get("is_self"))


@dataclass(frozen=True)
class GraphEdge:
    id: uuid.UUID
    type: str
    from_id: uuid.UUID
    to_id: uuid.UUID
    context_event_id: uuid.UUID | None
    attributes: dict[str, Any]
    status: str
    noticed_by: tuple[str, ...]
    evidence_count: int
    first_seen_at: datetime.datetime | None
    last_seen_at: datetime.datetime | None
    valid_from: datetime.date | None
    valid_to: datetime.date | None


@dataclass(frozen=True)
class Neighbour:
    edge: GraphEdge
    node: GraphNode
    direction: Direction  # "out": the edge runs from the asked-about node to this one.


class GraphStore(Protocol):
    def nodes(self) -> Sequence[GraphNode]: ...
    def node(self, node_id: uuid.UUID) -> GraphNode | None: ...
    def edges(self) -> Sequence[GraphEdge]: ...
    def edge(self, edge_id: uuid.UUID) -> GraphEdge | None: ...
    def neighbours(self, node_id: uuid.UUID) -> Sequence[Neighbour]: ...


class InMemoryGraphStore:
    """One user's active graph, held in memory."""

    def __init__(self, nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]) -> None:
        self._nodes = {node.id: node for node in nodes}
        # An edge is only part of the graph when both of its ends are.
        self._edges = {
            edge.id: edge
            for edge in edges
            if edge.from_id in self._nodes and edge.to_id in self._nodes
        }
        self._adjacent: dict[uuid.UUID, list[Neighbour]] = defaultdict(list)
        for edge in self._edges.values():
            self._adjacent[edge.from_id].append(Neighbour(edge, self._nodes[edge.to_id], "out"))
            self._adjacent[edge.to_id].append(Neighbour(edge, self._nodes[edge.from_id], "in"))

    def nodes(self) -> Sequence[GraphNode]:
        return list(self._nodes.values())

    def node(self, node_id: uuid.UUID) -> GraphNode | None:
        return self._nodes.get(node_id)

    def edges(self) -> Sequence[GraphEdge]:
        return list(self._edges.values())

    def edge(self, edge_id: uuid.UUID) -> GraphEdge | None:
        return self._edges.get(edge_id)

    def neighbours(self, node_id: uuid.UUID) -> Sequence[Neighbour]:
        return sorted(self._adjacent.get(node_id, []), key=lambda n: (n.edge.type, n.node.name))


def load_graph(session: Session, *, include_unsorted: bool = False) -> InMemoryGraphStore:
    """Read the current user's active graph from Postgres, the only source of truth."""
    types = [t.value for t in CORE_TYPES]
    if include_unsorted:
        types.append(NodeType.UNSORTED.value)
    areas = {area.id: area.key for area in session.scalars(select(LifeArea))}
    nodes = [
        GraphNode(
            id=n.id,
            type=n.type,
            kind=n.kind,
            name=n.name,
            normalized_name=n.normalized_name,
            description=n.description,
            attributes=dict(n.attributes),
            status=n.status,
            noticed_by=tuple(n.noticed_by),
            evidence_count=n.evidence_count,
            first_seen_at=n.first_seen_at,
            last_seen_at=n.last_seen_at,
            life_area=areas.get(n.life_area_id) if n.life_area_id else None,
            life_area_weights=dict(n.life_area_weights),
            is_system=n.is_system,
        )
        for n in session.scalars(
            select(Node)
            .where(Node.state == RecordState.ACTIVE.value, Node.type.in_(types))
            .order_by(Node.id)
        )
    ]
    edges = [
        GraphEdge(
            id=e.id,
            type=e.type,
            from_id=e.from_node_id,
            to_id=e.to_node_id,
            context_event_id=e.context_event_id,
            attributes=dict(e.attributes),
            status=e.status,
            noticed_by=tuple(e.noticed_by),
            evidence_count=e.evidence_count,
            first_seen_at=e.first_seen_at,
            last_seen_at=e.last_seen_at,
            valid_from=e.valid_from,
            valid_to=e.valid_to,
        )
        for e in session.scalars(
            select(Edge).where(Edge.state == RecordState.ACTIVE.value).order_by(Edge.id)
        )
    ]
    return InMemoryGraphStore(nodes, edges)

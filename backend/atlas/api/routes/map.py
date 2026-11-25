"""Read API for the map: the map document, one concept, and the quotes behind it."""

import datetime
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.api.deps import AuthDep, DbDep
from atlas.api.errors import ApiError
from atlas.db.models import Evidence, MapPosition, MediaFile, NodeAlias, Segment, Source, Statement
from atlas.db.seed import LIFE_AREA_NAMES
from atlas.domain import rules
from atlas.domain.generated.vocabulary import (
    EvidenceBasis,
    EvidenceStance,
    LifeArea,
    NodeType,
    NoticedBy,
    RelationshipType,
    SpeakerRole,
    StatementKind,
    Status,
)
from atlas.graph.geometry import SIZE, WEDGES
from atlas.graph.store import GraphEdge, GraphNode, GraphStore, load_graph
from atlas.pipeline.place import current_layout

router = APIRouter(tags=["map"])


def graph_store(db: DbDep) -> GraphStore:
    return load_graph(db)


GraphDep = Annotated[GraphStore, Depends(graph_store)]


class Region(BaseModel):
    key: LifeArea
    name: str
    # Points are [x, y] pairs in map units.
    anchor: list[float]
    polygon: list[list[float]]


class Landmark(BaseModel):
    id: uuid.UUID
    type: NodeType
    kind: str | None
    name: str
    x: float
    y: float
    life_area: LifeArea
    status: Status
    # Plain-language label. A hypothesis always carries one (the hypothesis rule).
    status_line: str
    is_hypothesis: bool
    noticed_by: list[NoticedBy]
    evidence_count: int
    first_seen_at: datetime.datetime | None
    last_seen_at: datetime.datetime | None
    is_self: bool
    source_ids: list[uuid.UUID]


class MapDocument(BaseModel):
    layout_version: int
    size: float
    regions: list[Region]
    landmarks: list[Landmark]


class NodeSummary(BaseModel):
    id: uuid.UUID
    type: NodeType
    kind: str | None
    name: str
    status: Status
    status_line: str
    is_hypothesis: bool


class RelationshipOut(BaseModel):
    edge_id: uuid.UUID
    type: RelationshipType
    direction: Literal["out", "in"]
    status: Status
    status_line: str
    is_hypothesis: bool
    evidence_count: int
    valid_from: datetime.date | None
    valid_to: datetime.date | None
    other: NodeSummary


class NodeDetail(NodeSummary):
    description: str | None
    attributes: dict[str, object]
    aliases: list[str]
    life_area: LifeArea
    noticed_by: list[NoticedBy]
    evidence_count: int
    first_seen_at: datetime.datetime | None
    last_seen_at: datetime.datetime | None
    is_self: bool
    relationships: list[RelationshipOut]


class EvidenceItem(BaseModel):
    id: uuid.UUID
    stance: EvidenceStance
    basis: EvidenceBasis
    statement_id: uuid.UUID
    quote: str
    text: str
    kind: StatementKind
    speaker_role: SpeakerRole
    said_at: datetime.datetime
    start_ms: int | None
    end_ms: int | None
    segment_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    source_occurred_at: datetime.datetime
    # The derived audio to play from start_ms; null for written sources.
    audio_media_id: uuid.UUID | None


class EvidenceOut(BaseModel):
    target_kind: Literal["node", "edge"]
    target_id: uuid.UUID
    title: str
    status: Status
    status_line: str
    is_hypothesis: bool
    items: list[EvidenceItem]


def _home(node: GraphNode) -> LifeArea:
    return LifeArea(node.life_area) if node.life_area else LifeArea.SELF


def _summary(node: GraphNode) -> NodeSummary:
    status = Status(node.status)
    return NodeSummary(
        id=node.id,
        type=NodeType(node.type),
        kind=node.kind,
        name=node.name,
        status=status,
        status_line=rules.status_line(status),
        is_hypothesis=status is Status.HYPOTHESIS,
    )


@router.get("/map")
def get_map(auth: AuthDep, db: DbDep, graph: GraphDep) -> MapDocument:
    """Regions as polygons and landmarks as points. Unsorted items are kept off the map."""
    layout, _ = current_layout(db, auth.user_id)
    shapes = layout.parameters["regions"]
    regions = [
        Region(
            key=area,
            name=LIFE_AREA_NAMES[area],
            anchor=shapes[area.value]["anchor"],
            polygon=shapes[area.value]["polygon"],
        )
        for area in (*WEDGES, LifeArea.SELF)
    ]
    positions = {
        row.node_id: (row.x, row.y)
        for row in db.scalars(select(MapPosition).where(MapPosition.layout_id == layout.id))
    }
    sources: dict[uuid.UUID, set[uuid.UUID]] = {}
    for node_id, source_id in db.execute(
        select(Evidence.target_id, Statement.source_id)
        .join(Statement, Statement.id == Evidence.statement_id)
        .where(Evidence.target_kind == "node")
        .distinct()
    ):
        sources.setdefault(node_id, set()).add(source_id)
    landmarks = []
    for node in graph.nodes():
        if node.id not in positions:
            continue
        summary = _summary(node)
        landmarks.append(
            Landmark(
                **summary.model_dump(),
                x=positions[node.id][0],
                y=positions[node.id][1],
                life_area=_home(node),
                noticed_by=[NoticedBy(n) for n in node.noticed_by],
                evidence_count=node.evidence_count,
                first_seen_at=node.first_seen_at,
                last_seen_at=node.last_seen_at,
                is_self=node.is_self,
                source_ids=sorted(sources.get(node.id, set())),
            )
        )
    return MapDocument(
        layout_version=layout.version, size=SIZE, regions=regions, landmarks=landmarks
    )


@router.get("/nodes/{node_id}")
def get_node(node_id: uuid.UUID, db: DbDep, graph: GraphDep) -> NodeDetail:
    """One concept with its neighbours."""
    node = graph.node(node_id)
    if node is None:
        raise ApiError(404, "node_not_found", "No such concept.")
    aliases = db.scalars(
        select(NodeAlias.alias).where(NodeAlias.node_id == node_id).order_by(NodeAlias.alias)
    ).all()
    relationships = []
    for neighbour in graph.neighbours(node_id):
        status = Status(neighbour.edge.status)
        relationships.append(
            RelationshipOut(
                edge_id=neighbour.edge.id,
                type=RelationshipType(neighbour.edge.type),
                direction=neighbour.direction,
                status=status,
                status_line=rules.status_line(status),
                is_hypothesis=status is Status.HYPOTHESIS,
                evidence_count=neighbour.edge.evidence_count,
                valid_from=neighbour.edge.valid_from,
                valid_to=neighbour.edge.valid_to,
                other=_summary(neighbour.node),
            )
        )
    return NodeDetail(
        **_summary(node).model_dump(),
        description=node.description,
        attributes=node.attributes,
        aliases=[alias for alias in aliases if alias != node.name],
        life_area=_home(node),
        noticed_by=[NoticedBy(n) for n in node.noticed_by],
        evidence_count=node.evidence_count,
        first_seen_at=node.first_seen_at,
        last_seen_at=node.last_seen_at,
        is_self=node.is_self,
        relationships=relationships,
    )


def _evidence(
    db: Session, kind: Literal["node", "edge"], target_id: uuid.UUID
) -> list[EvidenceItem]:
    rows = db.execute(
        select(Evidence, Statement, Source, Segment.id)
        .join(Statement, Statement.id == Evidence.statement_id)
        .join(Source, Source.id == Statement.source_id)
        .join(Segment, Segment.id == Statement.segment_id)
        .where(Evidence.target_kind == kind, Evidence.target_id == target_id)
        .order_by(Statement.said_at, Statement.quote_start_char, Evidence.id)
    ).all()
    audio = {
        media.source_id: media.id
        for media in db.scalars(
            select(MediaFile).where(
                MediaFile.role == "audio",
                MediaFile.source_id.in_({source.id for _, _, source, _ in rows}),
            )
        )
    }
    return [
        EvidenceItem(
            id=evidence.id,
            stance=EvidenceStance(evidence.stance),
            basis=EvidenceBasis(evidence.basis),
            statement_id=statement.id,
            quote=statement.quote,
            text=statement.text,
            kind=StatementKind(statement.kind),
            speaker_role=SpeakerRole(statement.speaker_role),
            said_at=statement.said_at,
            start_ms=statement.start_ms,
            end_ms=statement.end_ms,
            segment_id=segment_id,
            source_id=source.id,
            source_title=source.title,
            source_occurred_at=source.occurred_at,
            audio_media_id=audio.get(source.id),
        )
        for evidence, statement, source, segment_id in rows
    ]


@router.get("/nodes/{node_id}/evidence")
def node_evidence(node_id: uuid.UUID, db: DbDep, graph: GraphDep) -> EvidenceOut:
    """The quotes behind a concept."""
    node = graph.node(node_id)
    if node is None:
        raise ApiError(404, "node_not_found", "No such concept.")
    status = Status(node.status)
    return EvidenceOut(
        target_kind="node",
        target_id=node.id,
        title=node.name,
        status=status,
        status_line=rules.status_line(status),
        is_hypothesis=status is Status.HYPOTHESIS,
        items=_evidence(db, "node", node.id),
    )


def _edge_title(graph: GraphStore, edge: GraphEdge) -> str:
    source, target = graph.node(edge.from_id), graph.node(edge.to_id)
    verb = edge.type.replace("_", " ").lower()
    return f"{source.name if source else '?'} {verb} {target.name if target else '?'}"


@router.get("/edges/{edge_id}/evidence")
def edge_evidence(edge_id: uuid.UUID, db: DbDep, graph: GraphDep) -> EvidenceOut:
    """The quotes behind a relationship."""
    edge = graph.edge(edge_id)
    if edge is None:
        raise ApiError(404, "edge_not_found", "No such relationship.")
    status = Status(edge.status)
    return EvidenceOut(
        target_kind="edge",
        target_id=edge.id,
        title=_edge_title(graph, edge),
        status=status,
        status_line=rules.status_line(status),
        is_hypothesis=status is Status.HYPOTHESIS,
        items=_evidence(db, "edge", edge.id),
    )

"""The layout stage: give every new concept a position on the map and save it.

Layout runs in the worker, so every device shows the same map.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from atlas.db.models import MapLayout, MapPosition
from atlas.domain.generated.vocabulary import LifeArea, NodeType
from atlas.graph.geometry import Geometry
from atlas.graph.layout import ToPlace, place
from atlas.graph.store import GraphNode, load_graph
from atlas.pipeline.runner import StageContext
from atlas.pipeline.stages import Next, Outcome


def layout_seed(user_id: uuid.UUID) -> int:
    """Fixed per user, so a user's borders never change."""
    return user_id.int % (2**31)


def current_layout(session: Session, user_id: uuid.UUID) -> tuple[MapLayout, Geometry]:
    """The user's newest layout, created as version 1 the first time it is needed."""
    layout = session.scalars(select(MapLayout).order_by(MapLayout.version.desc())).first()
    if layout is None:
        geometry = Geometry(layout_seed(user_id))
        layout = MapLayout(user_id=user_id, version=1, parameters=geometry.parameters())
        session.add(layout)
        session.flush()
        return layout, geometry
    return layout, Geometry(int(layout.parameters["seed"]))


def home_of(node: GraphNode) -> LifeArea:
    return LifeArea(node.life_area) if node.life_area else LifeArea.SELF


def place_new_concepts(session: Session, user_id: uuid.UUID) -> int:
    """Place every active concept that has no position. Returns how many were placed."""
    layout, geometry = current_layout(session, user_id)
    graph = load_graph(session)
    on_map = {node.id: node for node in graph.nodes() if node.type != NodeType.UNSORTED.value}
    rows = session.scalars(select(MapPosition).where(MapPosition.layout_id == layout.id)).all()

    existing: dict[str, tuple[float, float]] = {}
    for row in rows:
        node = on_map.get(row.node_id)
        # A position goes when its concept leaves the map, or when its home area changes.
        moved_home = (
            node is not None
            and not node.is_self
            and geometry.region_of((row.x, row.y)) is not home_of(node)
        )
        if node is None or moved_home:
            session.execute(delete(MapPosition).where(MapPosition.id == row.id))
        else:
            existing[str(row.node_id)] = (row.x, row.y)

    new = [
        ToPlace(
            id=str(node.id),
            key=f"{node.type}:{node.normalized_name}",
            home=home_of(node),
            weights=node.life_area_weights,
            neighbours=[str(n.node.id) for n in graph.neighbours(node.id)],
            is_self=node.is_self,
        )
        for node in on_map.values()
        if str(node.id) not in existing
    ]
    for node_id, (x, y) in place(geometry, existing, new).items():
        session.add(
            MapPosition(user_id=user_id, node_id=uuid.UUID(node_id), layout_id=layout.id, x=x, y=y)
        )
    session.flush()
    return len(new)


def place_stage(ctx: StageContext) -> Outcome:
    placed = place_new_concepts(ctx.session, ctx.user_id)
    return Next(None, usage={"placed": placed})

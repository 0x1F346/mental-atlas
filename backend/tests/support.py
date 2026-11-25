"""Hand-built test graphs. All content is invented."""

import datetime
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db import atlas_store
from atlas.db.models import (
    Edge,
    Evidence,
    MediaFile,
    Node,
    NodeAlias,
    Run,
    Segment,
    Source,
    Speaker,
    Statement,
)
from atlas.domain.text import normalize_name

UTC = datetime.UTC


@dataclass
class Builder:
    """Adds one invented source at a time to a user's atlas."""

    session: Session
    user_id: uuid.UUID
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], Edge] = field(default_factory=dict)

    def source(self, title: str, when: datetime.datetime) -> "SourceBuilder":
        source = Source(user_id=self.user_id, kind="therapy_session", title=title, occurred_at=when)
        self.session.add(source)
        self.session.flush()
        self.session.add(
            MediaFile(
                user_id=self.user_id,
                source_id=source.id,
                storage_key=f"media/{source.id}/original",
                mime_type="audio/mpeg",
                bytes=10,
                sha256=uuid.uuid4().hex,
                role="original",
            )
        )
        speakers = {}
        for label, role in (("speaker_0", "self"), ("speaker_1", "therapist")):
            speaker = Speaker(
                user_id=self.user_id,
                source_id=source.id,
                provider_label=label,
                role=role,
                method="model",
                confidence=0.95,
            )
            self.session.add(speaker)
            speakers[role] = speaker
        run = Run(user_id=self.user_id, source_id=source.id, kind="concepts", pipeline_version=1)
        self.session.add(run)
        self.session.flush()
        return SourceBuilder(self, source, run, speakers, when)


@dataclass
class SourceBuilder:
    builder: Builder
    source: Source
    run: Run
    speakers: dict[str, Speaker]
    when: datetime.datetime
    _idx: int = 0

    def say(self, role: str, text: str) -> Statement:
        b = self.builder
        segment = Segment(
            user_id=b.user_id,
            source_id=self.source.id,
            speaker_id=self.speakers[role].id,
            idx=self._idx,
            start_ms=self._idx * 1000,
            end_ms=self._idx * 1000 + 900,
            start_char=0,
            end_char=len(text),
            text=text,
        )
        self._idx += 1
        b.session.add(segment)
        b.session.flush()
        statement = Statement(
            user_id=b.user_id,
            source_id=self.source.id,
            segment_id=segment.id,
            speaker_role=role,
            quote=text,
            quote_start_char=0,
            quote_end_char=len(text),
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=text,
            kind="observation" if role == "therapist" else "report",
            said_at=self.when,
            confidence=0.9,
            run_id=self.run.id,
        )
        b.session.add(statement)
        b.session.flush()
        return statement

    def node(self, node_type: str, name: str, kind: str | None = None) -> Node:
        b = self.builder
        if name not in b.nodes:
            node = Node(
                user_id=b.user_id,
                type=node_type,
                name=name,
                normalized_name=normalize_name(name),
                kind=kind,
                status="stated",
                schema_version=1,
                run_id=self.run.id,
            )
            b.session.add(node)
            b.session.flush()
            b.session.add(
                NodeAlias(
                    user_id=b.user_id,
                    node_id=node.id,
                    alias=name,
                    normalized_alias=normalize_name(name),
                    run_id=self.run.id,
                )
            )
            b.nodes[name] = node
        return b.nodes[name]

    def edge(self, edge_type: str, from_name: str, to_name: str) -> Edge:
        b = self.builder
        key = (edge_type, from_name, to_name)
        if key not in b.edges:
            edge = Edge(
                user_id=b.user_id,
                type=edge_type,
                from_node_id=b.nodes[from_name].id,
                to_node_id=b.nodes[to_name].id,
                status="stated",
                run_id=self.run.id,
            )
            b.session.add(edge)
            b.session.flush()
            b.edges[key] = edge
        return b.edges[key]

    def link(
        self,
        statement: Statement,
        target: Node | Edge,
        basis: str = "explicit",
        stance: str = "supports",
        weights: dict[str, float] | None = None,
    ) -> None:
        b = self.builder
        b.session.add(
            Evidence(
                user_id=b.user_id,
                statement_id=statement.id,
                target_kind="node" if isinstance(target, Node) else "edge",
                target_id=target.id,
                stance=stance,
                basis=basis,
                confidence=0.8,
                life_area_weights=weights,
                run_id=self.run.id,
            )
        )
        b.session.flush()

    def commit(self) -> None:
        b = self.builder
        atlas_store.recompute(
            b.session, [n.id for n in b.nodes.values()], [e.id for e in b.edges.values()]
        )


WORK = {"work": 0.8, "self": 0.2}


def build_first_session(builder: Builder) -> SourceBuilder:
    """A small invented session: a feeling, a belief, a behaviour, a person and an event."""
    s = builder.source("Invented session one", datetime.datetime(2026, 1, 5, 9, tzinfo=UTC))
    said_dread = s.say("self", "I felt dread before the review with Dana.")
    observed = s.say("therapist", "It sounds like you expect to be found out.")
    went_quiet = s.say("self", "So I went quiet and stopped answering her messages.")
    dread = s.node("feeling", "dread")
    belief = s.node("belief", "I will be found out")
    quiet = s.node("behaviour", "going quiet")
    dana = s.node("person", "Dana")
    review = s.node("event", "Review with Dana, January 2026")
    s.link(said_dread, dread, weights=WORK)
    s.link(said_dread, dana, weights=WORK)
    s.link(said_dread, review, weights=WORK)
    s.link(observed, belief, weights=WORK)
    s.link(went_quiet, quiet, weights=WORK)
    s.link(went_quiet, belief, basis="implied", weights=WORK)
    s.link(said_dread, s.edge("OCCURRED_IN", "dread", "Review with Dana, January 2026"))
    s.link(went_quiet, s.edge("LED_TO", "dread", "going quiet"), basis="implied")
    s.link(said_dread, s.edge("INVOLVES", "Review with Dana, January 2026", "Dana"))
    s.commit()
    return s


def build_second_session(builder: Builder) -> SourceBuilder:
    """A later invented session that repeats the feeling and has the owner state the belief."""
    s = builder.source("Invented session two", datetime.datetime(2026, 2, 9, 9, tzinfo=UTC))
    again = s.say("self", "The dread came back on Sunday night.")
    stated = s.say("self", "I really do think I will be found out.")
    s.link(again, s.node("feeling", "dread"), weights=WORK)
    s.link(stated, s.node("belief", "I will be found out"), weights=WORK)
    s.commit()
    return s


def node_named(session: Session, name: str) -> Node | None:
    session.expire_all()
    return session.scalars(select(Node).where(Node.name == name)).one_or_none()

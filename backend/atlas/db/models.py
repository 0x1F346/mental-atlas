"""Table models for the four layers.

Every table has id (time-ordered UUID), user_id and created_at, and a row-level
security policy created in the same migration as the table. Value sets come from
the generated vocabulary and are enforced by generated check constraints.
"""

import datetime
import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from atlas.db.ids import new_id

type Json = dict[str, Any]


class Base(DeclarativeBase):
    type_annotation_map = {  # noqa: RUF012
        uuid.UUID: PgUUID(as_uuid=True),
        datetime.datetime: DateTime(timezone=True),
        datetime.date: Date,
        str: Text,
        dict[str, Any]: JSONB,
    }


class Row(Base):
    """Columns shared by every table."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())


def _fk(target: str, ondelete: str = "CASCADE") -> ForeignKey:
    return ForeignKey(target, ondelete=ondelete)


# --- Accounts ---------------------------------------------------------------


class User(Row):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]


class Session(Row):
    """Server-side sign-in session. Only a hash of the cookie token is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(unique=True)
    csrf_token: Mapped[str]
    expires_at: Mapped[datetime.datetime]


# --- Run log ----------------------------------------------------------------


class Run(Row):
    """One execution of one pipeline stage. Every atlas write carries its id."""

    __tablename__ = "runs"

    source_id: Mapped[uuid.UUID | None] = mapped_column(_fk("sources.id"))
    kind: Mapped[str]
    pipeline_version: Mapped[int]
    prompt_version: Mapped[str | None]
    schema_version: Mapped[int | None]
    model: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="running")
    raw_output: Mapped[Json | None]
    usage: Mapped[Json | None]
    error: Mapped[str | None]
    started_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime.datetime | None]


class Job(Row):
    """One queued pipeline stage for one source. Claimed through atlas_claim_job()."""

    __tablename__ = "jobs"

    source_id: Mapped[uuid.UUID] = mapped_column(_fk("sources.id"))
    stage: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    run_after: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    locked_at: Mapped[datetime.datetime | None]
    locked_by: Mapped[str | None]
    payload: Mapped[Json] = mapped_column(default=dict, server_default="{}")
    error: Mapped[str | None]


# --- Layer 1: sources -------------------------------------------------------


class Source(Row):
    __tablename__ = "sources"

    kind: Mapped[str]
    title: Mapped[str]
    occurred_at: Mapped[datetime.datetime]
    status: Mapped[str] = mapped_column(default="uploaded")
    language: Mapped[str | None]
    metadata_: Mapped[Json] = mapped_column("metadata", default=dict, server_default="{}")


class MediaFile(Row):
    __tablename__ = "media_files"

    source_id: Mapped[uuid.UUID] = mapped_column(_fk("sources.id"))
    storage_key: Mapped[str]
    mime_type: Mapped[str]
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None]
    sha256: Mapped[str | None]
    role: Mapped[str]


class Transcript(Row):
    __tablename__ = "transcripts"

    source_id: Mapped[uuid.UUID] = mapped_column(_fk("sources.id"))
    provider: Mapped[str]
    model: Mapped[str]
    raw_response_key: Mapped[str | None]
    pipeline_version: Mapped[int]
    run_id: Mapped[uuid.UUID | None] = mapped_column(_fk("runs.id"))


class Speaker(Row):
    __tablename__ = "speakers"

    source_id: Mapped[uuid.UUID] = mapped_column(_fk("sources.id"))
    provider_label: Mapped[str]
    role: Mapped[str | None]
    person_node_id: Mapped[uuid.UUID | None] = mapped_column(_fk("nodes.id", "SET NULL"))
    method: Mapped[str | None]
    confidence: Mapped[float | None] = mapped_column(Float)


class Segment(Row):
    __tablename__ = "segments"

    source_id: Mapped[uuid.UUID] = mapped_column(_fk("sources.id"))
    speaker_id: Mapped[uuid.UUID] = mapped_column(_fk("speakers.id"))
    idx: Mapped[int]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    start_char: Mapped[int]
    end_char: Mapped[int]
    text: Mapped[str]
    # [[char offset in text, start_ms, end_ms], ...] per word, to find the moment of a quote.
    words: Mapped[list[Any] | None] = mapped_column(JSONB)


# --- Layer 2: statements ----------------------------------------------------


class Statement(Row):
    __tablename__ = "statements"

    source_id: Mapped[uuid.UUID] = mapped_column(_fk("sources.id"))
    segment_id: Mapped[uuid.UUID] = mapped_column(_fk("segments.id"))
    speaker_role: Mapped[str]
    quote: Mapped[str]
    quote_start_char: Mapped[int]
    quote_end_char: Mapped[int]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    text: Mapped[str]
    kind: Mapped[str]
    said_at: Mapped[datetime.datetime]
    about_time_text: Mapped[str | None]
    about_from: Mapped[datetime.date | None]
    about_to: Mapped[datetime.date | None]
    confidence: Mapped[float | None] = mapped_column(Float)
    run_id: Mapped[uuid.UUID] = mapped_column(_fk("runs.id"))
    embedding: Mapped[Any | None] = mapped_column(Vector())
    embedding_model: Mapped[str | None]
    embedding_dimension: Mapped[int | None]


# --- Layer 3: concepts ------------------------------------------------------


class Node(Row):
    __tablename__ = "nodes"

    type: Mapped[str]
    name: Mapped[str]
    normalized_name: Mapped[str]
    description: Mapped[str | None]
    kind: Mapped[str | None]
    attributes: Mapped[Json] = mapped_column(default=dict, server_default="{}")
    life_area_id: Mapped[uuid.UUID | None] = mapped_column(_fk("life_areas.id", "SET NULL"))
    life_area_weights: Mapped[Json] = mapped_column(default=dict, server_default="{}")
    # Computed from evidence by atlas.domain.rules; never set by hand.
    noticed_by: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    status: Mapped[str] = mapped_column(default="hypothesis")
    first_seen_at: Mapped[datetime.datetime | None]
    last_seen_at: Mapped[datetime.datetime | None]
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    confidence: Mapped[float | None] = mapped_column(Float)
    state: Mapped[str] = mapped_column(default="active", server_default="active")
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(_fk("nodes.id", "SET NULL"))
    schema_version: Mapped[int]
    run_id: Mapped[uuid.UUID | None] = mapped_column(_fk("runs.id", "SET NULL"))
    # Created by the system (the owner's own Person node, the therapist); never retracted.
    is_system: Mapped[bool] = mapped_column(default=False, server_default="false")
    embedding: Mapped[Any | None] = mapped_column(Vector())
    embedding_model: Mapped[str | None]
    embedding_dimension: Mapped[int | None]


class NodeAlias(Row):
    __tablename__ = "node_aliases"

    node_id: Mapped[uuid.UUID] = mapped_column(_fk("nodes.id"))
    alias: Mapped[str]
    normalized_alias: Mapped[str]
    run_id: Mapped[uuid.UUID | None] = mapped_column(_fk("runs.id", "SET NULL"))


class Edge(Row):
    __tablename__ = "edges"

    type: Mapped[str]
    from_node_id: Mapped[uuid.UUID] = mapped_column(_fk("nodes.id"))
    to_node_id: Mapped[uuid.UUID] = mapped_column(_fk("nodes.id"))
    context_event_id: Mapped[uuid.UUID | None] = mapped_column(_fk("nodes.id", "SET NULL"))
    attributes: Mapped[Json] = mapped_column(default=dict, server_default="{}")
    noticed_by: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    status: Mapped[str] = mapped_column(default="hypothesis")
    valid_from: Mapped[datetime.date | None]
    valid_to: Mapped[datetime.date | None]
    first_seen_at: Mapped[datetime.datetime | None]
    last_seen_at: Mapped[datetime.datetime | None]
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    confidence: Mapped[float | None] = mapped_column(Float)
    state: Mapped[str] = mapped_column(default="active", server_default="active")
    run_id: Mapped[uuid.UUID | None] = mapped_column(_fk("runs.id", "SET NULL"))


class Evidence(Row):
    """Ties a statement to a node or an edge. Deleted with its statement."""

    __tablename__ = "evidence"

    statement_id: Mapped[uuid.UUID] = mapped_column(_fk("statements.id"))
    target_kind: Mapped[str]
    target_id: Mapped[uuid.UUID]
    stance: Mapped[str]
    basis: Mapped[str]
    confidence: Mapped[float | None] = mapped_column(Float)
    # Life-area weights this mention gave its concept; node weights are recomputed from these.
    life_area_weights: Mapped[Json | None]
    run_id: Mapped[uuid.UUID] = mapped_column(_fk("runs.id"))


class ResolutionDecision(Row):
    __tablename__ = "resolution_decisions"

    run_id: Mapped[uuid.UUID] = mapped_column(_fk("runs.id"))
    proposed: Mapped[Json]
    candidate_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), default=list, server_default="{}"
    )
    decision: Mapped[str]
    matched_node_id: Mapped[uuid.UUID | None] = mapped_column(_fk("nodes.id", "SET NULL"))
    reason: Mapped[str | None]


# --- Layer 4: regions -------------------------------------------------------


class LifeArea(Row):
    __tablename__ = "life_areas"

    key: Mapped[str]
    name: Mapped[str]
    position: Mapped[int]
    anchor_x: Mapped[float] = mapped_column(Float)
    anchor_y: Mapped[float] = mapped_column(Float)


class MapLayout(Row):
    __tablename__ = "map_layouts"

    version: Mapped[int]
    parameters: Mapped[Json]


class MapPosition(Row):
    __tablename__ = "map_positions"

    node_id: Mapped[uuid.UUID] = mapped_column(_fk("nodes.id"))
    layout_id: Mapped[uuid.UUID] = mapped_column(_fk("map_layouts.id"))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    placed_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

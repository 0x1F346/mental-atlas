"""Source operations shared by the API, the tests and the evaluation harness."""

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db import atlas_store
from atlas.db.ids import new_id
from atlas.db.models import MediaFile, Run, Source
from atlas.domain.generated.vocabulary import SourceKind, SourceStatus
from atlas.pipeline import queue
from atlas.pipeline.stages import PIPELINE_VERSION, STATUS_DURING, Stage
from atlas.providers.base import BlobStore

TEXT_MIME = "text/plain; charset=utf-8"

# Pipeline order. A text source takes SEGMENT_TEXT in place of MEDIA's audio and TRANSCRIBE.
STAGE_ORDER: tuple[Stage, ...] = (
    Stage.MEDIA,
    Stage.TRANSCRIBE,
    Stage.SEGMENT_TEXT,
    Stage.SPEAKERS,
    Stage.STATEMENTS,
    Stage.CONCEPTS,
    Stage.COMMIT,
    Stage.EMBED,
    Stage.PLACE,
)


class DuplicateSource(Exception):
    def __init__(self, existing_source_id: uuid.UUID) -> None:
        super().__init__("duplicate_source")
        self.existing_source_id = existing_source_id


def original_key(user_id: uuid.UUID, source_id: uuid.UUID) -> str:
    return f"media/{user_id}/{source_id}/original"


def find_duplicate(
    session: Session, sha256: str, exclude: uuid.UUID | None = None
) -> uuid.UUID | None:
    query = select(MediaFile.source_id).where(
        MediaFile.role == "original", MediaFile.sha256 == sha256
    )
    if exclude is not None:
        query = query.where(MediaFile.source_id != exclude)
    return session.scalars(query).first()


def create_source(
    session: Session,
    user_id: uuid.UUID,
    *,
    kind: SourceKind,
    title: str,
    occurred_at: object,
    expected_names: list[str],
    mime_type: str,
) -> tuple[Source, MediaFile]:
    source = Source(
        id=new_id(),
        user_id=user_id,
        kind=kind.value,
        title=title,
        occurred_at=occurred_at,
        metadata_={"expected_names": expected_names} if expected_names else {},
    )
    session.add(source)
    session.flush()
    media = MediaFile(
        user_id=user_id,
        source_id=source.id,
        storage_key=original_key(user_id, source.id),
        mime_type=mime_type,
        role="original",
    )
    session.add(media)
    session.flush()
    return source, media


def create_text_source(
    session: Session,
    user_id: uuid.UUID,
    blobs: BlobStore,
    *,
    kind: SourceKind,
    title: str,
    occurred_at: object,
    text: str,
    expected_names: list[str] | None = None,
) -> Source:
    """Store pasted text as the source's original file and queue processing."""
    data = text.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    existing = find_duplicate(session, sha256)
    if existing is not None:
        raise DuplicateSource(existing)
    source, media = create_source(
        session,
        user_id,
        kind=kind,
        title=title,
        occurred_at=occurred_at,
        expected_names=expected_names or [],
        mime_type=TEXT_MIME,
    )
    media.sha256, media.bytes = sha256, len(data)
    blobs.put(media.storage_key, data, TEXT_MIME)
    start(session, source)
    return source


def complete_upload(session: Session, source: Source, blobs: BlobStore, workdir: Path) -> None:
    """Confirm an uploaded file: record its hash and size, refuse a duplicate, queue processing."""
    media = session.scalars(
        select(MediaFile).where(MediaFile.source_id == source.id, MediaFile.role == "original")
    ).one()
    info = blobs.head(media.storage_key)
    if info is None:
        raise FileNotFoundError(media.storage_key)
    local = workdir / "upload"
    blobs.download_to(media.storage_key, local)
    digest = hashlib.sha256()
    with local.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    existing = find_duplicate(session, sha256, exclude=source.id)
    if existing is not None:
        raise DuplicateSource(existing)
    media.sha256, media.bytes = sha256, info.bytes
    start(session, source)


def start(session: Session, source: Source) -> None:
    queue.enqueue(session, source.user_id, source.id, Stage.MEDIA)
    source.status = STATUS_DURING[Stage.MEDIA].value


def reprocess(session: Session, source: Source, stage: Stage, *, force: bool = False) -> None:
    """Run the pipeline again from `stage`: retract that stage and every later one first."""
    queue.cancel_pending(session, source.id)
    later = STAGE_ORDER[STAGE_ORDER.index(stage) :]
    runs = session.scalars(
        select(Run.id)
        .where(
            Run.source_id == source.id,
            Run.kind.in_([s.value for s in later]),
            Run.status != "retracted",
        )
        .order_by(Run.started_at.desc(), Run.id.desc())
    ).all()
    for run_id in runs:
        atlas_store.retract_run(session, run_id)
    queue.enqueue(
        session, source.user_id, source.id, stage, payload={"force": True} if force else None
    )
    source.status = STATUS_DURING[stage].value


def retract(session: Session, source_id: uuid.UUID) -> list[str]:
    """Retract a source and everything derived from it. Returns storage keys to delete."""
    source = session.get(Source, source_id)
    user_id = source.user_id if source is not None else None
    queue.cancel_pending(session, source_id)
    keys = atlas_store.retract_source(session, source_id).storage_keys
    if user_id is not None:
        # Files a stage may have written without yet recording them in the database.
        prefix = f"{user_id}/{source_id}"
        keys += [f"media/{prefix}/original", f"media/{prefix}/audio.m4a"]
        keys += [f"raw/{prefix}/transcript-v{PIPELINE_VERSION}.json"]
    return list(dict.fromkeys(keys))


def is_settled(source: Source) -> bool:
    return source.status in (
        SourceStatus.READY.value,
        SourceStatus.FAILED.value,
        SourceStatus.NEEDS_SPEAKER_CHECK.value,
    )

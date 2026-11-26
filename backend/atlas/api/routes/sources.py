"""Sources: upload, status, transcript, speaker roles, reprocessing and retraction."""

import datetime
import json
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.api.deps import AuthDep, DbDep, SettingsDep
from atlas.api.errors import ApiError
from atlas.db.models import MediaFile, Run, Segment, Source, Speaker
from atlas.db.session import user_session
from atlas.domain.generated.vocabulary import SourceKind, SourceStatus, SpeakerRole
from atlas.logging import get_logger
from atlas.pipeline import queue, sources
from atlas.pipeline.sources import DuplicateSource
from atlas.pipeline.speakers import apply_roles, valid_assignment
from atlas.pipeline.stages import STATUS_DURING, Stage
from atlas.pipeline.test_data import BlobError, parse_test_data
from atlas.providers.base import Providers
from atlas.providers.registry import get_providers

router = APIRouter(tags=["sources"])
log = get_logger("atlas.api.sources")

ProvidersDep = Annotated[Providers, Depends(get_providers)]
UPLOAD_TYPES = ("audio/", "video/", "text/plain")
# The commit, embed and place stages only replay the concepts stage's output.
REPROCESSABLE = frozenset(
    {
        Stage.MEDIA,
        Stage.TRANSCRIBE,
        Stage.SEGMENT_TEXT,
        Stage.IMPORT,
        Stage.SPEAKERS,
        Stage.STATEMENTS,
        Stage.CONCEPTS,
    }
)


class SourceCreate(BaseModel):
    kind: SourceKind
    title: str = Field(min_length=1, max_length=200)
    occurred_at: datetime.datetime
    expected_names: list[str] = Field(default_factory=list, max_length=200)
    # Either pasted text, or the content type of a file the browser will upload.
    text: str | None = Field(default=None, min_length=1)
    content_type: str | None = None
    # Or test data: concepts by type, such as {"person": [...], "feeling": [...]}.
    # See atlas/pipeline/test_data.py for the format.
    test_data: dict[str, Any] | None = None

    @model_validator(mode="after")
    def one_input(self) -> "SourceCreate":
        given = [self.text is not None, self.content_type is not None, self.test_data is not None]
        if sum(given) != 1:
            raise ValueError("give exactly one of text, content_type or test_data")
        return self


class StageOut(BaseModel):
    stage: str
    status: str
    error: str | None
    started_at: datetime.datetime
    finished_at: datetime.datetime | None


class SourceOut(BaseModel):
    id: uuid.UUID
    kind: SourceKind
    title: str
    occurred_at: datetime.datetime
    status: SourceStatus
    language: str | None
    created_at: datetime.datetime
    duration_ms: int | None = None
    audio_media_id: uuid.UUID | None = None
    stages: list[StageOut] = Field(default_factory=list)


class UploadTarget(BaseModel):
    url: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in: int


class SourceCreated(BaseModel):
    source: SourceOut
    upload: UploadTarget | None


class SpeakerOut(BaseModel):
    id: uuid.UUID
    label: str
    role: SpeakerRole | None
    method: str | None
    confidence: float | None
    first_start_ms: int | None


class SegmentOut(BaseModel):
    id: uuid.UUID
    idx: int
    speaker_id: uuid.UUID
    start_ms: int | None
    end_ms: int | None
    start_char: int
    end_char: int
    text: str


class TranscriptOut(BaseModel):
    source_id: uuid.UUID
    speakers: list[SpeakerOut]
    segments: list[SegmentOut]


class SpeakerRoles(BaseModel):
    roles: dict[uuid.UUID, SpeakerRole]


class ReprocessRequest(BaseModel):
    stage: Stage


def _source(db: Session, source_id: uuid.UUID) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise ApiError(404, "source_not_found", "No such source.")
    return source


def _out(db: Session, source: Source, with_stages: bool = False) -> SourceOut:
    audio = db.scalars(
        select(MediaFile).where(MediaFile.source_id == source.id, MediaFile.role == "audio")
    ).first()
    stages: list[StageOut] = []
    if with_stages:
        latest: dict[str, Run] = {}
        runs = db.scalars(
            select(Run).where(Run.source_id == source.id).order_by(Run.started_at, Run.id)
        )
        for run in runs:
            if run.status != "retracted":
                latest[run.kind] = run
        stages = [
            StageOut(
                stage=run.kind,
                status=run.status,
                error=run.error,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
            for run in latest.values()
        ]
    return SourceOut(
        id=source.id,
        kind=SourceKind(source.kind),
        title=source.title,
        occurred_at=source.occurred_at,
        status=SourceStatus(source.status),
        language=source.language,
        created_at=source.created_at,
        duration_ms=audio.duration_ms if audio else None,
        audio_media_id=audio.id if audio else None,
        stages=stages,
    )


def _duplicate(error: DuplicateSource) -> ApiError:
    return ApiError(
        409,
        "duplicate_source",
        "This file has already been uploaded.",
        source_id=str(error.existing_source_id),
    )


@router.post("/sources", status_code=201)
def create_source(
    body: SourceCreate, auth: AuthDep, db: DbDep, providers: ProvidersDep, settings: SettingsDep
) -> SourceCreated:
    names = [name.strip() for name in body.expected_names if name.strip()]
    if body.test_data is not None:
        try:
            parse_test_data(body.test_data)
        except BlobError as error:
            # The message names where the problem is; it never repeats what was sent.
            raise ApiError(422, "invalid_test_data", str(error)) from error
        payload = json.dumps(body.test_data, sort_keys=True).encode()
        try:
            source = sources.create_test_data_source(
                db,
                auth.user_id,
                providers.blobs,
                title=body.title,
                occurred_at=body.occurred_at,
                payload=payload,
            )
        except DuplicateSource as error:
            raise _duplicate(error) from error
        log.info("source.created", source_id=source.id, kind=source.kind, input="test_data")
        return SourceCreated(source=_out(db, source), upload=None)
    if body.text is not None:
        try:
            source = sources.create_text_source(
                db,
                auth.user_id,
                providers.blobs,
                kind=body.kind,
                title=body.title,
                occurred_at=body.occurred_at,
                text=body.text,
                expected_names=names,
            )
        except DuplicateSource as error:
            raise _duplicate(error) from error
        log.info("source.created", source_id=source.id, kind=body.kind, input="text")
        return SourceCreated(source=_out(db, source), upload=None)

    content_type = (body.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith(UPLOAD_TYPES):
        raise ApiError(415, "unsupported_media_type", "Upload audio, video or plain text.")
    source, media = sources.create_source(
        db,
        auth.user_id,
        kind=body.kind,
        title=body.title,
        occurred_at=body.occurred_at,
        expected_names=names,
        mime_type=content_type,
    )
    ttl = settings.signed_link_ttl_seconds
    upload = UploadTarget(
        url=providers.blobs.signed_upload_url(media.storage_key, content_type, ttl),
        headers={"Content-Type": content_type},
        expires_in=ttl,
    )
    log.info("source.created", source_id=source.id, kind=body.kind, input="file")
    return SourceCreated(source=_out(db, source), upload=upload)


@router.post("/sources/{source_id}/complete")
def complete_upload(source_id: uuid.UUID, auth: AuthDep, providers: ProvidersDep) -> SourceOut:
    duplicate: DuplicateSource | None = None
    with tempfile.TemporaryDirectory(prefix="atlas-") as workdir, user_session(auth.user_id) as db:
        # Locked, so two confirmations of one upload cannot both queue processing.
        source = db.get(Source, source_id, with_for_update=True)
        if source is None:
            raise ApiError(404, "source_not_found", "No such source.")
        if source.status != SourceStatus.UPLOADED.value:
            raise ApiError(409, "already_completed", "This upload was already confirmed.")
        try:
            sources.complete_upload(db, source, providers.blobs, Path(workdir))
        except FileNotFoundError as error:
            raise ApiError(409, "upload_missing", "The file has not been uploaded yet.") from error
        except DuplicateSource as error:
            # The same file is already a source: drop this one and point at the original.
            duplicate = error
            keys = sources.retract(db, source.id)
        else:
            return _out(db, source)
    for key in keys:
        providers.blobs.delete(key)
    raise _duplicate(duplicate)


@router.get("/sources")
def list_sources(db: DbDep) -> list[SourceOut]:
    rows = db.scalars(select(Source).order_by(Source.occurred_at.desc(), Source.id.desc()))
    return [_out(db, source) for source in rows]


@router.get("/sources/{source_id}")
def get_source(source_id: uuid.UUID, db: DbDep) -> SourceOut:
    return _out(db, _source(db, source_id), with_stages=True)


@router.get("/sources/{source_id}/transcript")
def get_transcript(source_id: uuid.UUID, db: DbDep) -> TranscriptOut:
    source = _source(db, source_id)
    segments = db.scalars(
        select(Segment).where(Segment.source_id == source.id).order_by(Segment.idx)
    ).all()
    first_start: dict[uuid.UUID, int | None] = {}
    for segment in segments:
        first_start.setdefault(segment.speaker_id, segment.start_ms)
    speakers = db.scalars(
        select(Speaker).where(Speaker.source_id == source.id).order_by(Speaker.provider_label)
    )
    return TranscriptOut(
        source_id=source.id,
        speakers=[
            SpeakerOut(
                id=s.id,
                label=s.provider_label,
                role=SpeakerRole(s.role) if s.role else None,
                method=s.method,
                confidence=s.confidence,
                first_start_ms=first_start.get(s.id),
            )
            for s in speakers
        ],
        segments=[
            SegmentOut(
                id=s.id,
                idx=s.idx,
                speaker_id=s.speaker_id,
                start_ms=s.start_ms,
                end_ms=s.end_ms,
                start_char=s.start_char,
                end_char=s.end_char,
                text=s.text,
            )
            for s in segments
        ],
    )


@router.put("/sources/{source_id}/speakers")
def set_speakers(source_id: uuid.UUID, body: SpeakerRoles, auth: AuthDep, db: DbDep) -> SourceOut:
    """Set or swap speaker roles. A swap reprocesses the source from the statement stage."""
    source = _source(db, source_id)
    speakers = list(db.scalars(select(Speaker).where(Speaker.source_id == source.id)))
    if not speakers:
        raise ApiError(409, "no_transcript", "This source has no transcript yet.")
    by_id = {speaker.id: speaker for speaker in speakers}
    if set(body.roles) != set(by_id):
        raise ApiError(422, "invalid_roles", "Give one role for every voice.")
    roles = {by_id[speaker_id].provider_label: role for speaker_id, role in body.roles.items()}
    if not valid_assignment({s.provider_label for s in speakers}, roles):
        raise ApiError(422, "invalid_roles", "Exactly one voice must be yours.")
    unchanged = all(
        s.role == roles[s.provider_label].value and s.method in ("owner", "model", "single")
        for s in speakers
    )
    apply_roles(db, auth.user_id, speakers, roles, "owner", 1.0)
    if source.status == SourceStatus.NEEDS_SPEAKER_CHECK.value:
        queue.enqueue(db, auth.user_id, source.id, Stage.STATEMENTS)
        source.status = STATUS_DURING[Stage.STATEMENTS].value
    elif not unchanged:
        sources.reprocess(db, source, Stage.STATEMENTS)
    log.info("source.speakers_set", source_id=source.id)
    return _out(db, source, with_stages=True)


@router.post("/sources/{source_id}/reprocess")
def reprocess(source_id: uuid.UUID, body: ReprocessRequest, db: DbDep) -> SourceOut:
    source = _source(db, source_id)
    if body.stage not in REPROCESSABLE:
        raise ApiError(422, "stage_not_reprocessable", "Reprocess from the concepts stage instead.")
    if source.status == SourceStatus.UPLOADED.value:
        raise ApiError(409, "upload_missing", "The file has not been uploaded yet.")
    has_speakers = db.scalars(select(Speaker.id).where(Speaker.source_id == source.id)).first()
    early = (Stage.MEDIA, Stage.TRANSCRIBE, Stage.SEGMENT_TEXT, Stage.IMPORT)
    if body.stage not in early and not has_speakers:
        raise ApiError(409, "no_transcript", "This source has no transcript yet.")
    sources.reprocess(db, source, body.stage)
    log.info("source.reprocess", source_id=source.id, stage=body.stage)
    return _out(db, source, with_stages=True)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: uuid.UUID, auth: AuthDep, providers: ProvidersDep) -> None:
    """Retract the source and everything derived from it, then delete its files."""
    with user_session(auth.user_id) as db:
        _source(db, source_id)
        keys = sources.retract(db, source_id)
    for key in keys:
        providers.blobs.delete(key)
    log.info("source.retracted", source_id=source_id, files=len(keys))


class MediaLink(BaseModel):
    url: str
    mime_type: str
    expires_in: int


@router.get("/media/{media_id}/link")
def media_link(
    media_id: uuid.UUID, db: DbDep, providers: ProvidersDep, settings: SettingsDep
) -> MediaLink:
    media = db.get(MediaFile, media_id)
    if media is None:
        raise ApiError(404, "media_not_found", "No such file.")
    ttl = settings.signed_link_ttl_seconds
    return MediaLink(
        url=providers.blobs.signed_download_url(media.storage_key, ttl),
        mime_type=media.mime_type,
        expires_in=ttl,
    )

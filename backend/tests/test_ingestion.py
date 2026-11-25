"""Ingestion: queue, worker, media, transcription, text and speaker roles. Invented data only."""

import datetime
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from atlas.db.models import Job, MediaFile, Node, Run, Segment, Source, Speaker, Transcript
from atlas.db.session import user_session
from atlas.domain.generated.vocabulary import SourceKind
from atlas.pipeline import queue, sources
from atlas.pipeline.handlers import HANDLERS
from atlas.pipeline.runner import StageContext, drain, work_once
from atlas.pipeline.sources import DuplicateSource
from atlas.pipeline.stages import Next, Outcome, Stage, StageError
from atlas.providers.base import Providers
from atlas.providers.fakes import FakeBlobStore, FakeTranscriber
from atlas.settings import get_settings
from tests.conftest import run_pipeline

WHEN = datetime.datetime(2026, 3, 2, 18, tzinfo=datetime.UTC)
JOURNAL = "I felt dread before the review.\n\nThen I went for a walk and it eased."
UNCLEAR_SCRIPT = [
    ("speaker_0", "Shall we start? How was it?"),
    ("speaker_1", "Fine? What do you want to know?"),
]


def upload_audio(
    user_id: uuid.UUID,
    providers: Providers,
    data: bytes,
    tmp_path: Path,
    kind: SourceKind = SourceKind.THERAPY_SESSION,
    names: list[str] | None = None,
) -> uuid.UUID:
    with user_session(user_id) as session:
        source, media = sources.create_source(
            session,
            user_id,
            kind=kind,
            title="Invented session",
            occurred_at=WHEN,
            expected_names=names or [],
            mime_type="audio/wav",
        )
        providers.blobs.put(media.storage_key, data, "audio/wav")
        sources.complete_upload(session, source, providers.blobs, tmp_path)
        return source.id


def add_journal(user_id: uuid.UUID, providers: Providers, body: str = JOURNAL) -> uuid.UUID:
    with user_session(user_id) as session:
        return sources.create_text_source(
            session,
            user_id,
            providers.blobs,
            kind=SourceKind.JOURNAL,
            title="Invented entry",
            occurred_at=WHEN,
            text=body,
        ).id


def make_due(user_id: uuid.UUID) -> None:
    """Skip the wait before a deferred or retried job runs again."""
    with user_session(user_id) as session:
        session.execute(update(Job).where(Job.status == "queued").values(run_after=WHEN))


def status_of(session: Session, source_id: uuid.UUID) -> str:
    session.expire_all()
    source = session.get(Source, source_id)
    assert source is not None
    return source.status


def test_pasted_text_reaches_segments(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    source_id = add_journal(user_id, providers)
    assert status_of(db, source_id) == "transcribing"
    run_pipeline(providers)

    segments = db.scalars(
        select(Segment).where(Segment.source_id == source_id).order_by(Segment.idx)
    ).all()
    assert [s.text for s in segments] == JOURNAL.split("\n\n")
    assert all(
        JOURNAL[s.start_char : s.end_char] == s.text and s.start_ms is None for s in segments
    )
    speaker = db.scalars(select(Speaker).where(Speaker.source_id == source_id)).one()
    me = db.scalars(select(Node).where(Node.name == "Me")).one()
    assert (speaker.role, speaker.method, speaker.person_node_id) == ("self", "single", me.id)
    kinds = db.scalars(
        select(Run.kind).where(Run.source_id == source_id).order_by(Run.started_at)
    ).all()
    assert kinds[:3] == ["media", "segment_text", "speakers"]
    assert status_of(db, source_id) == "ready"


def test_recording_reaches_a_transcript_with_correct_roles(
    db: Session, user_id: uuid.UUID, providers: Providers, audio_bytes: bytes, tmp_path: Path
) -> None:
    source_id = upload_audio(user_id, providers, audio_bytes, tmp_path, names=["Dana"])
    run_pipeline(providers)

    audio = db.scalars(
        select(MediaFile).where(MediaFile.source_id == source_id, MediaFile.role == "audio")
    ).one()
    assert audio.mime_type == "audio/mp4" and audio.duration_ms is not None
    assert 1800 <= audio.duration_ms <= 2300
    blobs = providers.blobs
    assert blobs.head(audio.storage_key) is not None
    original = db.scalars(
        select(MediaFile).where(MediaFile.source_id == source_id, MediaFile.role == "original")
    ).one()
    assert blobs.get(original.storage_key) == audio_bytes  # The original is stored untouched.

    transcript = db.scalars(select(Transcript).where(Transcript.source_id == source_id)).one()
    assert transcript.provider == "fake" and transcript.raw_response_key
    assert blobs.head(transcript.raw_response_key) is not None

    segments = db.scalars(
        select(Segment).where(Segment.source_id == source_id).order_by(Segment.idx)
    ).all()
    assert len(segments) == 6 and segments[1].text.startswith("I felt a lot of dread")
    assert segments[1].words and segments[1].start_ms is not None

    roles = {
        s.provider_label: (s.role, s.method)
        for s in db.scalars(select(Speaker).where(Speaker.source_id == source_id))
    }
    assert roles == {"speaker_0": ("therapist", "model"), "speaker_1": ("self", "model")}
    therapist = db.scalars(select(Node).where(Node.name == "My therapist")).one()
    assert therapist.run_id is None and therapist.status == "stated"
    assert status_of(db, source_id) == "ready"

    transcriber = providers.transcriber
    assert isinstance(transcriber, FakeTranscriber)
    assert transcriber.submissions[0]["key_terms"] == ["Dana"]
    assert transcriber.submissions[0]["num_speakers"] == 2


def test_unclear_roles_wait_for_the_owner(
    db: Session, user_id: uuid.UUID, providers: Providers, audio_bytes: bytes, tmp_path: Path
) -> None:
    transcriber = providers.transcriber
    assert isinstance(transcriber, FakeTranscriber)
    transcriber.script = UNCLEAR_SCRIPT
    source_id = upload_audio(user_id, providers, audio_bytes, tmp_path)
    run_pipeline(providers)

    assert status_of(db, source_id) == "needs_speaker_check"
    speakers = db.scalars(select(Speaker).where(Speaker.source_id == source_id)).all()
    assert all(s.method == "model_unconfirmed" and s.person_node_id is None for s in speakers)
    assert run_pipeline(providers) == 0  # Nothing runs until the owner answers.


def test_a_slow_provider_is_polled_without_counting_as_a_failure(
    db: Session, user_id: uuid.UUID, providers: Providers, audio_bytes: bytes, tmp_path: Path
) -> None:
    transcriber = providers.transcriber
    assert isinstance(transcriber, FakeTranscriber)
    transcriber.pending_fetches = 2
    source_id = upload_audio(user_id, providers, audio_bytes, tmp_path)
    for _ in range(3):
        run_pipeline(providers)
        make_due(user_id)
    run_pipeline(providers)

    assert status_of(db, source_id) == "ready"
    assert len(transcriber.submissions) == 1
    job = db.scalars(select(Job).where(Job.source_id == source_id, Job.stage == "transcribe")).one()
    assert (job.status, job.attempts) == ("succeeded", 1)
    runs = db.scalars(select(Run).where(Run.source_id == source_id, Run.kind == "transcribe")).all()
    assert len(runs) == 1


def test_a_worker_killed_mid_stage_resumes_that_stage_on_restart(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    settings = get_settings()
    source_id = add_journal(user_id, providers)
    work_once(HANDLERS, providers, settings)  # media
    # The worker claims the next stage and dies before finishing it.
    claimed = queue.claim(settings.worker_name, settings.job_lease_seconds)
    assert claimed is not None
    assert run_pipeline(providers) == 0  # Its lease still holds; nobody else takes the job.
    assert db.scalars(select(Segment).where(Segment.source_id == source_id)).all() == []

    assert queue.release(settings.worker_name) == 1  # What the worker does when it starts.
    run_pipeline(providers)

    assert status_of(db, source_id) == "ready"
    assert len(db.scalars(select(Segment).where(Segment.source_id == source_id)).all()) == 2
    media_runs = db.scalars(
        select(Run).where(Run.source_id == source_id, Run.kind == "media")
    ).all()
    assert len(media_runs) == 1  # The stage before it was not repeated.


def test_an_expired_lease_lets_another_worker_take_the_job(
    user_id: uuid.UUID, providers: Providers
) -> None:
    add_journal(user_id, providers)
    first = queue.claim("worker-a", 900)
    assert first is not None
    assert queue.claim("worker-b", 900) is None
    second = queue.claim("worker-b", 0)
    assert second is not None and second.job_id == first.job_id


def test_a_failed_stage_is_recorded_and_can_be_retried_alone(
    db: Session, user_id: uuid.UUID, providers: Providers, audio_bytes: bytes, tmp_path: Path
) -> None:
    def broken(ctx: StageContext) -> Outcome:
        raise StageError("invented_failure")

    source_id = upload_audio(user_id, providers, audio_bytes, tmp_path)
    drain({**HANDLERS, Stage.SPEAKERS: broken}, providers, get_settings())

    assert status_of(db, source_id) == "failed"
    run = db.scalars(select(Run).where(Run.source_id == source_id, Run.kind == "speakers")).one()
    assert (run.status, run.error) == ("failed", "invented_failure")
    # Nothing the failed stage did was kept, and the earlier stages' output is intact.
    assert len(db.scalars(select(Segment).where(Segment.source_id == source_id)).all()) == 6

    with user_session(user_id) as session:
        source = session.get(Source, source_id)
        assert source is not None
        sources.reprocess(session, source, Stage.SPEAKERS)
    run_pipeline(providers)

    assert status_of(db, source_id) == "ready"
    transcriber = providers.transcriber
    assert isinstance(transcriber, FakeTranscriber)
    assert len(transcriber.submissions) == 1  # Transcription was not repeated.


def test_an_unexpected_error_is_retried_then_gives_up(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    calls = 0

    def flaky(ctx: StageContext) -> Outcome:
        nonlocal calls
        calls += 1
        raise RuntimeError("an invented crash with private words in it")

    source_id = add_journal(user_id, providers)
    handlers = {**HANDLERS, Stage.SEGMENT_TEXT: flaky}
    for _ in range(5):
        drain(handlers, providers, get_settings())
        make_due(user_id)

    assert calls == get_settings().job_max_attempts
    assert status_of(db, source_id) == "failed"
    run = db.scalars(
        select(Run).where(Run.source_id == source_id, Run.kind == "segment_text")
    ).one()
    assert run.error == "unexpected_error"  # A code, never the exception's message.


def test_transcribing_again_reuses_the_stored_response(
    db: Session, user_id: uuid.UUID, providers: Providers, audio_bytes: bytes, tmp_path: Path
) -> None:
    source_id = upload_audio(user_id, providers, audio_bytes, tmp_path)
    run_pipeline(providers)
    with user_session(user_id) as session:
        source = session.get(Source, source_id)
        assert source is not None
        sources.reprocess(session, source, Stage.TRANSCRIBE)
    run_pipeline(providers)

    transcriber = providers.transcriber
    assert isinstance(transcriber, FakeTranscriber)
    assert len(transcriber.submissions) == 1
    assert len(db.scalars(select(Segment).where(Segment.source_id == source_id)).all()) == 6
    assert len(db.scalars(select(Transcript).where(Transcript.source_id == source_id)).all()) == 1
    assert status_of(db, source_id) == "ready"


def test_a_file_already_uploaded_is_refused(
    user_id: uuid.UUID, providers: Providers, audio_bytes: bytes, tmp_path: Path
) -> None:
    first = upload_audio(user_id, providers, audio_bytes, tmp_path)
    with pytest.raises(DuplicateSource) as error:
        upload_audio(user_id, providers, audio_bytes, tmp_path)
    assert error.value.existing_source_id == first
    add_journal(user_id, providers)
    with pytest.raises(DuplicateSource):
        add_journal(user_id, providers)


def test_another_users_identical_file_is_not_a_duplicate(
    user_id: uuid.UUID, other_user_id: uuid.UUID, providers: Providers
) -> None:
    add_journal(user_id, providers)
    add_journal(other_user_id, providers)


def test_unreadable_media_fails_with_a_code(
    db: Session, user_id: uuid.UUID, providers: Providers, tmp_path: Path
) -> None:
    source_id = upload_audio(user_id, providers, b"this is not audio", tmp_path)
    run_pipeline(providers)
    assert status_of(db, source_id) == "failed"
    run = db.scalars(select(Run).where(Run.source_id == source_id)).one()
    assert run.error == "media_unreadable"
    assert isinstance(providers.blobs, FakeBlobStore)


def test_stage_placeholder_is_only_for_m2() -> None:
    assert HANDLERS[Stage.STATEMENTS].__name__ == "_extraction_not_built"
    assert isinstance(HANDLERS[Stage.STATEMENTS](None), Next)  # type: ignore[arg-type]

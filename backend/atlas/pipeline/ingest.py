"""Ingestion stages: media, transcription and written text.

They turn any upload into the same shape: a source with ordered segments, each
with a speaker and a position.
"""

import json
import subprocess
from pathlib import Path

from sqlalchemy import delete, select

from atlas.db.models import MediaFile, Node, Segment, Speaker, Transcript
from atlas.domain.generated.vocabulary import NodeType, RecordState, SourceKind
from atlas.pipeline.runner import StageContext
from atlas.pipeline.segments import BuiltSegment, build_segments, build_text_segments
from atlas.pipeline.stages import PIPELINE_VERSION, Defer, Next, Outcome, Stage, StageError
from atlas.providers.base import TranscriptResult, Word

AUDIO_MIME = "audio/mp4"
POLL_SECONDS = 5.0
MAX_KEY_TERMS = 1000
TEXT_SPEAKER = "author"


def original_media(ctx: StageContext) -> MediaFile:
    media = ctx.session.scalars(
        select(MediaFile).where(MediaFile.source_id == ctx.source.id, MediaFile.role == "original")
    ).first()
    if media is None:
        raise StageError("original_media_missing")
    return media


def is_text(media: MediaFile) -> bool:
    return media.mime_type.startswith("text/")


def audio_key(ctx: StageContext) -> str:
    return f"media/{ctx.user_id}/{ctx.source.id}/audio.m4a"


def raw_transcript_key(ctx: StageContext) -> str:
    return f"raw/{ctx.user_id}/{ctx.source.id}/transcript-v{PIPELINE_VERSION}.json"


def _run(command: list[str]) -> str:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StageError("media_tool_failed", retryable=True) from error
    if done.returncode != 0:
        raise StageError("media_unreadable")
    return done.stdout


def media_stage(ctx: StageContext) -> Outcome:
    """Keep the original untouched and derive one mono audio file from it."""
    original = original_media(ctx)
    if is_text(original):
        return Next(Stage.SEGMENT_TEXT)
    source_path = ctx.workdir / "original"
    audio_path = ctx.workdir / "audio.m4a"
    ctx.providers.blobs.download_to(original.storage_key, source_path)
    _run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            str(audio_path),
        ]
    )
    probe = json.loads(
        _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(audio_path),
            ]
        )
    )
    duration_ms = int(float(probe["format"]["duration"]) * 1000)

    key = audio_key(ctx)
    ctx.providers.blobs.upload_from(audio_path, key, AUDIO_MIME)
    ctx.session.execute(
        delete(MediaFile).where(MediaFile.source_id == ctx.source.id, MediaFile.role == "audio")
    )
    ctx.session.add(
        MediaFile(
            user_id=ctx.user_id,
            source_id=ctx.source.id,
            storage_key=key,
            mime_type=AUDIO_MIME,
            bytes=audio_path.stat().st_size,
            duration_ms=duration_ms,
            role="audio",
        )
    )
    original.duration_ms = duration_ms
    return Next(Stage.TRANSCRIBE)


def key_terms(ctx: StageContext) -> list[str]:
    """Names the transcriber should expect: known people and groups, plus any given at upload."""
    names = list(
        ctx.session.scalars(
            select(Node.name).where(
                Node.type.in_([NodeType.PERSON.value, NodeType.GROUP.value]),
                Node.state == RecordState.ACTIVE.value,
                Node.is_system.is_(False),
            )
        )
    )
    names += [str(name) for name in ctx.source.metadata_.get("expected_names", [])]
    unique = list(dict.fromkeys(name.strip() for name in names if name.strip()))
    return unique[:MAX_KEY_TERMS]


def expected_speakers(kind: str) -> int | None:
    if kind == SourceKind.THERAPY_SESSION.value:
        return 2
    if kind == SourceKind.VOICE_NOTE.value:
        return 1
    return None


def _stored_transcript(ctx: StageContext) -> TranscriptResult | None:
    """A raw response saved by an earlier attempt, so transcription is never paid for twice."""
    key = raw_transcript_key(ctx)
    if ctx.providers.blobs.head(key) is None:
        return None
    stored = json.loads(ctx.providers.blobs.get(key))
    if stored.get("provider") != ctx.providers.transcriber.provider:
        return None
    return TranscriptResult(
        provider=stored["provider"],
        model=stored["model"],
        language=stored.get("language"),
        words=[Word(**word) for word in stored["words"]],
        raw=stored["raw"],
    )


def transcribe_stage(ctx: StageContext) -> Outcome:
    result = _stored_transcript(ctx) if not ctx.job.payload.get("force") else None
    if result is None:
        job_id = ctx.job.payload.get("provider_job")
        if job_id is None:
            audio = ctx.session.scalars(
                select(MediaFile).where(
                    MediaFile.source_id == ctx.source.id, MediaFile.role == "audio"
                )
            ).first()
            if audio is None:
                raise StageError("audio_missing")
            audio_path = ctx.workdir / "audio.m4a"
            ctx.providers.blobs.download_to(audio.storage_key, audio_path)
            job_id = ctx.providers.transcriber.submit(
                audio_path,
                key_terms=key_terms(ctx),
                num_speakers=expected_speakers(ctx.source.kind),
            )
            ctx.remember(provider_job=job_id)
        result = ctx.providers.transcriber.fetch(job_id)
        if result is None:
            return Defer(POLL_SECONDS)
        ctx.providers.blobs.put(
            raw_transcript_key(ctx),
            json.dumps(
                {
                    "provider": result.provider,
                    "model": result.model,
                    "language": result.language,
                    "words": [word.__dict__ for word in result.words],
                    "raw": result.raw,
                }
            ).encode(),
            "application/json",
        )
    if not result.words:
        raise StageError("transcript_empty")

    ctx.session.execute(delete(Transcript).where(Transcript.source_id == ctx.source.id))
    ctx.session.add(
        Transcript(
            user_id=ctx.user_id,
            source_id=ctx.source.id,
            provider=result.provider,
            model=result.model,
            raw_response_key=raw_transcript_key(ctx),
            pipeline_version=PIPELINE_VERSION,
            run_id=ctx.run.id,
        )
    )
    ctx.source.language = result.language
    store_segments(ctx, build_segments(result.words))
    return Next(Stage.SPEAKERS, model=result.model)


def store_segments(ctx: StageContext, built: list[BuiltSegment]) -> None:
    """Replace the source's speakers and segments. Anything extracted from them goes too."""
    ctx.session.execute(delete(Speaker).where(Speaker.source_id == ctx.source.id))
    ctx.session.flush()
    speakers: dict[str, Speaker] = {}
    for label in dict.fromkeys(segment.speaker for segment in built):
        speakers[label] = Speaker(
            user_id=ctx.user_id, source_id=ctx.source.id, provider_label=label
        )
        ctx.session.add(speakers[label])
    ctx.session.flush()
    for idx, segment in enumerate(built):
        ctx.session.add(
            Segment(
                user_id=ctx.user_id,
                source_id=ctx.source.id,
                speaker_id=speakers[segment.speaker].id,
                idx=idx,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                start_char=segment.start_char,
                end_char=segment.end_char,
                text=segment.text,
                words=segment.words or None,
            )
        )
    ctx.session.flush()


def segment_text_stage(ctx: StageContext) -> Outcome:
    """Written text needs no transcription: paragraphs become segments."""
    original = original_media(ctx)
    try:
        text = ctx.providers.blobs.get(original.storage_key).decode("utf-8")
    except UnicodeDecodeError as error:
        raise StageError("text_not_utf8") from error
    built = build_text_segments(text, speaker=TEXT_SPEAKER)
    if not built:
        raise StageError("text_empty")
    store_segments(ctx, built)
    return Next(Stage.SPEAKERS)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")

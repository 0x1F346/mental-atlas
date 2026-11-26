"""Pipeline stages, their order, and what each one means for a source's status."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from atlas.domain.generated.vocabulary import SourceStatus

# Raise when a stage's behaviour changes in a way that should replace earlier output.
PIPELINE_VERSION = 1


class Stage(StrEnum):
    MEDIA = "media"
    TRANSCRIBE = "transcribe"
    SEGMENT_TEXT = "segment_text"
    IMPORT = "import"
    SPEAKERS = "speakers"
    STATEMENTS = "statements"
    CONCEPTS = "concepts"
    COMMIT = "commit"
    EMBED = "embed"
    PLACE = "place"


# The status a source shows while each stage is queued or running.
STATUS_DURING: dict[Stage, SourceStatus] = {
    Stage.MEDIA: SourceStatus.TRANSCRIBING,
    Stage.TRANSCRIBE: SourceStatus.TRANSCRIBING,
    Stage.SEGMENT_TEXT: SourceStatus.TRANSCRIBING,
    Stage.IMPORT: SourceStatus.EXTRACTING,
    Stage.SPEAKERS: SourceStatus.TRANSCRIBING,
    Stage.STATEMENTS: SourceStatus.EXTRACTING,
    Stage.CONCEPTS: SourceStatus.EXTRACTING,
    Stage.COMMIT: SourceStatus.EXTRACTING,
    Stage.EMBED: SourceStatus.PLACING,
    Stage.PLACE: SourceStatus.PLACING,
}

# Stages whose runs write to the atlas (layers 2 to 4). Reprocessing from one of these
# retracts it and every later one.
EXTRACTION_STAGES: tuple[Stage, ...] = (
    Stage.STATEMENTS,
    Stage.CONCEPTS,
    Stage.COMMIT,
    Stage.EMBED,
    Stage.PLACE,
)


@dataclass(frozen=True)
class Next:
    """The stage finished; queue this one next (None ends the pipeline: the source is ready)."""

    stage: Stage | None
    usage: dict[str, Any] = field(default_factory=dict)
    raw_output: dict[str, Any] | None = None
    model: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True)
class Defer:
    """Not finished yet (a provider is still working). Run this stage again after a delay."""

    seconds: float


@dataclass(frozen=True)
class Wait:
    """Finished, but the pipeline pauses until the owner acts."""

    status: SourceStatus


type Outcome = Next | Defer | Wait


class StageError(Exception):
    """A stage failed. `code` is safe to log and to show; no content is attached."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable

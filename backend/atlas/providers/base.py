"""Interfaces for every outside provider (design rule 6).

The pipeline depends only on these protocols. Each has one real adapter and one
fake; tests and local development without keys use the fakes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# --- Blob storage -----------------------------------------------------------


@dataclass(frozen=True)
class BlobInfo:
    bytes: int
    content_type: str | None


class BlobStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def head(self, key: str) -> BlobInfo | None: ...
    def delete(self, key: str) -> None: ...
    def download_to(self, key: str, path: Path) -> None: ...
    def upload_from(self, path: Path, key: str, content_type: str) -> None: ...
    def signed_upload_url(self, key: str, content_type: str, ttl_seconds: int) -> str: ...
    def signed_download_url(self, key: str, ttl_seconds: int) -> str: ...


# --- Transcription ----------------------------------------------------------


@dataclass(frozen=True)
class Word:
    text: str
    start_ms: int
    end_ms: int
    speaker: str


@dataclass(frozen=True)
class TranscriptResult:
    provider: str
    model: str
    language: str | None
    words: list[Word]
    # The provider's response, kept so results can be re-derived without paying again.
    raw: dict[str, Any]


class Transcriber(Protocol):
    """Submit-then-fetch, so the worker never holds a connection open for a long file.

    An adapter whose provider answers directly may finish the work in `submit` and
    return the result from the first `fetch`.
    """

    provider: str

    def submit(
        self, audio_path: Path, *, key_terms: list[str], num_speakers: int | None
    ) -> str: ...

    def fetch(self, job_id: str) -> TranscriptResult | None:
        """The transcript, or None while the provider is still working."""
        ...


# --- Extraction model -------------------------------------------------------


@dataclass(frozen=True)
class TextBlock:
    text: str
    # Marks the end of a prefix worth caching (the transcript, the vocabulary block).
    cache: bool = False


@dataclass(frozen=True)
class ToolCall:
    """One schema-constrained call: the model must answer through `tool`."""

    model: str
    system: list[TextBlock]
    user: list[TextBlock]
    tool: dict[str, Any]
    max_tokens: int = 8000
    # Names what the call is for, so a fake can answer without parsing prompts.
    purpose: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    data: dict[str, Any]
    model: str
    usage: dict[str, int]


class ExtractionModel(Protocol):
    def call(self, request: ToolCall) -> ToolResult: ...


# --- Embeddings -------------------------------------------------------------


class Embedder(Protocol):
    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


# --- Bundle -----------------------------------------------------------------


@dataclass(frozen=True)
class Providers:
    blobs: BlobStore
    transcriber: Transcriber
    extraction: ExtractionModel
    embedder: Embedder

"""Fake providers. They make no outside call and are deterministic.

Tests use them, and so does local development when ATLAS_PROVIDERS=fake.
"""

import hashlib
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atlas.providers.base import (
    BlobInfo,
    ToolCall,
    ToolResult,
    TranscriptResult,
    Word,
)


class FakeBlobStore:
    """Blobs held in memory. Signed links use a memory:// scheme no browser can follow."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get(self, key: str) -> bytes:
        return self.objects[key][0]

    def head(self, key: str) -> BlobInfo | None:
        if key not in self.objects:
            return None
        data, content_type = self.objects[key]
        return BlobInfo(bytes=len(data), content_type=content_type)

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def download_to(self, key: str, path: Path) -> None:
        path.write_bytes(self.get(key))

    def upload_from(self, path: Path, key: str, content_type: str) -> None:
        self.put(key, path.read_bytes(), content_type)

    def signed_upload_url(self, key: str, content_type: str, ttl_seconds: int) -> str:
        return f"memory://upload/{key}?ttl={ttl_seconds}"

    def signed_download_url(self, key: str, ttl_seconds: int) -> str:
        return f"memory://download/{key}?ttl={ttl_seconds}"


# An invented two-voice exchange, used when no script is supplied for the audio.
DEFAULT_SCRIPT: list[tuple[str, str]] = [
    ("speaker_0", "So what has been on your mind since we last spoke?"),
    ("speaker_1", "I felt a lot of dread before the review with Dana on Monday."),
    ("speaker_0", "What happened right before the dread arrived?"),
    ("speaker_1", "I reread her message and then I went quiet and stopped replying to her."),
    ("speaker_0", "It sounds like you expect to be found out."),
    ("speaker_1", "Maybe. I want to stop avoiding her and just answer."),
]


class FakeTranscriber:
    """Turns a script of (speaker label, sentence) pairs into word-level output.

    `pending_fetches` makes the first fetches return None, to exercise polling.
    """

    provider = "fake"

    def __init__(
        self,
        script: list[tuple[str, str]] | None = None,
        *,
        model: str = "fake-transcriber",
        pending_fetches: int = 0,
    ) -> None:
        self.script = script or DEFAULT_SCRIPT
        self.model = model
        self.pending_fetches = pending_fetches
        self.submissions: list[dict[str, Any]] = []
        self._pending: dict[str, int] = {}

    def submit(self, audio_path: Path, *, key_terms: list[str], num_speakers: int | None) -> str:
        job_id = f"fake-job-{len(self.submissions) + 1}"
        self.submissions.append(
            {"job_id": job_id, "key_terms": list(key_terms), "num_speakers": num_speakers}
        )
        self._pending[job_id] = self.pending_fetches
        return job_id

    def fetch(self, job_id: str) -> TranscriptResult | None:
        if self._pending.get(job_id, 0) > 0:
            self._pending[job_id] -= 1
            return None
        words: list[Word] = []
        clock = 0
        for speaker, sentence in self.script:
            for token in sentence.split():
                words.append(Word(text=token, start_ms=clock, end_ms=clock + 300, speaker=speaker))
                clock += 350
            clock += 600
        raw = {
            "language_code": "en",
            "words": [
                {
                    "text": w.text,
                    "start": w.start_ms / 1000,
                    "end": w.end_ms / 1000,
                    "speaker_id": w.speaker,
                    "type": "word",
                }
                for w in words
            ],
        }
        return TranscriptResult(
            provider=self.provider, model=self.model, language="en", words=words, raw=raw
        )


_TOKEN = re.compile(r"[a-z0-9']+")


class FakeEmbedder:
    """Hashed bag-of-words vectors: deterministic, and similar texts land close together."""

    def __init__(self, dimension: int = 256, model: str = "fake-embedding") -> None:
        self.model = model
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _TOKEN.findall(text.casefold()):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


Handler = Callable[[ToolCall], dict[str, Any]]


class FakeExtractionModel:
    """Answers tool calls from handlers keyed by `ToolCall.purpose`.

    The default handlers live in atlas.pipeline.fake_extraction; tests may pass
    their own to script exact model output, including malformed output.
    """

    def __init__(self, handlers: dict[str, Handler] | None = None) -> None:
        self.handlers: dict[str, Handler] = dict(handlers or {})
        self.calls: list[ToolCall] = []

    def call(self, request: ToolCall) -> ToolResult:
        self.calls.append(request)
        handler = self.handlers.get(request.purpose)
        if handler is None:
            raise LookupError(f"no fake handler for purpose {request.purpose!r}")
        data = handler(request)
        size = sum(len(block.text) for block in [*request.system, *request.user]) // 4
        return ToolResult(
            data=data, model=request.model, usage={"input_tokens": size, "output_tokens": 0}
        )

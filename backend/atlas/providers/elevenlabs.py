"""ElevenLabs Scribe adapter (batch speech-to-text with speaker separation).

API details were checked against the ElevenLabs API reference on 2026-11-25:
POST /v1/speech-to-text (multipart) and GET /v1/speech-to-text/transcripts/{id}.

Two modes, chosen by settings.transcription_mode:
  direct  one request that returns the transcript. `submit` does the work and
          `fetch` hands the result back.
  poll    the request is sent with webhook=true, which returns a transcription id
          early; `fetch` then asks for the transcript by id until it exists. The
          reference does not document the still-processing response, so any
          non-200 answer other than an auth error is read as "not ready yet".
"""

import re
from pathlib import Path
from typing import Any

import httpx

from atlas.pipeline.stages import StageError
from atlas.providers.base import TranscriptResult, Word

BASE_URL = "https://api.elevenlabs.io"
MAX_KEYTERMS = 1000
_FORBIDDEN = re.compile(r"[<>{}\[\]\\]")


def clean_keyterms(terms: list[str]) -> list[str]:
    """Apply the documented limits: 1,000 terms, 50 characters and 5 words each."""
    cleaned: list[str] = []
    for term in terms:
        term = _FORBIDDEN.sub("", term).strip()
        if term and len(term) <= 50 and len(term.split()) <= 5 and term not in cleaned:
            cleaned.append(term)
    return cleaned[:MAX_KEYTERMS]


def parse_response(raw: dict[str, Any], model: str) -> TranscriptResult:
    """Keep spoken words only; spacing tokens and audio events are dropped."""
    words: list[Word] = []
    last_end = 0
    for item in raw.get("words", []):
        if item.get("type", "word") != "word" or not str(item.get("text", "")).strip():
            continue
        start = item.get("start")
        end = item.get("end")
        start_ms = round(start * 1000) if start is not None else last_end
        end_ms = round(end * 1000) if end is not None else start_ms
        last_end = end_ms
        words.append(
            Word(
                text=str(item["text"]).strip(),
                start_ms=start_ms,
                end_ms=end_ms,
                speaker=str(item.get("speaker_id") or "speaker_0"),
            )
        )
    return TranscriptResult(
        provider="elevenlabs", model=model, language=raw.get("language_code"), words=words, raw=raw
    )


class ElevenLabsTranscriber:
    provider = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        mode: str = "direct",
        zero_retention: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        self._mode = mode
        self._zero_retention = zero_retention
        self._client = client or httpx.Client(
            base_url=BASE_URL,
            headers={"xi-api-key": api_key},
            timeout=httpx.Timeout(1800, connect=30),
        )
        self._direct: dict[str, TranscriptResult] = {}

    def _check(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise StageError("transcriber_auth_failed")
        if response.status_code == 429 or response.status_code >= 500:
            raise StageError("transcriber_unavailable", retryable=True)
        if response.status_code >= 400:
            raise StageError("transcriber_rejected_request")

    def submit(self, audio_path: Path, *, key_terms: list[str], num_speakers: int | None) -> str:
        data: dict[str, Any] = {
            "model_id": self._model,
            "diarize": "true",
            "timestamps_granularity": "word",
        }
        if num_speakers:
            data["num_speakers"] = str(num_speakers)
        terms = clean_keyterms(key_terms)
        if terms:
            data["keyterms"] = terms
        if self._mode == "poll":
            data["webhook"] = "true"
        params = {"enable_logging": "false"} if self._zero_retention else {}
        try:
            with audio_path.open("rb") as handle:
                response = self._client.post(
                    "/v1/speech-to-text",
                    params=params,
                    data=data,
                    files={"file": (audio_path.name, handle, "audio/mp4")},
                )
        except httpx.HTTPError as error:
            raise StageError("transcriber_unavailable", retryable=True) from error
        self._check(response)
        body = response.json()
        if self._mode == "poll":
            return str(body["transcription_id"])
        job_id = str(body.get("transcription_id") or f"direct-{len(self._direct) + 1}")
        self._direct[job_id] = parse_response(body, self._model)
        return job_id

    def fetch(self, job_id: str) -> TranscriptResult | None:
        if job_id in self._direct:
            return self._direct.pop(job_id)
        try:
            response = self._client.get(f"/v1/speech-to-text/transcripts/{job_id}")
        except httpx.HTTPError as error:
            raise StageError("transcriber_unavailable", retryable=True) from error
        if response.status_code in (401, 403):
            raise StageError("transcriber_auth_failed")
        if response.status_code != 200:
            return None
        body = response.json()
        if "words" not in body:
            return None
        return parse_response(body, self._model)

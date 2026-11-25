"""The ElevenLabs adapter, against a response in the documented shape. No live call."""

import json
from pathlib import Path

import httpx
import pytest

from atlas.pipeline.segments import build_segments
from atlas.pipeline.stages import StageError
from atlas.providers.elevenlabs import ElevenLabsTranscriber, clean_keyterms, parse_response

RECORDED = json.loads(
    (Path(__file__).parent / "recorded/elevenlabs_scribe_synthetic.json").read_text()
)


def transcriber(
    handler: httpx.MockTransport, mode: str = "direct", **kwargs: bool
) -> ElevenLabsTranscriber:
    client = httpx.Client(base_url="https://api.elevenlabs.io", transport=handler)
    return ElevenLabsTranscriber("invented-key", "scribe_v3", mode=mode, client=client, **kwargs)


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    path = tmp_path / "audio.m4a"
    path.write_bytes(b"not real audio")
    return path


def test_response_becomes_words_and_segments() -> None:
    result = parse_response(RECORDED, "scribe_v3")
    assert (result.provider, result.model, result.language) == ("elevenlabs", "scribe_v3", "en")
    assert [w.text for w in result.words] == [
        "How", "was", "the", "week?", "I", "felt", "dread", "before", "the", "review.",
    ]  # fmt: skip
    assert (result.words[0].start_ms, result.words[0].end_ms) == (100, 300)
    assert result.words[-1].start_ms == 3450  # A missing time falls back to the previous end.
    assert result.raw is RECORDED
    segments = build_segments(result.words)
    assert [(s.speaker, s.text) for s in segments] == [
        ("speaker_0", "How was the week?"),
        ("speaker_1", "I felt dread before the review."),
    ]


def test_direct_mode_sends_the_documented_request(audio: Path) -> None:
    seen: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode("latin-1")
        return httpx.Response(200, json=RECORDED)

    client = transcriber(httpx.MockTransport(handle), zero_retention=True)
    job = client.submit(audio, key_terms=["Dana", "x" * 60, "Dana"], num_speakers=2)
    result = client.fetch(job)

    assert result is not None and len(result.words) == 10
    assert seen["url"] == "https://api.elevenlabs.io/v1/speech-to-text?enable_logging=false"
    for field, value in (
        ("model_id", "scribe_v3"), ("diarize", "true"), ("num_speakers", "2"),
        ("timestamps_granularity", "word"), ("keyterms", "Dana"),
    ):  # fmt: skip
        assert f'name="{field}"\r\n\r\n{value}\r\n' in seen["body"]
    assert seen["body"].count('name="keyterms"') == 1
    assert 'name="webhook"' not in seen["body"]


def test_poll_mode_waits_until_the_transcript_exists(audio: Path) -> None:
    answers = [httpx.Response(404, json={}), httpx.Response(200, json=RECORDED)]

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert 'name="webhook"\r\n\r\ntrue' in request.content.decode("latin-1")
            return httpx.Response(200, json={"message": "ok", "transcription_id": "abc"})
        assert request.url.path == "/v1/speech-to-text/transcripts/abc"
        return answers.pop(0)

    client = transcriber(httpx.MockTransport(handle), mode="poll")
    job = client.submit(audio, key_terms=[], num_speakers=None)
    assert job == "abc"
    assert client.fetch(job) is None
    result = client.fetch(job)
    assert result is not None and result.words[0].text == "How"


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "transcriber_auth_failed", False),
        (429, "transcriber_unavailable", True),
        (503, "transcriber_unavailable", True),
        (422, "transcriber_rejected_request", False),
    ],
)
def test_errors_become_codes(audio: Path, status: int, code: str, retryable: bool) -> None:
    client = transcriber(
        httpx.MockTransport(lambda _: httpx.Response(status, json={"detail": "x"}))
    )
    with pytest.raises(StageError) as error:
        client.submit(audio, key_terms=[], num_speakers=None)
    assert (error.value.code, error.value.retryable) == (code, retryable)


def test_keyterms_respect_the_documented_limits() -> None:
    terms = ["Dana", "  Dana ", "a b c d e f", "x" * 51, "Sam [work]", ""]
    assert clean_keyterms(terms) == ["Dana", "Sam work"]
    assert len(clean_keyterms([f"name{i}" for i in range(1200)])) == 1000

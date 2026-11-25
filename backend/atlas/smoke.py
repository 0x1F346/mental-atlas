"""Live smoke tests, one per provider adapter. Run by hand with `make smoke`.

These make real, paid calls using invented material only: a one-line prompt, the
synthetic two-voice recording and one invented sentence. Ask the owner first.

    python -m atlas.smoke                 run every adapter that is configured
    python -m atlas.smoke --record        also save the transcription response as the
                                          recorded fixture for tests/test_elevenlabs.py
"""

import argparse
import json
import sys
from collections.abc import Callable

from atlas.pipeline.stages import StageError
from atlas.providers.anthropic_model import AnthropicExtractionModel
from atlas.providers.base import TextBlock, ToolCall
from atlas.providers.elevenlabs import ElevenLabsTranscriber
from atlas.providers.embeddings_http import HttpEmbedder
from atlas.settings import REPO_ROOT, Settings, get_settings

RECORDING = REPO_ROOT / "evals/fixtures/synthetic/audio/two_voice_session.m4a"
RECORDED = REPO_ROOT / "backend/tests/recorded/elevenlabs_scribe_synthetic.json"
TOOL = {
    "name": "answer",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"type": "boolean"}},
    },
}


def claude(settings: Settings, model: str) -> str:
    key = settings.anthropic_api_key
    adapter = AnthropicExtractionModel(
        key.get_secret_value() if key else None,
        effort_model=settings.extraction_model,
        effort=settings.extraction_effort,
        fallbacks=settings.extraction_fallbacks,
    )
    result = adapter.call(
        ToolCall(
            model, [TextBlock("Reply through the schema.")], [TextBlock("Set ok to true.")], TOOL
        )
    )
    return f"model={result.model} ok={result.data.get('ok')} tokens={sum(result.usage.values())}"


def elevenlabs(settings: Settings, record: bool) -> str:
    if settings.elevenlabs_api_key is None:
        return "skipped: ATLAS_ELEVENLABS_API_KEY is not set"
    adapter = ElevenLabsTranscriber(
        settings.elevenlabs_api_key.get_secret_value(),
        settings.transcription_model,
        mode=settings.transcription_mode,
        zero_retention=settings.transcription_zero_retention,
    )
    job = adapter.submit(RECORDING, key_terms=["Dana"], num_speakers=2)
    result = adapter.fetch(job)
    if result is None:
        return f"submitted as {job}; not ready yet (poll mode): run again to fetch"
    if record:
        raw = {"_note": "Recorded by `make smoke` from the synthetic two-voice clip.", **result.raw}
        RECORDED.write_text(json.dumps(raw, indent=1) + "\n")
    speakers = sorted({word.speaker for word in result.words})
    return (
        f"model={result.model} words={len(result.words)} speakers={len(speakers)} recorded={record}"
    )


def embeddings(settings: Settings) -> str:
    if not (settings.embedding_base_url and settings.embedding_api_key):
        return "skipped: no embedding provider configured (D-014)"
    adapter = HttpEmbedder(
        settings.embedding_base_url,
        settings.embedding_api_key.get_secret_value(),
        settings.embedding_model,
        settings.embedding_dimension,
    )
    vectors = adapter.embed(["an invented sentence about nothing"])
    matches = len(vectors[0]) == settings.embedding_dimension
    return f"model={adapter.model} dimension={len(vectors[0])} matches_setting={matches}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    checks: list[tuple[str, Callable[[], str]]] = [
        ("claude extraction", lambda: claude(settings, settings.extraction_model)),
        ("claude small", lambda: claude(settings, settings.small_model)),
        ("elevenlabs", lambda: elevenlabs(settings, args.record)),
        ("embeddings", lambda: embeddings(settings)),
    ]
    failed = False
    for name, check in checks:
        try:
            outcome = check()
        except StageError as error:
            outcome, failed = f"FAILED: {error.code}", True
        sys.stdout.write(f"{name:<20}{outcome}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

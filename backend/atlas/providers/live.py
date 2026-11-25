"""Real provider adapters, chosen when ATLAS_PROVIDERS=live."""

from atlas.providers.anthropic_model import AnthropicExtractionModel
from atlas.providers.base import BlobStore, Embedder, Providers
from atlas.providers.elevenlabs import ElevenLabsTranscriber
from atlas.providers.embeddings_http import HttpEmbedder
from atlas.providers.fakes import FakeEmbedder
from atlas.settings import Settings


class ProviderConfigError(RuntimeError):
    """A live provider is selected but not configured."""


def build_live_providers(settings: Settings, blobs: BlobStore) -> Providers:
    if settings.elevenlabs_api_key is None:
        raise ProviderConfigError("ATLAS_ELEVENLABS_API_KEY is not set")
    embedder: Embedder
    if settings.embedding_base_url and settings.embedding_api_key:
        embedder = HttpEmbedder(
            settings.embedding_base_url,
            settings.embedding_api_key.get_secret_value(),
            settings.embedding_model,
            settings.embedding_dimension,
        )
    elif settings.embedding_model == "fake-embedding":
        # No embedding provider chosen yet: the local hashed embedder sends nothing outside.
        embedder = FakeEmbedder()
    else:
        raise ProviderConfigError(
            "ATLAS_EMBEDDING_BASE_URL and ATLAS_EMBEDDING_API_KEY are not set"
        )
    key = settings.anthropic_api_key
    return Providers(
        blobs=blobs,
        transcriber=ElevenLabsTranscriber(
            settings.elevenlabs_api_key.get_secret_value(),
            settings.transcription_model,
            mode=settings.transcription_mode,
            zero_retention=settings.transcription_zero_retention,
        ),
        # With no key set, the SDK falls back to its own credential chain.
        extraction=AnthropicExtractionModel(
            key.get_secret_value() if key else None,
            effort_model=settings.extraction_model,
            effort=settings.extraction_effort,
            fallbacks=settings.extraction_fallbacks,
        ),
        embedder=embedder,
    )

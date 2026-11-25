"""Builds the provider bundle from settings. The only place adapters are chosen."""

from atlas.providers.base import BlobStore, Providers
from atlas.providers.fakes import (
    FakeBlobStore,
    FakeEmbedder,
    FakeExtractionModel,
    FakeTranscriber,
)
from atlas.settings import Settings, get_settings

_providers: Providers | None = None


def build_providers(settings: Settings) -> Providers:
    blobs: BlobStore
    if settings.blob_store == "memory":
        blobs = FakeBlobStore()
    else:
        from atlas.providers.blob_s3 import S3BlobStore

        blobs = S3BlobStore(settings)

    if settings.providers == "live":
        from atlas.providers.live import build_live_providers

        return build_live_providers(settings, blobs)

    from atlas.pipeline.fake_extraction import default_handlers

    return Providers(
        blobs=blobs,
        transcriber=FakeTranscriber(),
        extraction=FakeExtractionModel(default_handlers()),
        embedder=FakeEmbedder(),
    )


def get_providers() -> Providers:
    global _providers
    if _providers is None:
        _providers = build_providers(get_settings())
    return _providers


def set_providers(providers: Providers | None) -> None:
    """Replace the bundle (tests), or clear it so it is rebuilt from settings."""
    global _providers
    _providers = providers

"""Real provider adapters, chosen when ATLAS_PROVIDERS=live."""

from atlas.providers.base import BlobStore, Providers
from atlas.settings import Settings


def build_live_providers(settings: Settings, blobs: BlobStore) -> Providers:
    raise NotImplementedError("live adapters arrive in M2-T5 and M3")

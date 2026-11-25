from pathlib import Path

from atlas.providers.fakes import FakeBlobStore, FakeEmbedder, FakeTranscriber
from atlas.providers.registry import build_providers
from atlas.settings import Settings


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_blob_store_round_trip(tmp_path: Path) -> None:
    blobs = FakeBlobStore()
    blobs.put("a/b", b"hello", "text/plain")
    info = blobs.head("a/b")
    assert info is not None and info.bytes == 5 and info.content_type == "text/plain"
    target = tmp_path / "out"
    blobs.download_to("a/b", target)
    assert target.read_bytes() == b"hello"
    assert blobs.signed_download_url("a/b", 300).startswith("memory://")
    blobs.delete("a/b")
    assert blobs.head("a/b") is None


def test_fake_transcriber_supports_polling(tmp_path: Path) -> None:
    transcriber = FakeTranscriber(
        [("speaker_0", "Hello there."), ("speaker_1", "Hi.")], pending_fetches=1
    )
    job = transcriber.submit(tmp_path / "x.m4a", key_terms=["Dana"], num_speakers=2)
    assert transcriber.fetch(job) is None
    result = transcriber.fetch(job)
    assert result is not None
    assert [w.text for w in result.words] == ["Hello", "there.", "Hi."]
    assert {w.speaker for w in result.words} == {"speaker_0", "speaker_1"}
    assert transcriber.submissions[0]["key_terms"] == ["Dana"]


def test_fake_embedder_is_deterministic_and_places_similar_text_closer() -> None:
    embedder = FakeEmbedder(dimension=128)
    a, b, c = embedder.embed(
        ["dread before the review", "dread before a review", "a walk by the sea"]
    )
    assert len(a) == 128
    assert embedder.embed(["dread before the review"])[0] == a
    assert cosine(a, b) > cosine(a, c)


def test_settings_choose_fakes_by_default() -> None:
    providers = build_providers(Settings(_env_file=None, blob_store="memory"))
    assert isinstance(providers.blobs, FakeBlobStore)
    assert isinstance(providers.transcriber, FakeTranscriber)

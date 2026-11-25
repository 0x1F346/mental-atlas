import re

from atlas.settings import ENV_EXAMPLE_FILE, Settings


def _settings(**overrides: object) -> Settings:
    # Never read the developer's local env file from tests.
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_defaults_load_without_env_file() -> None:
    settings = _settings()
    assert settings.providers == "fake"
    assert settings.signed_link_ttl_seconds <= 300


def test_env_example_lists_every_variable_and_no_secrets() -> None:
    text = ENV_EXAMPLE_FILE.read_text()
    listed = set(re.findall(r"^#?\s*(ATLAS_[A-Z0-9_]+)=", text, flags=re.MULTILINE))
    expected = {f"ATLAS_{name.upper()}" for name in Settings.model_fields}
    assert listed == expected
    for line in text.splitlines():
        if re.match(r"^#?\s*ATLAS_[A-Z0-9_]*(KEY|PASSWORD)=", line):
            assert line.rstrip().endswith("="), "secret variables must be listed without a value"


def test_secrets_do_not_appear_in_repr() -> None:
    settings = _settings(anthropic_api_key="sk-test-value")
    assert "sk-test-value" not in repr(settings)

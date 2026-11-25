"""Typed settings, read once from environment variables.

Every variable is prefixed ATLAS_ and listed in the example env file at the
repository root. Defaults match docker-compose.yml, so a fresh clone runs
without any local env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE_FILE = REPO_ROOT / ".env.example"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", env_file=ENV_FILE, extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # Postgres. The app role cannot bypass row-level security; the owner role runs migrations.
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://atlas_app:atlas_app@localhost:54329/atlas"
    )
    database_owner_url: SecretStr = SecretStr(
        "postgresql+psycopg://atlas_owner:atlas_owner@localhost:54329/atlas"
    )

    # S3-compatible object storage.
    s3_endpoint_url: str = "http://localhost:9100"
    s3_region: str = "us-east-1"
    s3_bucket: str = "atlas"
    s3_access_key: SecretStr = SecretStr("atlas")
    s3_secret_key: SecretStr = SecretStr("atlas-local-secret")
    signed_link_ttl_seconds: int = 300
    # "memory" keeps blobs in process memory; only tests use it.
    blob_store: Literal["s3", "memory"] = "s3"

    # Providers. "fake" uses the in-repo fakes and makes no outside call.
    providers: Literal["fake", "live"] = "fake"
    anthropic_api_key: SecretStr | None = None
    elevenlabs_api_key: SecretStr | None = None
    embedding_api_key: SecretStr | None = None

    # Model ids live here, never in code.
    extraction_model: str = "claude-sonnet-5-5"
    small_model: str = "claude-haiku-5-5"
    transcription_model: str = "scribe_v3"
    embedding_model: str = "fake-embedding"
    embedding_dimension: int = 1024

    # Pipeline thresholds (starting values from the plan; tuned in the evaluation harness).
    speaker_role_confidence_threshold: float = 0.9
    match_accept_threshold: float = 0.90
    match_review_threshold: float = 0.75

    # Sign-in.
    session_cookie_name: str = "atlas_session"
    session_ttl_hours: int = 24 * 14
    cookie_secure: bool = False
    login_rate_limit_per_minute: int = 5
    seed_user_email: str = "owner@example.com"
    seed_user_password: SecretStr | None = None

    web_origin: str = "http://localhost:5173"

    # Worker.
    worker_name: str = "worker-1"
    worker_poll_seconds: float = 1.0
    job_lease_seconds: int = 900
    job_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()

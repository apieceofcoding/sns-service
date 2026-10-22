from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    # SNS database: accounts and posts stay here. Recommendation database: vectors and jobs.
    source_database_url: str = "postgresql://snsuser:snspassword@localhost:5432/snsdb"
    database_url: str = "postgresql://recommend:recommend@localhost:55432/recommend"
    redis_url: str = "redis://localhost:56379/0"
    cursor_secret: SecretStr = Field(
        default=SecretStr("course-local-cursor-secret"), min_length=1, max_length=512
    )
    model_mode: Literal["fixture", "live", "record", "replay"] = "live"
    model_api_key: SecretStr = SecretStr("ollama")
    model_base_url: str = "http://localhost:11434/v1"
    model_timeout_seconds: float = 120
    embedding_model: str = "qwen3-embedding:0.6b"
    rerank_model: str = "sns-reranker"
    dimensions: int = Field(default=768, ge=5)
    snapshot_ttl: int = Field(default=1800, gt=0)
    refresh_seconds: int = Field(default=300, gt=0)
    lease_seconds: int = Field(default=120, gt=0)
    daily_call_limit: int = Field(default=20, ge=0)
    minimum_refresh_seconds: int = Field(default=60, ge=0)
    input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    recordings_dir: str = "recordings"

    @field_validator("cursor_secret")
    @classmethod
    def validate_cursor_secret(cls, token: SecretStr) -> SecretStr:
        if any(not 33 <= ord(char) <= 126 for char in token.get_secret_value()):
            raise ValueError("cursor secret must contain visible ASCII characters only")
        return token


@lru_cache
def settings() -> Settings:
    return Settings()

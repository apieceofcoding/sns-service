from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # SNS database: accounts and posts stay here. Recommend database: user events and vectors.
    source_database_url: str = "postgresql://snsuser:snspassword@localhost:5432/snsdb"
    database_url: str = "postgresql://recommend:recommend@localhost:55432/recommend"
    redis_url: str = "redis://localhost:56379/0"
    cursor_secret: str = "course-local-cursor-secret"
    # fixture: keyword vectors for tests. live: the embedding model API.
    model_mode: Literal["fixture", "live"] = "live"
    model_api_key: SecretStr = SecretStr("ollama")
    model_base_url: str = "http://localhost:11434/v1"
    model_timeout_seconds: float = 120
    embedding_model: str = "qwen3-embedding:0.6b"
    dimensions: int = 768
    model_dir: str = "models"
    snapshot_ttl: int = 1800
    refresh_seconds: int = 300
    minimum_refresh_seconds: int = 60
    lease_seconds: int = 120
    # A new model is promoted only if it beats the embedding ranking by this NDCG margin.
    promote_margin: float = 0.01
    retrain_min_sessions: int = 200


@lru_cache
def settings() -> Settings:
    return Settings()

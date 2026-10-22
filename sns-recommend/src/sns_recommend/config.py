from functools import lru_cache
from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # SNS database: accounts and posts stay here. Recommendation database: vectors and jobs.
    source_database_url: str = "postgresql://snsuser:snspassword@localhost:5432/snsdb"
    database_url: str = "postgresql://recommend:recommend@localhost:55432/recommend"
    redis_url: str = "redis://localhost:56379/0"
    cursor_secret: str = "course-local-cursor-secret"
    model_mode: Literal["fixture", "live", "record", "replay"] = "live"
    model_api_key: SecretStr = SecretStr("ollama")
    model_base_url: str = "http://localhost:11434/v1"
    model_timeout_seconds: float = 120
    embedding_model: str = "qwen3-embedding:0.6b"
    rerank_model: str = "sns-reranker"
    dimensions: int = 768
    snapshot_ttl: int = 1800
    refresh_seconds: int = 300
    lease_seconds: int = 120
    daily_call_limit: int = 20
    recordings_dir: str = "recordings"


@lru_cache
def settings() -> Settings:
    return Settings()

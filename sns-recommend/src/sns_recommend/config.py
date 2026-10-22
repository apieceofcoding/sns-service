from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # SNS database: accounts and posts stay here. Recommend database: vectors and jobs.
    source_database_url: str = "postgresql://snsuser:snspassword@localhost:5432/snsdb"
    database_url: str = "postgresql://recommend:recommend@localhost:55432/recommend"
    redis_url: str = "redis://localhost:56379/0"
    cursor_secret: str = "course-local-cursor-secret"
    model_mode: str = "fixture"
    embedding_model: str = "gemini-embedding-2"
    rerank_model: str = "gemini-3.5-flash-lite"
    dimensions: int = 32
    snapshot_ttl: int = 1800
    refresh_seconds: int = 300
    lease_seconds: int = 120
    daily_call_limit: int = 20
    recordings_dir: str = "recordings"


@lru_cache
def settings() -> Settings:
    return Settings()

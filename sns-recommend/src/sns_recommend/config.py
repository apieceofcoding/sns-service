from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # SNS database: accounts and posts stay here. Recommend database: user events and vectors.
    source_database_url: str = "postgresql://snsuser:snspassword@localhost:5432/snsdb"
    database_url: str = "postgresql://recommend:recommend@localhost:55432/recommend"
    # fixture: keyword vectors for tests. live: the embedding model API.
    model_mode: Literal["fixture", "live"] = "live"
    model_api_key: SecretStr = SecretStr("ollama")
    model_base_url: str = "http://localhost:11434/v1"
    model_timeout_seconds: float = 120
    embedding_model: str = "qwen3-embedding:0.6b"
    dimensions: int = 768


@lru_cache
def settings() -> Settings:
    return Settings()

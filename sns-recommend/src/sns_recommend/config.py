from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    source_database_url: str = "postgresql://snsuser:snspassword@localhost:5432/snsdb"
    sns_redis_url: str = "redis://localhost:6379/0"
    storage_url: str = "http://localhost:9000"
    storage_bucket: str = "media"
    storage_access_key: str = "rustfsadmin"
    storage_secret_key: SecretStr = SecretStr("rustfsadmin")


@lru_cache
def settings() -> Settings:
    return Settings()

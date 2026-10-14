from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str | None = None
    # Без короткого таймаута проверка здоровья при упавшей базе висит до минуты
    db_connect_timeout_seconds: float = 3.0

    jwt_secret: SecretStr
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    cors_origins: list[str] = []

    demo_mama_password: SecretStr | None = None
    demo_papa_password: SecretStr | None = None
    load_password: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

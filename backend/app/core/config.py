from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str | None = None
    # Без короткого таймаута проверка здоровья при упавшей базе висит до минуты
    db_connect_timeout_seconds: float = 3.0
    # Пул соединений одного процесса API: постоянные плюс временные сверх них
    db_pool_size: int = 5
    db_max_overflow: int = 10
    # Загрузка пула нужна нагрузочному тесту; на стенде для людей она не открывается
    pool_metrics_enabled: bool = False

    jwt_secret: SecretStr
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    cors_origins: list[str] = []

    demo_mama_password: SecretStr | None = None
    demo_papa_password: SecretStr | None = None
    load_password: SecretStr | None = None
    # Куда сид сохраняет журналы детских сессий перед пересозданием демо-семьи
    exports_dir: str = "exports"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    bot_token: str = ""
    admin_ids: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/followup"
    timezone: str = "Europe/Moscow"
    daily_min: int = 10
    daily_limit: int = 15
    inactive_days: int = 7
    repeat_after_days: int = 30
    send_start_hour: int = 10
    send_end_hour: int = 19
    min_delay_minutes: int = 20
    max_delay_minutes: int = 45
    automation_enabled: bool = False
    webapp_url: str = ""
    secret_key: str = "change-me"
    support_username: str = ""

    @property
    def admins(self) -> set[int]:
        return {int(x.strip()) for x in self.admin_ids.split(",") if x.strip()}

    @property
    def async_database_url(self) -> str:
        """Railway exposes postgresql://; SQLAlchemy asyncpg needs the explicit driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

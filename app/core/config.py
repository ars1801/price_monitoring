# Настройки приложения и окружения
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Price Monitoring System", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=True, alias="DEBUG")

    api_prefix: str = Field(default="/api", alias="API_PREFIX")

    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="price_monitoring", alias="DB_NAME")
    db_user: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="postgres", alias="DB_PASSWORD")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    redis_url: str = Field(default="redis://redis:6379", alias="REDIS_URL")

    monitoring_interval_hours: int = Field(default=6, alias="MONITORING_INTERVAL_HOURS")

    price_snapshot_interval_minutes: int = Field(default=1440, alias="PRICE_SNAPSHOT_INTERVAL_MINUTES")

    @property
    def database_url(self) -> str:
        # Подключения к PostgreSQL
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    # Кэшируем настройки, чтобы не создавать объект много раз
    return Settings()
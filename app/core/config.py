from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Bulk Certificate Generator"
    environment: str = "development"
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    redis_url: str = Field(default="", validation_alias="REDIS_URL")
    storage_path: str = Field(default="storage", validation_alias="STORAGE_PATH")
    max_csv_bytes: int = Field(default=5_000_000, validation_alias="MAX_CSV_BYTES")
    max_rows: int = Field(default=10_000, validation_alias="MAX_ROWS")
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=list,
        validation_alias="CORS_ORIGINS",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
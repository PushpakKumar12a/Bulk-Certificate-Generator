from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
    )

    app_name: str = "Bulk Certificate Generator"
    environment: str = "production"
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    max_csv_bytes: int = Field(default=5_000_000, validation_alias="MAX_CSV_BYTES")
    max_rows: int = Field(default=10_000, validation_alias="MAX_ROWS")
    cors_origins: list[str] = Field(
        default=["*"],
        validation_alias="CORS_ORIGINS",
    )
    max_jobs_per_user: int = Field(default=100, validation_alias="MAX_JOBS_PER_USER")
    rate_limit_per_minute: int = Field(default=60, validation_alias="RATE_LIMIT_PER_MINUTE")
    api_keys: str = Field(default="", validation_alias="API_KEYS")

    # Azure-native Storage & Queue Configuration
    azure_storage_account_name: str = Field(default="", validation_alias="AZURE_STORAGE_ACCOUNT_NAME")
    azure_storage_connection_string: str = Field(default="", validation_alias="AZURE_STORAGE_CONNECTION_STRING")
    azure_storage_queue_name: str = Field(default="certificate-jobs", validation_alias="AZURE_STORAGE_QUEUE_NAME")
    azure_storage_poison_queue_name: str = Field(default="certificate-jobs-poison", validation_alias="AZURE_STORAGE_POISON_QUEUE_NAME")
    azure_storage_uploads_container: str = Field(default="uploads", validation_alias="AZURE_STORAGE_UPLOADS_CONTAINER")
    azure_storage_certificates_container: str = Field(default="certificates", validation_alias="AZURE_STORAGE_CERTIFICATES_CONTAINER")
    azure_client_id: str = Field(default="", validation_alias="AZURE_CLIENT_ID")
    worker_visibility_timeout: int = Field(default=300, validation_alias="WORKER_VISIBILITY_TIMEOUT")
    worker_max_retries: int = Field(default=3, validation_alias="WORKER_MAX_RETRIES")

@lru_cache
def get_settings() -> Settings:
    return Settings()
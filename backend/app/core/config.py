"""应用配置。

所有配置通过环境变量注入（ADR-0001 / ADR-0006）。
secrets 走 env / Docker secret；API Key 主密钥 APP_ENCRYPTION_KEY 用于 Fernet（ADR-0006）。
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    APP_NAME: str = "PPT 素材库"
    APP_VERSION: str = "0.1.0"
    ENV: str = "dev"
    SECRET_KEY: str = "change-me-in-production"
    # Token expiry (minutes)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # --- Database ---
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "pptlibrary"
    POSTGRES_USER: str = "pptlibrary"
    POSTGRES_PASSWORD: str = "pptlibrary"

    # --- Redis ---
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # --- MinIO / S3 ---
    MINIO_ENDPOINT: str = "minio:9000"
    # External endpoint for browser-facing presigned URLs (§14.3). Defaults to MINIO_ENDPOINT.
    MINIO_EXTERNAL_ENDPOINT: str = "localhost:19000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ppt-library"
    MINIO_SECURE: bool = False

    # --- Bootstrap admin ---
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme123"

    # --- Crypto master key for API keys (ADR-0006) ---
    # Must be a urlsafe base64-encoded 32-byte key (Fernet.generate_key())
    APP_ENCRYPTION_KEY: str = "dGVzdC1tYXN0ZXIta2V5LTEyMzQ1Njc4OTAxMjM0NTY="

    # --- Upload limits (PRD §18.1) ---
    UPLOAD_MAX_SIZE_MB: int = 200
    UPLOAD_ALLOWED_EXTENSIONS: List[str] = Field(default_factory=lambda: [".pptx"])
    ZIP_BOMB_RATIO: int = 200  # max uncompressed / compressed ratio

    # --- CORS ---
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:13000", "http://127.0.0.1:13000",
        ]
    )

    # --- Storage of derived object keys prefix ---
    STORAGE_SOURCE_NAME: str = "source.pptx"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def celery_broker_url(self) -> str:
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        return self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

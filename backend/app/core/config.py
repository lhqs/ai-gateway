from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LHQS AI Gateway"
    environment: str = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/lhqs_ai_gateway"
    )
    redis_url: str = "redis://localhost:6379/0"
    admin_token: str = "change-me-admin-token"
    request_body_limit_bytes: int = 2 * 1024 * 1024
    native_stream_max_seconds: int = 300
    default_timeout_seconds: float = 60.0
    default_rate_limit_per_minute: int = 120
    default_cost_currency: str = "USD"
    store_api_key_value: bool = False
    cache_namespace: str = "ai-gateway"
    jwt_secret_key: str = "change-me-jwt-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    admin_registration_mode: str = "bootstrap"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )
    request_logging_enabled: bool = True
    request_logging_body_max_bytes: int = 4096
    request_logging_long_value_max_chars: int = 512
    request_logging_excluded_paths: list[str] = [
        "/health",
        "/docs",
        "/redoc",
        "/favicon.ico",
        "/openapi.json",
    ]
    request_logging_body_excluded_paths: list[str] = []
    request_logging_omit_body_keys: list[str] = [
        "audio",
        "audio_base64",
        "base64",
        "blob",
        "data",
        "file",
        "file_base64",
        "image_base64",
        "messages",
        "prompt",
        "raw_request_body",
        "raw_response_body",
    ]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

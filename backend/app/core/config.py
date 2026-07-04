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
    cache_namespace: str = "ai-gateway"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

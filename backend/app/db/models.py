from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JsonType, list[str]: JsonType, list[int]: JsonType}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    access_config: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    key_value: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    access_config: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def key(self) -> str | None:
        return self.key_value


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminSession(Base, TimestampMixin):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    protocol_modes: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    auth_type: Mapped[str] = mapped_column(String(64), nullable=False, default="api_key_header")
    auth_config: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    allowed_paths: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    blocked_headers: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    usage_parser_type: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_health_error: Mapped[str | None] = mapped_column(Text)
    last_health_status_code: Mapped[int | None] = mapped_column(Integer)
    failure_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=60000)
    allow_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    native_rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer)


class Model(Base, TimestampMixin):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    capabilities: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    context_window: Mapped[int | None] = mapped_column(Integer)
    input_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    output_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class ModelPriceConfig(Base, TimestampMixin):
    __tablename__ = "model_price_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    model_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False, default="tokens")
    unit_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1_000_000)
    input_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    cached_input_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    output_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    reasoning_output_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    request_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ModelAlias(Base, TimestampMixin):
    __tablename__ = "model_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alias: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class RouteRule(Base, TimestampMixin):
    __tablename__ = "route_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_alias_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    primary_model_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    fallback_model_ids: Mapped[list[int]] = mapped_column(JsonType, nullable=False, default=list)
    strategy_type: Mapped[str] = mapped_column(String(64), nullable=False, default="primary_fallback")
    strategy_config: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    failover_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failover_on_status_codes: Mapped[list[int]] = mapped_column(JsonType, nullable=False, default=list)
    failover_on_error_types: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    max_failover_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    cache_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    cache_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="client")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_id: Mapped[int | None] = mapped_column(Integer, index=True)
    api_key_id: Mapped[int | None] = mapped_column(Integer, index=True)
    model_alias: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_id: Mapped[int | None] = mapped_column(Integer, index=True)
    model_id: Mapped[int | None] = mapped_column(Integer, index=True)
    stream: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billable_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billable_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    first_token_latency_ms: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    cost_currency: Mapped[str | None] = mapped_column(String(16), index=True)
    cost_unit_type: Mapped[str | None] = mapped_column(String(32))
    cost_unit_quantity: Mapped[int | None] = mapped_column(Integer)
    input_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    cached_input_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    output_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    pricing_config_id: Mapped[int | None] = mapped_column(Integer, index=True)
    pricing_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_calculated", index=True
    )
    cost_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    call_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unified_chat")
    native_method: Mapped[str | None] = mapped_column(String(16))
    native_path: Mapped[str | None] = mapped_column(Text)
    native_status_code: Mapped[int | None] = mapped_column(Integer)
    usage_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    raw_usage: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    prompt_content: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    completion_content: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    raw_request_body: Mapped[dict[str, Any] | str | None] = mapped_column(JsonType)
    raw_response_body: Mapped[dict[str, Any] | str | None] = mapped_column(JsonType)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cache_key: Mapped[str | None] = mapped_column(Text)
    failover_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failover_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    initial_provider_id: Mapped[int | None] = mapped_column(Integer)
    initial_model_id: Mapped[int | None] = mapped_column(Integer)
    final_provider_id: Mapped[int | None] = mapped_column(Integer)
    final_model_id: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    client_id: Mapped[int | None] = mapped_column(Integer, index=True)
    model_alias: Mapped[str | None] = mapped_column(String(128), index=True)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    response_body: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

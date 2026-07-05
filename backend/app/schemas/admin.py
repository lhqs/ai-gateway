from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    name: str
    description: str | None = None
    status: str = "active"
    access_config: dict[str, Any] = Field(default_factory=dict)


class ClientPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    access_config: dict[str, Any] | None = None


class ClientRead(ClientCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientPage(BaseModel):
    items: list[ClientRead]
    total: int
    limit: int
    offset: int


class ApiKeyCreate(BaseModel):
    client_id: int
    name: str
    expires_at: datetime | None = None
    access_config: dict[str, Any] = Field(default_factory=dict)


class ApiKeyCreated(BaseModel):
    id: int
    key: str
    key_prefix: str


class ApiKeyRead(BaseModel):
    id: int
    client_id: int
    name: str
    key: str | None = None
    key_prefix: str
    status: str
    access_config: dict[str, Any]
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyPage(BaseModel):
    items: list[ApiKeyRead]
    total: int
    limit: int
    offset: int


class ProviderWrite(BaseModel):
    name: str
    provider_type: str
    base_url: str
    encrypted_api_key: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    protocol_modes: list[str] = Field(default_factory=list)
    auth_type: str = "api_key_header"
    auth_config: dict[str, Any] = Field(default_factory=dict)
    allowed_paths: list[str] = Field(default_factory=list)
    blocked_headers: list[str] = Field(default_factory=list)
    usage_parser_type: str = "none"
    health_status: str = "healthy"
    failure_threshold: int = 5
    cooldown_seconds: int = 60
    timeout_ms: int = 60000
    allow_streaming: bool = True
    native_rate_limit_per_minute: int | None = None


class ProviderPatch(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    encrypted_api_key: str | None = None
    config: dict[str, Any] | None = None
    status: str | None = None
    protocol_modes: list[str] | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] | None = None
    allowed_paths: list[str] | None = None
    blocked_headers: list[str] | None = None
    usage_parser_type: str | None = None
    health_status: str | None = None
    failure_threshold: int | None = None
    cooldown_seconds: int | None = None
    timeout_ms: int | None = None
    allow_streaming: bool | None = None
    native_rate_limit_per_minute: int | None = None


class ProviderRead(ProviderWrite):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderPage(BaseModel):
    items: list[ProviderRead]
    total: int
    limit: int
    offset: int


class ModelWrite(BaseModel):
    provider_id: int
    name: str
    display_name: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    context_window: int | None = None
    input_price: float | None = None
    output_price: float | None = None
    currency: str = "USD"
    status: str = "active"


class ModelPatch(BaseModel):
    provider_id: int | None = None
    name: str | None = None
    display_name: str | None = None
    capabilities: list[str] | None = None
    context_window: int | None = None
    input_price: float | None = None
    output_price: float | None = None
    currency: str | None = None
    status: str | None = None


class ModelRead(ModelWrite):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelPage(BaseModel):
    items: list[ModelRead]
    total: int
    limit: int
    offset: int


class ModelPriceConfigWrite(BaseModel):
    provider_id: int
    model_id: int
    model_name: str
    currency_code: str = "USD"
    unit_type: str = "tokens"
    unit_quantity: int = Field(default=1_000_000, gt=0)
    input_unit_price: Decimal | None = None
    cached_input_unit_price: Decimal | None = None
    output_unit_price: Decimal | None = None
    reasoning_output_unit_price: Decimal | None = None
    request_unit_price: Decimal | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class ModelPriceConfigPatch(BaseModel):
    provider_id: int | None = None
    model_id: int | None = None
    model_name: str | None = None
    currency_code: str | None = None
    unit_type: str | None = None
    unit_quantity: int | None = Field(default=None, gt=0)
    input_unit_price: Decimal | None = None
    cached_input_unit_price: Decimal | None = None
    output_unit_price: Decimal | None = None
    reasoning_output_unit_price: Decimal | None = None
    request_unit_price: Decimal | None = None
    config: dict[str, Any] | None = None
    status: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class ModelPriceConfigRead(ModelPriceConfigWrite):
    id: int
    effective_from: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelPriceConfigPage(BaseModel):
    items: list[ModelPriceConfigRead]
    total: int
    limit: int
    offset: int


class ModelAliasWrite(BaseModel):
    alias: str
    description: str | None = None
    status: str = "active"


class ModelAliasPatch(BaseModel):
    alias: str | None = None
    description: str | None = None
    status: str | None = None


class ModelAliasRead(ModelAliasWrite):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelAliasPage(BaseModel):
    items: list[ModelAliasRead]
    total: int
    limit: int
    offset: int


class RouteRuleWrite(BaseModel):
    model_alias_id: int
    primary_model_id: int
    fallback_model_ids: list[int] = Field(default_factory=list)
    strategy_type: str = "primary_fallback"
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    status: str = "active"
    failover_enabled: bool = True
    failover_on_status_codes: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    failover_on_error_types: list[str] = Field(
        default_factory=lambda: ["timeout", "connection_error", "rate_limit", "provider_error"]
    )
    max_failover_attempts: int = 2
    cache_enabled: bool = False
    cache_ttl_seconds: int = 300
    cache_scope: str = "client"


class RouteRulePatch(BaseModel):
    model_alias_id: int | None = None
    primary_model_id: int | None = None
    fallback_model_ids: list[int] | None = None
    strategy_type: str | None = None
    strategy_config: dict[str, Any] | None = None
    priority: int | None = None
    status: str | None = None
    failover_enabled: bool | None = None
    failover_on_status_codes: list[int] | None = None
    failover_on_error_types: list[str] | None = None
    max_failover_attempts: int | None = None
    cache_enabled: bool | None = None
    cache_ttl_seconds: int | None = None
    cache_scope: str | None = None


class RouteRuleRead(RouteRuleWrite):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RouteRulePage(BaseModel):
    items: list[RouteRuleRead]
    total: int
    limit: int
    offset: int

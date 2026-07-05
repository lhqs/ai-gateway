from datetime import datetime
from typing import Any

from pydantic import BaseModel


class UsageLogRead(BaseModel):
    id: int
    request_id: str
    client_id: int | None
    model_alias: str | None
    provider_id: int | None
    model_id: int | None
    stream: bool
    status: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_input_tokens: int
    billable_input_tokens: int
    billable_output_tokens: int
    estimated_cost: Any | None = None
    cost_currency: str | None
    cost_unit_type: str | None
    cost_unit_quantity: int | None
    input_cost: Any | None
    cached_input_cost: Any | None
    output_cost: Any | None
    total_cost: Any | None
    pricing_config_id: int | None
    pricing_status: str
    cost_breakdown: dict[str, Any] | None
    latency_ms: int | None
    error_code: str | None
    error_message: str | None
    call_mode: str
    native_method: str | None
    native_path: str | None
    native_status_code: int | None
    usage_status: str
    raw_usage: dict[str, Any] | None
    prompt_content: dict[str, Any] | None
    completion_content: dict[str, Any] | None
    raw_request_body: Any | None
    raw_response_body: Any | None
    cache_hit: bool
    cache_key: str | None
    failover_triggered: bool
    failover_attempts: int
    initial_provider_id: int | None
    initial_model_id: int | None
    final_provider_id: int | None
    final_model_id: int | None
    failure_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageLogPage(BaseModel):
    items: list[UsageLogRead]
    total: int
    limit: int
    offset: int

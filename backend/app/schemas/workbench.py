from typing import Any

from pydantic import BaseModel, Field

from app.schemas.chat import ChatCompletionRequest


class WorkbenchChatTestRequest(ChatCompletionRequest):
    api_key_id: int = Field(gt=0)


class WorkbenchChatTestMeta(BaseModel):
    usage_log_id: int | None = None
    latency_ms: int | None = None
    model_alias: str | None = None
    provider_id: int | None = None
    model_id: int | None = None
    final_provider_id: int | None = None
    final_model_id: int | None = None
    status: str | None = None
    usage_status: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_hit: bool = False
    failover_triggered: bool = False
    failover_attempts: int = 0


class WorkbenchChatTestResponse(BaseModel):
    request_id: str
    body: dict[str, Any]
    meta: WorkbenchChatTestMeta

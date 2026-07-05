from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]]
    name: str | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    stop: str | list[str] | None = None
    user: str | None = None

    model_config = {"extra": "allow"}


class GatewayChatRequest(BaseModel):
    request_id: str
    model_alias: str
    provider_model: str
    messages: list[ChatMessage]
    stream: bool = False
    body: dict[str, Any]


class GatewayChatResponse(BaseModel):
    body: dict[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    raw_usage: dict[str, Any] | None = None
    usage_status: Literal["parsed", "estimated", "unknown", "failed"] = "unknown"


class GatewayChatChunk(BaseModel):
    data: bytes
    first_token: bool = False
    completion_delta: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    raw_usage: dict[str, Any] | None = None
    usage_status: Literal["parsed", "estimated", "unknown", "failed"] = "unknown"

from typing import Any, Literal

from pydantic import BaseModel


class NativeProxyRequest(BaseModel):
    request_id: str
    method: Literal["GET", "POST"]
    provider_name: str
    native_path: str
    query_params: list[tuple[str, str]]
    headers: dict[str, str]
    body: bytes


class NativeUsageResult(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_usage: dict[str, Any] | None = None
    usage_status: Literal["parsed", "estimated", "unknown", "failed"] = "unknown"


class NativeProxyResponse(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: bytes
    usage: NativeUsageResult


class NativeProxyChunk(BaseModel):
    data: bytes
    usage: NativeUsageResult | None = None

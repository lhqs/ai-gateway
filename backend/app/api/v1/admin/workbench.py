import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis, require_admin, session_dep
from app.core.security import AuthContext
from app.db.models import UsageLog
from app.repositories.api_keys import ApiKeyRepository
from app.repositories.clients import ClientRepository
from app.schemas.chat import ChatCompletionRequest
from app.schemas.workbench import WorkbenchChatTestRequest, WorkbenchChatTestResponse
from app.services.cache_service import CacheService
from app.services.chat_service import ChatService

router = APIRouter(dependencies=[Depends(require_admin)])


async def _auth_context_for_api_key(session: AsyncSession, api_key_id: int) -> AuthContext:
    api_key_repo = ApiKeyRepository(session)
    api_key = await api_key_repo.get(api_key_id)
    if not api_key or api_key.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active API key not found")
    if api_key.expires_at and api_key.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key expired")
    client = await ClientRepository(session).get_active(api_key.client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client is disabled")
    await api_key_repo.mark_used(api_key.id)
    return AuthContext(client=client, api_key=api_key)


def _workbench_meta(log: UsageLog | None) -> dict[str, Any]:
    if not log:
        return {}
    return {
        "usage_log_id": log.id,
        "latency_ms": log.latency_ms,
        "model_alias": log.model_alias,
        "provider_id": log.provider_id,
        "model_id": log.model_id,
        "final_provider_id": log.final_provider_id,
        "final_model_id": log.final_model_id,
        "status": log.status,
        "usage_status": log.usage_status,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "total_tokens": log.total_tokens,
        "cached_input_tokens": log.cached_input_tokens,
        "total_cost": log.total_cost,
        "cost_currency": log.cost_currency,
        "pricing_status": log.pricing_status,
        "cache_hit": log.cache_hit,
        "failover_triggered": log.failover_triggered,
        "failover_attempts": log.failover_attempts,
    }


def _ndjson_event(event_type: str, **payload: Any) -> bytes:
    return (json.dumps({"type": event_type, **payload}, default=str) + "\n").encode("utf-8")


def _stream_delta_from_chunk(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    deltas: list[str] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        raw = line.removeprefix("data:").strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        choices = payload.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if isinstance(content, str):
            deltas.append(content)
    return "".join(deltas)


async def _usage_log_for_request(session: AsyncSession, request_id: str) -> UsageLog | None:
    return await session.scalar(
        select(UsageLog).where(UsageLog.request_id == request_id).order_by(desc(UsageLog.id)).limit(1)
    )


@router.post("/chat-test", response_model=WorkbenchChatTestResponse)
async def chat_test(
    payload: WorkbenchChatTestRequest,
    session: AsyncSession = Depends(session_dep),
    redis: Redis | None = Depends(get_redis),
):
    request_id = uuid.uuid4().hex
    auth = await _auth_context_for_api_key(session, payload.api_key_id)
    chat_payload = ChatCompletionRequest.model_validate(payload.model_dump(exclude={"api_key_id"}))
    chat_service = ChatService(session, CacheService(redis))
    if payload.stream:
        chunks: list[str] = []
        async for chunk in chat_service.complete_stream(auth, request_id, chat_payload):
            chunks.append(chunk.decode("utf-8", errors="replace"))
        log = await _usage_log_for_request(session, request_id)
        completion = ""
        if log and isinstance(log.completion_content, dict):
            content = log.completion_content.get("content")
            completion = content if isinstance(content, str) else ""
        body = {
            "id": request_id,
            "object": "workbench.stream",
            "choices": [{"message": {"role": "assistant", "content": completion}}],
            "stream_chunks": chunks[-200:],
        }
        return {"request_id": request_id, "body": body, "meta": _workbench_meta(log)}

    body = await chat_service.complete(auth, request_id, chat_payload)
    log = await _usage_log_for_request(session, request_id)
    return {"request_id": request_id, "body": body, "meta": _workbench_meta(log)}


@router.post("/chat-test/stream")
async def chat_test_stream(
    payload: WorkbenchChatTestRequest,
    session: AsyncSession = Depends(session_dep),
    redis: Redis | None = Depends(get_redis),
):
    request_id = uuid.uuid4().hex
    auth = await _auth_context_for_api_key(session, payload.api_key_id)
    chat_payload = ChatCompletionRequest.model_validate(
        {**payload.model_dump(exclude={"api_key_id"}), "stream": True}
    )
    chat_service = ChatService(session, CacheService(redis))

    async def iterator():
        yield _ndjson_event("start", request_id=request_id)
        chunks: list[str] = []
        try:
            async for chunk in chat_service.complete_stream(auth, request_id, chat_payload):
                raw = chunk.decode("utf-8", errors="replace")
                chunks.append(raw)
                delta = _stream_delta_from_chunk(chunk)
                if delta:
                    yield _ndjson_event("delta", content=delta)
                else:
                    yield _ndjson_event("chunk", raw=raw)
            log = await _usage_log_for_request(session, request_id)
            yield _ndjson_event("meta", meta=_workbench_meta(log), chunks=chunks[-200:])
            yield _ndjson_event("done", request_id=request_id)
        except Exception as exc:
            yield _ndjson_event("error", message=str(exc), request_id=request_id)

    return StreamingResponse(iterator(), media_type="application/x-ndjson")

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
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
        "cache_hit": log.cache_hit,
        "failover_triggered": log.failover_triggered,
        "failover_attempts": log.failover_attempts,
    }


@router.post("/chat-test", response_model=WorkbenchChatTestResponse)
async def chat_test(
    payload: WorkbenchChatTestRequest,
    session: AsyncSession = Depends(session_dep),
    redis: Redis | None = Depends(get_redis),
):
    if payload.stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workbench chat test does not support streaming yet",
        )
    request_id = uuid.uuid4().hex
    auth = await _auth_context_for_api_key(session, payload.api_key_id)
    chat_payload = ChatCompletionRequest.model_validate(payload.model_dump(exclude={"api_key_id"}))
    body = await ChatService(session, CacheService(redis)).complete(auth, request_id, chat_payload)
    log = await session.scalar(
        select(UsageLog).where(UsageLog.request_id == request_id).order_by(desc(UsageLog.id)).limit(1)
    )
    return {"request_id": request_id, "body": body, "meta": _workbench_meta(log)}

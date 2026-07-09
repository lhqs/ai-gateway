import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context, get_redis, session_dep
from app.core.errors import ProviderCallError
from app.core.request_logging import get_request_id
from app.core.security import AuthContext
from app.schemas.chat import ChatCompletionRequest
from app.services.cache_service import CacheService
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(session_dep),
    redis: Redis | None = Depends(get_redis),
    auth: AuthContext = Depends(get_auth_context),
):
    request_id = get_request_id(request)
    response.headers["x-request-id"] = request_id
    service = ChatService(session, CacheService(redis))
    if payload.stream:
        async def iterator():
            try:
                async for chunk in service.complete_stream(auth, request_id, payload):
                    yield chunk
            except ProviderCallError as exc:
                error = {"error": {"message": exc.message, "type": exc.error_type}}
                yield f"data: {json.dumps(error)}\n\n"

        return StreamingResponse(
            iterator(),
            media_type="text/event-stream",
            headers={"x-request-id": request_id},
        )
    body = await service.complete(auth, request_id, payload)
    return JSONResponse(content=body, headers={"x-request-id": request_id})

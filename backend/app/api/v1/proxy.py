from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context, get_redis, session_dep
from app.core.request_logging import get_request_id
from app.core.security import AuthContext
from app.services.native_proxy_service import NativeProxyService

router = APIRouter()


def _wants_stream(native_path: str, request: Request) -> bool:
    if "streamGenerateContent" in native_path:
        return True
    return request.query_params.get("stream", "").lower() == "true"


@router.get("/{provider}/{native_path:path}")
async def proxy_get(
    provider: str,
    native_path: str,
    request: Request,
    session: AsyncSession = Depends(session_dep),
    redis: Redis | None = Depends(get_redis),
    auth: AuthContext = Depends(get_auth_context),
):
    request_id = get_request_id(request)
    service = NativeProxyService(session, redis)
    if _wants_stream(native_path, request):
        return await service.stream(auth, request_id, provider, native_path, "GET", request)
    response = await service.forward(auth, request_id, provider, native_path, "GET", request)
    response.headers["x-request-id"] = request_id
    return response


@router.post("/{provider}/{native_path:path}")
async def proxy_post(
    provider: str,
    native_path: str,
    request: Request,
    session: AsyncSession = Depends(session_dep),
    redis: Redis | None = Depends(get_redis),
    auth: AuthContext = Depends(get_auth_context),
):
    request_id = get_request_id(request)
    service = NativeProxyService(session, redis)
    if _wants_stream(native_path, request):
        return await service.stream(auth, request_id, provider, native_path, "POST", request)
    response = await service.forward(auth, request_id, provider, native_path, "POST", request)
    response.headers["x-request-id"] = request_id
    return response

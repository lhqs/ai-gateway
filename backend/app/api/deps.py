from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    AdminAuthContext,
    AuthContext,
    authenticate_api_key,
    verify_admin_token,
)
from app.db.session import get_db_session
from app.services.admin_auth_service import AdminAuthService


async def get_redis(request: Request) -> Redis | None:
    return getattr(request.app.state, "redis", None)


def verify_bootstrap_token(authorization: str | None) -> None:
    verify_admin_token(get_settings().admin_token, authorization)


async def session_dep() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        try:
            yield session
            await session.commit()
        except HTTPException:
            await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise


async def get_auth_context(
    request: Request,
    session: AsyncSession = Depends(session_dep),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    auth = await authenticate_api_key(session, authorization)
    request.state.request_auth_source = "api_key"
    request.state.request_client_id = auth.client.id
    request.state.request_api_key_id = auth.api_key.id
    return auth


async def get_admin_context(
    request: Request,
    session: AsyncSession = Depends(session_dep),
    authorization: str | None = Header(default=None),
) -> AdminAuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    access_token = authorization.split(" ", 1)[1].strip()
    user = await AdminAuthService(session, get_settings()).authenticate_access_token(access_token)
    request.state.request_auth_source = "admin"
    request.state.request_admin_user_id = user.id
    return AdminAuthContext(user=user)


async def require_admin(auth: AdminAuthContext = Depends(get_admin_context)) -> AdminAuthContext:
    return auth

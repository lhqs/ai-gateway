from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import AuthContext, authenticate_api_key, verify_admin_token
from app.db.session import get_db_session


async def get_redis(request: Request) -> Redis | None:
    return getattr(request.app.state, "redis", None)


async def require_admin(authorization: str | None = Header(default=None)) -> None:
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
    session: AsyncSession = Depends(session_dep),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    return await authenticate_api_key(session, authorization)

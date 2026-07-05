import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminUser, ApiKey, Client
from app.repositories.api_keys import ApiKeyRepository
from app.repositories.clients import ClientRepository


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    key = f"lhqs_{secrets.token_urlsafe(32)}"
    return key, key[:12]


@dataclass(slots=True)
class AuthContext:
    client: Client
    api_key: ApiKey


@dataclass(slots=True)
class AdminAuthContext:
    user: AdminUser


async def authenticate_api_key(session: AsyncSession, authorization: str | None) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    raw_key = authorization.split(" ", 1)[1].strip()
    key_hash = hash_api_key(raw_key)
    api_key = await ApiKeyRepository(session).get_active_by_hash(key_hash)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if api_key.expires_at and api_key.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

    client = await ClientRepository(session).get_active(api_key.client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client is disabled")

    await ApiKeyRepository(session).mark_used(api_key.id)
    return AuthContext(client=client, api_key=api_key)


def verify_admin_token(expected: str, authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin token")
    actual = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin token")

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import AdminSession, AdminUser
from app.repositories.admin_audit_logs import AdminAuditLogRepository
from app.repositories.admin_sessions import AdminSessionRepository
from app.repositories.admin_users import AdminUserRepository

password_hasher = PasswordHash.recommended()


@dataclass(slots=True)
class AdminTokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    user: AdminUser


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class AdminAuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = AdminUserRepository(session)
        self.sessions = AdminSessionRepository(session)
        self.audit = AdminAuditLogRepository(session)

    async def has_users(self) -> bool:
        return await self.users.any_exists()

    async def register(
        self,
        *,
        email: str,
        username: str,
        password: str,
        display_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminUser:
        if await self.users.get_by_account(email) or await self.users.get_by_account(username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

        try:
            user = await self.users.create(
                {
                    "email": email,
                    "username": username,
                    "password_hash": password_hasher.hash(password),
                    "display_name": display_name,
                    "status": "active",
                    "token_version": 1,
                    "password_changed_at": datetime.now(timezone.utc),
                }
            )
            await self.audit.record(
                "admin_user_registered",
                user_id=user.id,
                resource_type="admin_user",
                resource_id=str(user.id),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return user
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists") from exc

    async def login(
        self,
        *,
        account: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminTokenPair:
        user = await self.users.get_by_account(account)
        if not user or user.status != "active" or not password_hasher.verify(
            password, user.password_hash
        ):
            await self.audit.record(
                "admin_login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                detail={"account": account},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        await self.users.mark_login(user.id)
        pair = await self._create_token_pair(user, ip_address=ip_address, user_agent=user_agent)
        await self.audit.record(
            "admin_login_succeeded",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return pair

    async def refresh(
        self,
        *,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminTokenPair:
        token_hash = hash_refresh_token(refresh_token)
        admin_session = await self.sessions.get_active_by_hash(token_hash)
        if not admin_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user = await self.users.get_active(admin_session.user_id)
        if not user:
            await self.sessions.revoke(admin_session.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        await self.sessions.revoke(admin_session.id)
        await self.sessions.mark_used(admin_session.id)
        return await self._create_token_pair(user, ip_address=ip_address, user_agent=user_agent)

    async def logout(self, refresh_token: str) -> None:
        admin_session = await self.sessions.get_active_by_hash(hash_refresh_token(refresh_token))
        if admin_session:
            await self.sessions.revoke(admin_session.id)
            await self.audit.record(
                "admin_logout",
                user_id=admin_session.user_id,
                resource_type="admin_session",
                resource_id=str(admin_session.id),
            )

    async def logout_all(self, user: AdminUser) -> None:
        await self.users.bump_token_version(user.id)
        await self.sessions.revoke_for_user(user.id)
        await self.audit.record("admin_logout_all", user_id=user.id)

    async def change_password(
        self,
        *,
        user: AdminUser,
        old_password: str,
        new_password: str,
    ) -> None:
        if not password_hasher.verify(old_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user.password_hash = password_hasher.hash(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        user.token_version += 1
        await self.sessions.revoke_for_user(user.id)
        await self.audit.record("admin_password_changed", user_id=user.id)

    async def authenticate_access_token(self, access_token: str) -> AdminUser:
        payload = self._decode_access_token(access_token)
        user_id = payload.get("sub")
        token_version = payload.get("token_version")
        if not isinstance(user_id, str) or not user_id.isdigit() or not isinstance(token_version, int):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user = await self.users.get_active(int(user_id))
        if not user or user.token_version != token_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user

    async def _create_token_pair(
        self,
        user: AdminUser,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AdminTokenPair:
        refresh_token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_expire_days)
        await self.sessions.create(
            {
                "user_id": user.id,
                "refresh_token_hash": hash_refresh_token(refresh_token),
                "user_agent": user_agent,
                "ip_address": ip_address,
                "expires_at": expires_at,
                "status": "active",
            }
        )
        return AdminTokenPair(
            access_token=self._create_access_token(user),
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_expire_minutes * 60,
            user=user,
        )

    def _create_access_token(self, user: AdminUser) -> str:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.settings.access_token_expire_minutes)
        payload: dict[str, Any] = {
            "sub": str(user.id),
            "token_version": user.token_version,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(payload, self.settings.jwt_secret_key, algorithm=self.settings.jwt_algorithm)

    def _decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
        except InvalidTokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return payload

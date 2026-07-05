from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.models import AdminSession
from app.repositories.base import Repository


class AdminSessionRepository(Repository[AdminSession]):
    model = AdminSession

    async def get_active_by_hash(self, refresh_token_hash: str) -> AdminSession | None:
        now = datetime.now(timezone.utc)
        return await self.session.scalar(
            select(AdminSession).where(
                AdminSession.refresh_token_hash == refresh_token_hash,
                AdminSession.status == "active",
                AdminSession.expires_at > now,
            )
        )

    async def revoke(self, session_id: int) -> None:
        await self.session.execute(
            update(AdminSession)
            .where(AdminSession.id == session_id)
            .values(status="revoked", revoked_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )

    async def revoke_for_user(self, user_id: int) -> None:
        await self.session.execute(
            update(AdminSession)
            .where(AdminSession.user_id == user_id, AdminSession.status == "active")
            .values(status="revoked", revoked_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )

    async def mark_used(self, session_id: int) -> None:
        await self.session.execute(
            update(AdminSession)
            .where(AdminSession.id == session_id)
            .values(last_used_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )

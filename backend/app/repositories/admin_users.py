from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update

from app.db.models import AdminUser
from app.repositories.base import Repository


class AdminUserRepository(Repository[AdminUser]):
    model = AdminUser

    async def any_exists(self) -> bool:
        count = await self.session.scalar(select(func.count()).select_from(AdminUser))
        return bool(count)

    async def get_by_account(self, account: str) -> AdminUser | None:
        normalized = account.strip().lower()
        return await self.session.scalar(
            select(AdminUser).where(
                or_(AdminUser.email == normalized, AdminUser.username == normalized)
            )
        )

    async def get_active(self, user_id: int) -> AdminUser | None:
        return await self.session.scalar(
            select(AdminUser).where(AdminUser.id == user_id, AdminUser.status == "active")
        )

    async def mark_login(self, user_id: int) -> None:
        await self.session.execute(
            update(AdminUser)
            .where(AdminUser.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )

    async def bump_token_version(self, user_id: int) -> None:
        await self.session.execute(
            update(AdminUser)
            .where(AdminUser.id == user_id)
            .values(token_version=AdminUser.token_version + 1)
            .execution_options(synchronize_session=False)
        )

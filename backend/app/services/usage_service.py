from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.usage_logs import UsageLogRepository


class UsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = UsageLogRepository(session)

    async def record(self, **data: Any) -> None:
        await self.repo.create_log(data)

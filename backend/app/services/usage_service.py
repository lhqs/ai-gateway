from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.usage_logs import UsageLogRepository
from app.services.pricing_service import PricingService


class UsageService:
    def __init__(self, session: AsyncSession | None) -> None:
        self.repo = UsageLogRepository(session) if session else None
        self.pricing = PricingService(session)

    async def record(self, **data: Any) -> None:
        data.update(await self.pricing.calculate_for_usage(data))
        if self.repo:
            await self.repo.create_log(data)

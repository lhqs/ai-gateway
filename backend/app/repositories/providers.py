from sqlalchemy import select

from app.db.models import Provider
from app.repositories.base import Repository


class ProviderRepository(Repository[Provider]):
    model = Provider

    async def get_active_by_name(self, name: str) -> Provider | None:
        return await self.session.scalar(
            select(Provider).where(Provider.name == name, Provider.status == "active")
        )

    async def list_active(self) -> list[Provider]:
        result = await self.session.scalars(select(Provider).where(Provider.status == "active"))
        return list(result)

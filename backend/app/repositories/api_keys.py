from datetime import datetime, timezone

from sqlalchemy import delete, select, update

from app.db.models import ApiKey
from app.repositories.base import Repository


class ApiKeyRepository(Repository[ApiKey]):
    model = ApiKey

    async def get_active_by_hash(self, key_hash: str) -> ApiKey | None:
        return await self.session.scalar(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.status == "active")
        )

    async def mark_used(self, key_id: int) -> None:
        await self.session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )

    async def list_public(self, limit: int = 100, offset: int = 0) -> list[ApiKey]:
        result = await self.session.scalars(
            select(ApiKey).order_by(ApiKey.id.desc()).limit(limit).offset(offset)
        )
        return list(result)

    async def delete_for_client(self, client_id: int) -> None:
        await self.session.execute(delete(ApiKey).where(ApiKey.client_id == client_id))
        await self.session.flush()

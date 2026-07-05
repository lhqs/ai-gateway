from typing import Any

from sqlalchemy import desc, func, select

from app.db.models import UsageLog
from app.repositories.base import Repository


class UsageLogRepository(Repository[UsageLog]):
    model = UsageLog

    async def create_log(self, data: dict[str, Any]) -> UsageLog:
        item = UsageLog(**data)
        self.session.add(item)
        await self.session.flush()
        return item

    def _filtered_stmt(self, filters: dict[str, Any] | None = None):
        stmt = select(UsageLog)
        filters = filters or {}
        for field in (
            "call_mode",
            "client_id",
            "model_alias",
            "provider_id",
            "status",
            "cache_hit",
            "failover_triggered",
        ):
            value = filters.get(field)
            if value is not None:
                column = getattr(UsageLog, field)
                stmt = stmt.where(column == value)
        native_path = filters.get("native_path")
        if native_path:
            stmt = stmt.where(UsageLog.native_path.ilike(f"%{native_path}%"))
        return stmt

    async def list_recent(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[UsageLog]:
        stmt = self._filtered_stmt(filters)
        result = await self.session.scalars(stmt.order_by(desc(UsageLog.created_at)).limit(limit).offset(offset))
        return list(result)

    async def count_recent(self, filters: dict[str, Any] | None = None) -> int:
        filtered = self._filtered_stmt(filters).subquery()
        return await self.session.scalar(select(func.count()).select_from(filtered)) or 0

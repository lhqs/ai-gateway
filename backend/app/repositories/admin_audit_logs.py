from typing import Any

from sqlalchemy import Select, func, select

from app.db.models import AdminAuditLog
from app.repositories.base import Repository


class AdminAuditLogRepository(Repository[AdminAuditLog]):
    model = AdminAuditLog

    def _filtered_stmt(
        self,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: int | None = None,
    ) -> Select[tuple[AdminAuditLog]]:
        stmt = select(AdminAuditLog)
        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AdminAuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AdminAuditLog.resource_id == resource_id)
        if user_id is not None:
            stmt = stmt.where(AdminAuditLog.user_id == user_id)
        return stmt

    async def list_filtered(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: int | None = None,
    ) -> list[AdminAuditLog]:
        result = await self.session.scalars(
            self._filtered_stmt(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
            )
            .order_by(AdminAuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result)

    async def count_filtered(
        self,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: int | None = None,
    ) -> int:
        stmt = self._filtered_stmt(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
        ).subquery()
        return await self.session.scalar(select(func.count()).select_from(stmt)) or 0

    async def record(
        self,
        action: str,
        *,
        user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AdminAuditLog:
        return await self.create(
            {
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "request_id": request_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "detail": detail,
            }
        )

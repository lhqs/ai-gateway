from typing import Any

from app.db.models import AdminAuditLog
from app.repositories.base import Repository


class AdminAuditLogRepository(Repository[AdminAuditLog]):
    model = AdminAuditLog

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

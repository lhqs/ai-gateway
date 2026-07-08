from typing import Any

from sqlalchemy import case, desc, func, literal, select

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
            "api_key_id",
            "model_alias",
            "provider_id",
            "model_id",
            "status",
            "usage_status",
            "pricing_status",
            "cost_currency",
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
        created_from = filters.get("created_from")
        if created_from is not None:
            stmt = stmt.where(UsageLog.created_at >= created_from)
        created_to = filters.get("created_to")
        if created_to is not None:
            stmt = stmt.where(UsageLog.created_at <= created_to)
        return stmt

    async def list_recent(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[UsageLog]:
        stmt = self._filtered_stmt(filters)
        result = await self.session.scalars(
            stmt.order_by(desc(UsageLog.created_at)).limit(limit).offset(offset)
        )
        return list(result)

    async def count_recent(self, filters: dict[str, Any] | None = None) -> int:
        filtered = self._filtered_stmt(filters).subquery()
        return await self.session.scalar(select(func.count()).select_from(filtered)) or 0

    async def aggregate(
        self,
        filters: dict[str, Any] | None = None,
        group_by: str = "total",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        group_expr = self._group_expr(group_by)
        group_key = group_expr.label("group_key")
        stmt = self._filtered_stmt(filters).with_only_columns(
            group_key,
            func.count(UsageLog.id).label("request_count"),
            func.coalesce(func.sum(case((UsageLog.status == "success", 1), else_=0)), 0).label(
                "success_count"
            ),
            func.coalesce(func.sum(case((UsageLog.status != "success", 1), else_=0)), 0).label(
                "error_count"
            ),
            func.coalesce(func.sum(UsageLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(UsageLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(UsageLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(UsageLog.cached_input_tokens), 0).label("cached_input_tokens"),
            func.coalesce(func.sum(UsageLog.total_cost), 0).label("total_cost"),
            func.coalesce(func.avg(UsageLog.latency_ms), 0).label("avg_latency_ms"),
            func.coalesce(func.sum(case((UsageLog.cache_hit.is_(True), 1), else_=0)), 0).label(
                "cache_hit_count"
            ),
            func.coalesce(
                func.sum(case((UsageLog.failover_triggered.is_(True), 1), else_=0)), 0
            ).label("failover_count"),
            func.coalesce(func.sum(case((UsageLog.stream.is_(True), 1), else_=0)), 0).label(
                "stream_count"
            ),
            func.coalesce(
                func.sum(case((UsageLog.usage_status.in_(["parsed", "estimated"]), 1), else_=0)), 0
            ).label("parsed_usage_count"),
            func.coalesce(
                func.sum(case((UsageLog.pricing_status == "missing_price_config", 1), else_=0)), 0
            ).label("missing_price_count"),
        )
        stmt = stmt.group_by(group_expr).order_by(desc("request_count")).limit(limit)
        rows = (await self.session.execute(stmt)).mappings().all()
        return [
            {
                "group_key": str(row["group_key"] if row["group_key"] is not None else "none"),
                "request_count": int(row["request_count"] or 0),
                "success_count": int(row["success_count"] or 0),
                "error_count": int(row["error_count"] or 0),
                "total_tokens": int(row["total_tokens"] or 0),
                "prompt_tokens": int(row["prompt_tokens"] or 0),
                "completion_tokens": int(row["completion_tokens"] or 0),
                "cached_input_tokens": int(row["cached_input_tokens"] or 0),
                "total_cost": row["total_cost"],
                "avg_latency_ms": float(row["avg_latency_ms"] or 0),
                "cache_hit_count": int(row["cache_hit_count"] or 0),
                "failover_count": int(row["failover_count"] or 0),
                "stream_count": int(row["stream_count"] or 0),
                "parsed_usage_count": int(row["parsed_usage_count"] or 0),
                "missing_price_count": int(row["missing_price_count"] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _group_expr(group_by: str):
        if group_by == "day":
            return func.date(UsageLog.created_at)
        if group_by == "client":
            return UsageLog.client_id
        if group_by == "api_key":
            return UsageLog.api_key_id
        if group_by == "provider":
            return UsageLog.provider_id
        if group_by == "model":
            return UsageLog.model_id
        if group_by == "model_alias":
            return UsageLog.model_alias
        if group_by == "status":
            return UsageLog.status
        if group_by == "call_mode":
            return UsageLog.call_mode
        return literal("total")

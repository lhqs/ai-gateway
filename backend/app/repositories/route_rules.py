from sqlalchemy import select

from app.db.models import ModelAlias, RouteRule
from app.repositories.base import Repository


class RouteRuleRepository(Repository[RouteRule]):
    model = RouteRule

    async def get_for_alias(self, alias: str) -> tuple[ModelAlias, RouteRule] | None:
        stmt = (
            select(ModelAlias, RouteRule)
            .join(RouteRule, RouteRule.model_alias_id == ModelAlias.id)
            .where(ModelAlias.alias == alias, ModelAlias.status == "active", RouteRule.status == "active")
            .order_by(RouteRule.priority.asc(), RouteRule.id.asc())
            .limit(1)
        )
        row = (await self.session.execute(stmt)).first()
        if not row:
            return None
        return row[0], row[1]

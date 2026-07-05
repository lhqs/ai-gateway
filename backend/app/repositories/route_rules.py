from sqlalchemy import delete, select

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

    async def remove_model_references(self, model_ids: list[int]) -> None:
        if not model_ids:
            return

        await self.session.execute(delete(RouteRule).where(RouteRule.primary_model_id.in_(model_ids)))
        result = await self.session.scalars(select(RouteRule))
        removed_ids = set(model_ids)
        for route_rule in result:
            fallback_ids = [
                model_id
                for model_id in route_rule.fallback_model_ids
                if model_id not in removed_ids
            ]
            if fallback_ids != route_rule.fallback_model_ids:
                route_rule.fallback_model_ids = fallback_ids
        await self.session.flush()

    async def delete_for_alias(self, alias_id: int) -> None:
        await self.session.execute(delete(RouteRule).where(RouteRule.model_alias_id == alias_id))
        await self.session.flush()

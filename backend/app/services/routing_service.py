from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Model, ModelAlias, Provider, RouteRule
from app.repositories.models import ModelRepository
from app.repositories.providers import ProviderRepository
from app.repositories.route_rules import RouteRuleRepository


@dataclass(slots=True)
class RouteTarget:
    alias: ModelAlias
    rule: RouteRule
    model: Model
    provider: Provider


class RoutingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.route_rules = RouteRuleRepository(session)
        self.models = ModelRepository(session)
        self.providers = ProviderRepository(session)

    async def resolve(self, model_alias: str) -> RouteTarget:
        found = await self.route_rules.get_for_alias(model_alias)
        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No route rule found for model alias: {model_alias}",
            )
        alias, rule = found
        model = await self.models.get_active(rule.primary_model_id)
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary model is unavailable")
        provider = await self.providers.get(model.provider_id)
        if not provider or provider.status != "active":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider is unavailable")
        return RouteTarget(alias=alias, rule=rule, model=model, provider=provider)

    async def resolve_model(self, model_id: int) -> tuple[Model, Provider]:
        model = await self.models.get_active(model_id)
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} is unavailable")
        provider = await self.providers.get(model.provider_id)
        if not provider or provider.status != "active":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider is unavailable")
        return model, provider

from datetime import datetime

from sqlalchemy import func, or_, select

from app.db.models import ModelPriceConfig
from app.repositories.base import Repository


class ModelPriceConfigRepository(Repository[ModelPriceConfig]):
    model = ModelPriceConfig

    def _filtered_query(
        self,
        model_id: int | None = None,
        currency_code: str | None = None,
        provider_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
    ):
        query = select(ModelPriceConfig)
        if model_id is not None:
            query = query.where(ModelPriceConfig.model_id == model_id)
        if currency_code:
            query = query.where(ModelPriceConfig.currency_code == currency_code.upper())
        if provider_id is not None:
            query = query.where(ModelPriceConfig.provider_id == provider_id)
        if status:
            query = query.where(ModelPriceConfig.status == status)
        if search:
            query = query.where(ModelPriceConfig.model_name.ilike(f"%{search}%"))
        return query

    async def list_filtered(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        model_id: int | None = None,
        currency_code: str | None = None,
        provider_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list[ModelPriceConfig]:
        query = (
            self._filtered_query(model_id, currency_code, provider_id, status, search)
            .order_by(ModelPriceConfig.model_id, ModelPriceConfig.currency_code, ModelPriceConfig.id)
            .limit(limit)
            .offset(offset)
        )
        return list(await self.session.scalars(query))

    async def count_filtered(
        self,
        *,
        model_id: int | None = None,
        currency_code: str | None = None,
        provider_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(
            self._filtered_query(model_id, currency_code, provider_id, status, search).subquery()
        )
        return await self.session.scalar(query) or 0

    async def get_active_for_model(
        self, model_id: int, currency_code: str, at_time: datetime
    ) -> ModelPriceConfig | None:
        return await self.session.scalar(
            select(ModelPriceConfig)
            .where(
                ModelPriceConfig.model_id == model_id,
                ModelPriceConfig.currency_code == currency_code.upper(),
                ModelPriceConfig.status == "active",
                ModelPriceConfig.effective_from <= at_time,
                or_(ModelPriceConfig.effective_to.is_(None), ModelPriceConfig.effective_to > at_time),
            )
            .order_by(ModelPriceConfig.effective_from.desc(), ModelPriceConfig.id.desc())
            .limit(1)
        )

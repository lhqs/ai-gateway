from sqlalchemy import delete, select

from app.db.models import Model
from app.repositories.base import Repository


class ModelRepository(Repository[Model]):
    model = Model

    async def get_active(self, model_id: int) -> Model | None:
        return await self.session.scalar(
            select(Model).where(Model.id == model_id, Model.status == "active")
        )

    async def list_ids_for_provider(self, provider_id: int) -> list[int]:
        result = await self.session.scalars(select(Model.id).where(Model.provider_id == provider_id))
        return list(result)

    async def delete_for_provider(self, provider_id: int) -> None:
        await self.session.execute(delete(Model).where(Model.provider_id == provider_id))
        await self.session.flush()

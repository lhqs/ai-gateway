from sqlalchemy import select

from app.db.models import Model
from app.repositories.base import Repository


class ModelRepository(Repository[Model]):
    model = Model

    async def get_active(self, model_id: int) -> Model | None:
        return await self.session.scalar(
            select(Model).where(Model.id == model_id, Model.status == "active")
        )

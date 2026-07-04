from sqlalchemy import select

from app.db.models import Client
from app.repositories.base import Repository


class ClientRepository(Repository[Client]):
    model = Client

    async def get_active(self, client_id: int) -> Client | None:
        return await self.session.scalar(
            select(Client).where(Client.id == client_id, Client.status == "active")
        )

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db.models import CacheEntry
from app.repositories.base import Repository


class CacheEntryRepository(Repository[CacheEntry]):
    model = CacheEntry

    async def upsert_metadata(
        self,
        *,
        cache_key: str,
        client_id: int,
        model_alias: str,
        request_hash: str,
        response_body: dict[str, Any],
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        expires_at: datetime,
    ) -> CacheEntry:
        item = await self.session.scalar(select(CacheEntry).where(CacheEntry.cache_key == cache_key))
        data = {
            "client_id": client_id,
            "model_alias": model_alias,
            "request_hash": request_hash,
            "response_body": response_body,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "expires_at": expires_at,
        }
        if item:
            for key, value in data.items():
                setattr(item, key, value)
            await self.session.flush()
            return item

        item = CacheEntry(cache_key=cache_key, **data)
        self.session.add(item)
        await self.session.flush()
        return item

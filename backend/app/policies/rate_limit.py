from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import get_settings


class RateLimiter:
    def __init__(self, redis: Redis | None) -> None:
        self.redis = redis
        self.settings = get_settings()

    async def check(self, key: str, limit: int | None = None, window_seconds: int = 60) -> None:
        limit = limit or self.settings.default_rate_limit_per_minute
        if limit <= 0 or self.redis is None:
            return
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, window_seconds)
        if count > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

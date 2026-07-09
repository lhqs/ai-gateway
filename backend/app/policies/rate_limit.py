from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import get_settings


class RateLimiter:
    def __init__(self, redis: Redis | None) -> None:
        self.redis = redis
        self.settings = get_settings()

    async def check(self, key: str, limit: int | None = None, window_seconds: int = 60) -> None:
        if limit is None:
            limit = self.settings.default_rate_limit_per_minute
        if limit <= 0 or self.redis is None:
            return
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, window_seconds)
        if count > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


def configured_limit(config: dict | None, key: str = "rate_limit_per_minute") -> int | None:
    if not config:
        return None
    value = config.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def strictest_limit(*limits: int | None) -> int | None:
    configured = [limit for limit in limits if limit is not None]
    if not configured:
        return None
    return min(configured)

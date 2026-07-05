import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings


class CacheService:
    def __init__(self, redis: Redis | None) -> None:
        self.redis = redis
        self.settings = get_settings()

    def build_request_hash(self, client_id: int, model_alias: str, body: dict[str, Any]) -> str:
        relevant = {
            "client_id": client_id,
            "model": model_alias,
            "messages": body.get("messages"),
            "temperature": body.get("temperature"),
            "top_p": body.get("top_p"),
            "max_tokens": body.get("max_tokens"),
            "tools": body.get("tools"),
            "tool_choice": body.get("tool_choice"),
            "response_format": body.get("response_format"),
            "stop": body.get("stop"),
        }
        encoded = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def build_cache_key(self, request_hash: str) -> str:
        return f"{self.settings.cache_namespace}:chat-cache:{request_hash}"

    async def get_json(self, cache_key: str) -> dict[str, Any] | None:
        if not self.redis:
            return None
        value = await self.redis.get(cache_key)
        if not value:
            return None
        return json.loads(value)

    async def set_json(self, cache_key: str, value: dict[str, Any], ttl_seconds: int) -> bool:
        if not self.redis:
            return False
        await self.redis.set(cache_key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
        return True

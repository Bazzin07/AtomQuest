import json
from typing import Any

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from redis.exceptions import RedisError


class JsonCache:
    def __init__(self, redis: Redis, *, ttl_seconds: int = 600) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self.redis.get(key)
        except RedisError:
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set(self, key: str, value: Any) -> None:
        try:
            await self.redis.set(key, json.dumps(jsonable_encoder(value)), ex=self.ttl_seconds)
        except (TypeError, RedisError):
            return

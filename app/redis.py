import json
import logging
from typing import Any

import redis.asyncio as redis


async def fetch_redis_cache(
    redis_client: redis.Redis, redis_key: str, logger: logging.Logger
) -> Any | None:
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except redis.RedisError:
        logger.error(f"Error fetching key {redis_key} from Redis")
        return None


async def update_redis_cache(
    redis_client: redis.Redis,
    redis_key: str,
    exp_time: int,
    data: Any,
    logger: logging.Logger,
) -> None:
    try:
        await redis_client.setex(redis_key, exp_time, json.dumps(data))
    except redis.RedisError:
        logger.error(f"Error saving values for key {redis_key} into Redis")


async def invalidate_redis_cache(
    redis_client: redis.Redis, redis_key: str, logger: logging.Logger
) -> None:
    try:
        await redis_client.delete(redis_key)
    except redis.RedisError as e:
        logger.error(f"Redis cache invalidation failed for key {redis_key}: {e}")

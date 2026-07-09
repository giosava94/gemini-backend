import asyncio
import json
import logging
from typing import Any, Callable

import redis.asyncio as redis

from app.config import get_settings

WTIME = 0.1  # Lock waiting time 0.1s

logger = logging.getLogger("gemini_backend.redis")


async def create_redis_client() -> redis.Redis | None:
    logger.debug("Creating Redis client...")
    s = get_settings()
    redis_client = redis.Redis(host=s.redis_host, decode_responses=True)
    try:
        await redis_client.ping()
        logger.info("Redis client initialized and connected")
        return redis_client
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")


async def close_redis_connection(redis_client: redis.Redis | None) -> None:
    """Close the Redis client connection.

    A no-op when *redis_client* is ``None`` (e.g. if startup failed before the
    driver was created).
    """
    if redis_client is not None:
        logger.debug("Closing Redis client connection...")
        await redis_client.close()
        logger.info("Redis client connection closed")


async def fetch_redis_cache(
    redis_client: redis.Redis, key: str, logger: logging.Logger
) -> Any | None:
    try:
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)
    except redis.RedisError:
        logger.error(f"Error fetching key {key} from Redis")


async def update_redis_cache(
    redis_client: redis.Redis,
    key: str,
    ttl: int,
    data: Any,
    logger: logging.Logger,
) -> None:
    try:
        await redis_client.setex(key, ttl, json.dumps(data))
    except redis.RedisError:
        logger.error(f"Error saving values for key {key} into Redis")


async def invalidate_redis_cache(
    redis_client: redis.Redis, key: str, logger: logging.Logger
) -> None:
    try:
        await redis_client.delete(key)
    except redis.RedisError as e:
        logger.error(f"Redis cache invalidation failed for key {key}: {e}")


async def set_lock(
    redis_client: redis.Redis, key: str, ttl: int, logger: logging.Logger
) -> bool | str | bytes | None:
    try:
        return await redis_client.set(
            key, "1", ex=ttl, nx=True
        )  # Only set if not exists
    except redis.RedisError:
        logger.error("Error acquiring Redis lock")


async def get_with_lock(
    redis_client: redis.Redis, key: str, fetch_func: Callable, logger: logging.Logger
):
    """Prevent cache stampede with lock"""
    settings = get_settings()
    while True:
        # Try cache first
        cached = await fetch_redis_cache(redis_client, key, logger)
        if cached:
            return cached

        # Try to acquire lock
        lock_key = f"{key}:lock"
        lock_acquired = await set_lock(
            redis_client, lock_key, settings.redis_lock_exp_time, logger
        )

        if lock_acquired:
            # We got the lock, fetch data. Release the lock anyway
            try:
                data = await fetch_func()
                await update_redis_cache(
                    redis_client, key, settings.redis_exp_time, data, logger
                )
                return data
            finally:
                await invalidate_redis_cache(redis_client, lock_key, logger)
        else:
            # Someone else is fetching, wait a bit and retry
            await asyncio.sleep(WTIME)

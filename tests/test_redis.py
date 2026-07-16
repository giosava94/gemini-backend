"""Unit tests for app/redis.py.

All Redis client calls and asyncio.sleep are replaced with AsyncMock /
MagicMock so no real Redis server is required.  Settings that influence
TTLs are patched via a simple Settings stub.

``pytest-asyncio`` is not installed in this project, so every test drives
the coroutine under test synchronously via ``asyncio.run()``.
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as aioredis

from app.redis import (
    WTIME,
    close_redis_connection,
    create_redis_client,
    fetch_redis_cache,
    get_with_lock,
    invalidate_redis_cache,
    set_lock,
    update_redis_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis() -> AsyncMock:
    """Return an AsyncMock standing in for a redis.asyncio.Redis client."""
    return AsyncMock()


def _make_logger() -> MagicMock:
    return MagicMock(spec=logging.Logger)


def _make_settings(exp_time: int = 3600, lock_exp_time: int = 10) -> MagicMock:
    s = MagicMock()
    s.redis_exp_time = exp_time
    s.redis_lock_exp_time = lock_exp_time
    return s


def _settings_patch(exp_time: int = 3600, lock_exp_time: int = 10):
    return patch(
        "app.redis.get_settings",
        return_value=_make_settings(exp_time, lock_exp_time),
    )


# ---------------------------------------------------------------------------
# create_redis_client
# ---------------------------------------------------------------------------


class TestCreateRedisClient:
    def test_returns_client_on_successful_ping(self):
        """Returns the Redis client when ping succeeds."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)

        with (
            patch(
                "app.redis.get_settings", return_value=MagicMock(redis_host="localhost")
            ),
            patch("app.redis.redis.Redis", return_value=mock_client),
        ):
            result = asyncio.run(create_redis_client())

        assert result is mock_client
        mock_client.ping.assert_awaited_once()

    def test_returns_none_on_connection_error(self):
        """Returns None when ping raises a ConnectionError."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=aioredis.ConnectionError("refused"))

        with (
            patch(
                "app.redis.get_settings", return_value=MagicMock(redis_host="localhost")
            ),
            patch("app.redis.redis.Redis", return_value=mock_client),
        ):
            result = asyncio.run(create_redis_client())

        assert result is None

    def test_uses_redis_host_from_settings(self):
        """The Redis client is created with the host from settings."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)

        with (
            patch(
                "app.redis.get_settings", return_value=MagicMock(redis_host="myhost")
            ),
            patch("app.redis.redis.Redis", return_value=mock_client) as mock_cls,
        ):
            asyncio.run(create_redis_client())

        mock_cls.assert_called_once_with(host="myhost", decode_responses=True)


# ---------------------------------------------------------------------------
# close_redis_connection
# ---------------------------------------------------------------------------


class TestCloseRedisConnection:
    def test_closes_client_when_not_none(self):
        """close() is awaited on a non-None client."""
        mock_client = AsyncMock()
        asyncio.run(close_redis_connection(mock_client))
        mock_client.close.assert_awaited_once()

    def test_noop_when_client_is_none(self):
        """No exception is raised when client is None."""
        asyncio.run(close_redis_connection(None))  # must not raise


# ---------------------------------------------------------------------------
# fetch_redis_cache
# ---------------------------------------------------------------------------


class TestFetchRedisCache:
    def test_returns_parsed_json_on_cache_hit(self):
        """Returns the deserialised value when the key exists in Redis."""
        payload = {"id": 1, "name": "LEBT"}
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=json.dumps(payload))

        result = asyncio.run(
            fetch_redis_cache(redis_client, "beam_line:1", _make_logger())
        )

        assert result == payload
        redis_client.get.assert_awaited_once_with("beam_line:1")

    def test_returns_none_on_cache_miss(self):
        """Returns None when the key is absent (get returns None)."""
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=None)

        result = asyncio.run(
            fetch_redis_cache(redis_client, "beam_line:99", _make_logger())
        )

        assert result is None

    def test_returns_none_on_redis_error(self):
        """Returns None (silently) when a RedisError is raised."""
        redis_client = _make_redis()
        redis_client.get = AsyncMock(side_effect=aioredis.RedisError("oops"))
        log = _make_logger()

        result = asyncio.run(fetch_redis_cache(redis_client, "beam_line:1", log))

        assert result is None
        log.error.assert_called_once()

    def test_logs_error_key_name_on_failure(self):
        """The error log message includes the key name."""
        redis_client = _make_redis()
        redis_client.get = AsyncMock(side_effect=aioredis.RedisError("boom"))
        log = _make_logger()

        asyncio.run(fetch_redis_cache(redis_client, "my_key", log))

        assert "my_key" in log.error.call_args[0][0]

    def test_handles_complex_nested_json(self):
        """Nested dicts and lists in the cached value are deserialised correctly."""
        payload = {"links": {"adjacents": "/foo"}, "data": {"id": 1, "labels": ["a"]}}
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=json.dumps(payload))

        result = asyncio.run(fetch_redis_cache(redis_client, "k", _make_logger()))

        assert result == payload


# ---------------------------------------------------------------------------
# update_redis_cache
# ---------------------------------------------------------------------------


class TestUpdateRedisCache:
    def test_calls_setex_with_correct_args(self):
        """setex is called with the key, TTL, and JSON-serialised data."""
        redis_client = _make_redis()
        data = {"id": 1}

        asyncio.run(
            update_redis_cache(redis_client, "beam_line:1", 3600, data, _make_logger())
        )

        redis_client.setex.assert_awaited_once_with(
            "beam_line:1", 3600, json.dumps(data)
        )

    def test_serialises_complex_data(self):
        """Nested structures are JSON-serialised before being stored."""
        redis_client = _make_redis()
        data = {
            "links": {"line_items": "/api/v1/beam-lines/1/line-items"},
            "list": [1, 2],
        }

        asyncio.run(update_redis_cache(redis_client, "k", 60, data, _make_logger()))

        stored = redis_client.setex.call_args[0][2]
        assert json.loads(stored) == data

    def test_logs_error_on_redis_error(self):
        """Logs an error message when setex raises RedisError."""
        redis_client = _make_redis()
        redis_client.setex = AsyncMock(side_effect=aioredis.RedisError("fail"))
        log = _make_logger()

        asyncio.run(update_redis_cache(redis_client, "my_key", 60, {}, log))

        log.error.assert_called_once()
        assert "my_key" in log.error.call_args[0][0]

    def test_does_not_raise_on_redis_error(self):
        """RedisError is swallowed — the function must not propagate it."""
        redis_client = _make_redis()
        redis_client.setex = AsyncMock(side_effect=aioredis.RedisError("fail"))

        asyncio.run(
            update_redis_cache(redis_client, "k", 60, {}, _make_logger())
        )  # must not raise

    def test_uses_provided_ttl(self):
        """The TTL argument is forwarded unchanged to setex."""
        redis_client = _make_redis()
        asyncio.run(update_redis_cache(redis_client, "k", 120, {}, _make_logger()))
        assert redis_client.setex.call_args[0][1] == 120


# ---------------------------------------------------------------------------
# invalidate_redis_cache
# ---------------------------------------------------------------------------


class TestInvalidateRedisCache:
    def test_calls_delete_with_key(self):
        """delete is called with the correct key."""
        redis_client = _make_redis()
        asyncio.run(invalidate_redis_cache(redis_client, "beam_line:1", _make_logger()))
        redis_client.delete.assert_awaited_once_with("beam_line:1")

    def test_logs_error_on_redis_error(self):
        """Logs an error message when delete raises RedisError."""
        redis_client = _make_redis()
        redis_client.delete = AsyncMock(side_effect=aioredis.RedisError("gone"))
        log = _make_logger()

        asyncio.run(invalidate_redis_cache(redis_client, "my_key", log))

        log.error.assert_called_once()
        assert "my_key" in log.error.call_args[0][0]

    def test_does_not_raise_on_redis_error(self):
        """RedisError is swallowed — the function must not propagate it."""
        redis_client = _make_redis()
        redis_client.delete = AsyncMock(side_effect=aioredis.RedisError("gone"))

        asyncio.run(
            invalidate_redis_cache(redis_client, "k", _make_logger())
        )  # must not raise


# ---------------------------------------------------------------------------
# set_lock
# ---------------------------------------------------------------------------


class TestSetLock:
    def test_returns_truthy_when_lock_acquired(self):
        """Returns a truthy value when SET NX succeeds (lock not previously held)."""
        redis_client = _make_redis()
        redis_client.set = AsyncMock(return_value=True)

        result = asyncio.run(set_lock(redis_client, "my_key:lock", 10, _make_logger()))

        assert result

    def test_returns_none_when_lock_already_held(self):
        """Returns None when SET NX returns None (lock already held)."""
        redis_client = _make_redis()
        redis_client.set = AsyncMock(return_value=None)

        result = asyncio.run(set_lock(redis_client, "my_key:lock", 10, _make_logger()))

        assert result is None

    def test_calls_set_with_nx_and_ex(self):
        """set() is called with nx=True and the correct ex (TTL) value."""
        redis_client = _make_redis()
        redis_client.set = AsyncMock(return_value=True)

        asyncio.run(set_lock(redis_client, "k:lock", 15, _make_logger()))

        redis_client.set.assert_awaited_once_with("k:lock", "1", ex=15, nx=True)

    def test_returns_none_on_redis_error(self):
        """Returns None when a RedisError is raised."""
        redis_client = _make_redis()
        redis_client.set = AsyncMock(side_effect=aioredis.RedisError("fail"))
        log = _make_logger()

        result = asyncio.run(set_lock(redis_client, "k:lock", 10, log))

        assert result is None
        log.error.assert_called_once()

    def test_does_not_raise_on_redis_error(self):
        """RedisError is swallowed — the function must not propagate it."""
        redis_client = _make_redis()
        redis_client.set = AsyncMock(side_effect=aioredis.RedisError("fail"))

        asyncio.run(
            set_lock(redis_client, "k:lock", 10, _make_logger())
        )  # must not raise


# ---------------------------------------------------------------------------
# get_with_lock
# ---------------------------------------------------------------------------


class TestGetWithLock:
    """Tests for the cache-stampede-prevention loop.

    The function loops until it either finds a cache hit or acquires the lock,
    fetches fresh data, caches it, and returns it.
    """

    def test_returns_cached_value_immediately(self):
        """Returns the cached value on the very first iteration without calling fetch_func."""
        payload = {"id": 1, "name": "LEBT"}
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=json.dumps(payload))

        fetch_func = AsyncMock(return_value={"id": 99})

        with _settings_patch():
            result = asyncio.run(
                get_with_lock(redis_client, "beam_line:1", fetch_func, _make_logger())
            )

        assert result == payload
        fetch_func.assert_not_awaited()

    def test_fetches_and_caches_when_cache_miss_and_lock_acquired(self):
        """Fetches fresh data, stores it in Redis, and returns it when the lock is acquired."""
        fresh_data = {"id": 1, "name": "LEBT"}
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock(return_value=True)  # lock acquired
        redis_client.setex = AsyncMock(return_value=True)  # store data
        redis_client.delete = AsyncMock(return_value=1)  # release lock

        fetch_func = AsyncMock(return_value=fresh_data)

        with _settings_patch(exp_time=3600, lock_exp_time=10):
            result = asyncio.run(
                get_with_lock(redis_client, "beam_line:1", fetch_func, _make_logger())
            )

        assert result == fresh_data
        fetch_func.assert_awaited_once()

    def test_stores_fetched_data_in_cache(self):
        """After fetching, setex is called with the correct key, TTL, and JSON data."""
        fresh_data = {"id": 2}
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock(return_value=True)
        redis_client.setex = AsyncMock(return_value=True)
        redis_client.delete = AsyncMock(return_value=1)

        with _settings_patch(exp_time=1800):
            asyncio.run(
                get_with_lock(
                    redis_client,
                    "mykey",
                    AsyncMock(return_value=fresh_data),
                    _make_logger(),
                )
            )

        redis_client.setex.assert_awaited_once_with(
            "mykey", 1800, json.dumps(fresh_data)
        )

    def test_releases_lock_after_fetch(self):
        """The lock key is deleted (released) after a successful fetch."""
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock(return_value=True)
        redis_client.setex = AsyncMock(return_value=True)
        redis_client.delete = AsyncMock(return_value=1)

        with _settings_patch():
            asyncio.run(
                get_with_lock(
                    redis_client, "mykey", AsyncMock(return_value={}), _make_logger()
                )
            )

        redis_client.delete.assert_awaited_once_with("mykey:lock")

    def test_releases_lock_even_when_fetch_raises(self):
        """The lock is released even when the fetch function raises an exception."""
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock(return_value=True)
        redis_client.setex = AsyncMock(return_value=True)
        redis_client.delete = AsyncMock(return_value=1)

        async def failing_fetch():
            raise RuntimeError("db down")

        with _settings_patch():
            with pytest.raises(RuntimeError, match="db down"):
                asyncio.run(
                    get_with_lock(redis_client, "mykey", failing_fetch, _make_logger())
                )

        redis_client.delete.assert_awaited_once_with("mykey:lock")

    def test_waits_and_retries_when_lock_held_then_cache_populated(self):
        """Sleeps and retries when the lock is held; returns the value that appears
        in the cache on the next iteration."""
        payload = {"id": 5}
        redis_client = _make_redis()
        # First get → cache miss; second get (after sleep) → cache hit
        redis_client.get = AsyncMock(side_effect=[None, json.dumps(payload)])
        redis_client.set = AsyncMock(return_value=None)  # lock held by someone else

        fetch_func = AsyncMock(return_value={"id": 99})

        with (
            _settings_patch(),
            patch("app.redis.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            result = asyncio.run(
                get_with_lock(redis_client, "k", fetch_func, _make_logger())
            )

        assert result == payload
        mock_sleep.assert_awaited_once_with(WTIME)
        fetch_func.assert_not_awaited()

    def test_lock_key_uses_key_plus_lock_suffix(self):
        """The lock key is formed by appending ':lock' to the cache key."""
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock(return_value=True)
        redis_client.setex = AsyncMock(return_value=True)
        redis_client.delete = AsyncMock(return_value=1)

        with _settings_patch(lock_exp_time=5):
            asyncio.run(
                get_with_lock(
                    redis_client,
                    "beam_line:7",
                    AsyncMock(return_value={}),
                    _make_logger(),
                )
            )

        set_call = redis_client.set.call_args
        assert set_call[0][0] == "beam_line:7:lock"
        assert set_call[1]["ex"] == 5

    def test_sleep_uses_wtime_constant(self):
        """asyncio.sleep is called with the WTIME module constant."""
        payload = {"id": 1}
        redis_client = _make_redis()
        redis_client.get = AsyncMock(side_effect=[None, json.dumps(payload)])
        redis_client.set = AsyncMock(return_value=None)  # lock held

        with (
            _settings_patch(),
            patch("app.redis.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            asyncio.run(get_with_lock(redis_client, "k", AsyncMock(), _make_logger()))

        mock_sleep.assert_awaited_once_with(WTIME)

    def test_multiple_wait_cycles_before_cache_hit(self):
        """Sleeps multiple times if the lock remains held across several iterations."""
        payload = {"id": 3}
        redis_client = _make_redis()
        # Three cache misses, then a hit on the fourth call
        redis_client.get = AsyncMock(
            side_effect=[None, None, None, json.dumps(payload)]
        )
        redis_client.set = AsyncMock(return_value=None)  # lock held throughout

        with (
            _settings_patch(),
            patch("app.redis.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            result = asyncio.run(
                get_with_lock(redis_client, "k", AsyncMock(), _make_logger())
            )

        assert result == payload
        assert mock_sleep.await_count == 3

    def test_returns_none_data_from_fetch_func(self):
        """A None return value from fetch_func is stored and returned correctly."""
        redis_client = _make_redis()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock(return_value=True)
        redis_client.setex = AsyncMock(return_value=True)
        redis_client.delete = AsyncMock(return_value=1)

        with _settings_patch():
            result = asyncio.run(
                get_with_lock(
                    redis_client, "k", AsyncMock(return_value=None), _make_logger()
                )
            )

        assert result is None

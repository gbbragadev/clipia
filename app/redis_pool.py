"""Centralized Redis connection pool for the ClipIA application."""

import redis
from app.config import settings

_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> redis.Redis:
    """Return a Redis client using the shared connection pool."""
    return redis.Redis(connection_pool=_pool)

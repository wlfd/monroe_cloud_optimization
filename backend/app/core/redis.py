"""Redis async client dependency.

The Redis client is initialized in main.py's lifespan and stored on
app.state.redis. This module provides the FastAPI dependency for injection.

Usage:
    @router.get("/foo")
    async def foo(redis: aioredis.Redis = Depends(get_redis)):
        ...
"""

import redis.asyncio as aioredis
from fastapi import Request


async def get_redis(request: Request) -> aioredis.Redis:
    """FastAPI dependency: returns the shared Redis client from app.state."""
    return request.app.state.redis

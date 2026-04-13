import redis.asyncio as redis

from .config import REDIS_URL, REDIS_URL_MISSING_ERROR

if not REDIS_URL:
    raise RuntimeError(REDIS_URL_MISSING_ERROR)

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
)
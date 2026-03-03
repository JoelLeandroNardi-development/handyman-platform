from __future__ import annotations

IDEMPOTENCY_DEFAULT_TTL_SECONDS = 3600


async def already_processed(
    *,
    redis_client,
    event_id: str,
    ttl_seconds: int = IDEMPOTENCY_DEFAULT_TTL_SECONDS,
    prefix: str = "processed_event",
) -> bool:
    """
    Redis-backed idempotency marker.
    Returns True if already processed, else sets marker and returns False.
    """
    key = f"{prefix}:{event_id}"
    if await redis_client.get(key):
        return True
    await redis_client.set(key, "1", ex=ttl_seconds)
    return False
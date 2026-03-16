from __future__ import annotations

IDEMPOTENCY_DEFAULT_TTL_SECONDS = 3600


async def already_processed(
    *,
    redis_client,
    event_id: str,
    ttl_seconds: int = IDEMPOTENCY_DEFAULT_TTL_SECONDS,
    prefix: str = "processed_event",
) -> bool:
    key = f"{prefix}:{event_id}"
    was_set = await redis_client.set(key, "1", ex=ttl_seconds, nx=True)
    return not was_set
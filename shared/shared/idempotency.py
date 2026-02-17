from .redis import redis_client

async def is_processed(event_id: str) -> bool:
    return await redis_client.exists(f"event:{event_id}")

async def mark_processed(event_id: str):
    await redis_client.set(f"event:{event_id}", "1", ex=86400)

import asyncio
import json
import time
from dataclasses import dataclass

from .redis_client import redis_client
from .messaging import publisher

# Redis-backed outbox for availability-service (because Availability state is Redis)
OUTBOX_PENDING = "outbox:availability:pending"
OUTBOX_PROCESSING = "outbox:availability:processing"
OUTBOX_DLQ = "outbox:availability:dlq"

POLL_INTERVAL_SECONDS = 0.5
MAX_ATTEMPTS = 25


def _now_ms() -> int:
    return int(time.time() * 1000)


def _envelope(routing_key: str, payload: dict) -> dict:
    return {
        "routing_key": routing_key,
        "payload": payload,
        "attempts": 0,
        "created_at_ms": _now_ms(),
        "last_error": None,
    }


async def enqueue_domain_event(event: dict) -> None:
    """
    Producers should call this instead of publishing directly.
    Enforces routing_key == event["event_type"].

    This keeps HTTP + consumers working even if RabbitMQ is down.
    """
    event_type = (event or {}).get("event_type")
    if not event_type or not isinstance(event_type, str):
        # poison event -> DLQ (do not block caller)
        await redis_client.rpush(OUTBOX_DLQ, json.dumps({"bad_event": event, "reason": "missing_event_type"}))
        return

    rk = event_type.strip()
    if not rk:
        await redis_client.rpush(OUTBOX_DLQ, json.dumps({"bad_event": event, "reason": "empty_event_type"}))
        return

    await redis_client.rpush(OUTBOX_PENDING, json.dumps(_envelope(rk, event)))


async def outbox_stats() -> dict:
    """
    Lightweight stats for /health and debugging.
    """
    pending = await redis_client.llen(OUTBOX_PENDING)
    processing = await redis_client.llen(OUTBOX_PROCESSING)
    dlq = await redis_client.llen(OUTBOX_DLQ)
    return {
        "type": "redis",
        "pending": int(pending or 0),
        "processing": int(processing or 0),
        "dlq": int(dlq or 0),
    }


@dataclass
class OutboxWorker:
    _stop: asyncio.Event = asyncio.Event()
    _task: asyncio.Task | None = None

    async def start(self):
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop.set()
        if self._task:
            try:
                await self._task
            except Exception:
                pass

    async def _run(self):
        while not self._stop.is_set():
            try:
                drained = await self._drain_once()
                if not drained:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=POLL_INTERVAL_SECONDS)
                    except asyncio.TimeoutError:
                        pass
            except Exception as e:
                print(f"[availability-service] outbox worker loop error: {e}")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

    async def _drain_once(self) -> bool:
        raw = await redis_client.rpoplpush(OUTBOX_PENDING, OUTBOX_PROCESSING)
        if not raw:
            return False

        try:
            env = json.loads(raw)
        except Exception:
            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)
            await redis_client.rpush(OUTBOX_DLQ, raw)
            return True

        routing_key = env.get("routing_key")
        payload = env.get("payload")
        attempts = int(env.get("attempts", 0) or 0)

        if not routing_key or payload is None:
            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)
            await redis_client.rpush(OUTBOX_DLQ, raw)
            return True

        try:
            await publisher.publish(routing_key=routing_key, payload=payload)
            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)
            return True
        except Exception as e:
            attempts += 1
            env["attempts"] = attempts
            env["last_error"] = str(e)

            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)

            if attempts >= MAX_ATTEMPTS:
                await redis_client.rpush(OUTBOX_DLQ, json.dumps(env))
            else:
                await redis_client.rpush(OUTBOX_PENDING, json.dumps(env))

            return True


worker = OutboxWorker()
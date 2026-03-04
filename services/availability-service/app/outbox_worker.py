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


async def enqueue_domain_event(routing_key: str, payload: dict):
    """
    Producers should call this instead of publishing directly.
    This keeps HTTP + consumers working even if RabbitMQ is down.
    """
    await redis_client.rpush(OUTBOX_PENDING, json.dumps(_envelope(routing_key, payload)))


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
        # Best-effort (won't crash if Rabbit is briefly down)
        try:
            await publisher.start()
        except Exception:
            pass

        while not self._stop.is_set():
            try:
                drained = await self._drain_once()
                if not drained:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=POLL_INTERVAL_SECONDS)
                    except asyncio.TimeoutError:
                        pass
            except Exception as e:
                print(f"[availability-service] outbox worker loop error: {type(e).__name__}: {e}")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

    async def _drain_once(self) -> bool:
        """
        Uses RPOPLPUSH to move a message to processing before publish.
        On success: remove from processing.
        On failure: increment attempts; move back to pending (or DLQ).
        """
        raw = await redis_client.rpoplpush(OUTBOX_PENDING, OUTBOX_PROCESSING)
        if not raw:
            return False

        try:
            env = json.loads(raw)
        except Exception:
            # poison envelope -> DLQ
            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)
            await redis_client.rpush(OUTBOX_DLQ, raw)
            return True

        routing_key = (env.get("routing_key") or "").strip()
        payload = env.get("payload")
        attempts = int(env.get("attempts", 0) or 0)

        if not routing_key or payload is None:
            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)
            await redis_client.rpush(OUTBOX_DLQ, raw)
            return True

        try:
            # ✅ FIX: keyword-only call + message_id for tracing/idempotency
            message_id = None
            if isinstance(payload, dict):
                message_id = payload.get("event_id")

            await publisher.publish(
                routing_key=routing_key,
                payload=payload,
                message_id=message_id,
            )

            # ack: remove from processing
            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)
            return True

        except Exception as e:
            attempts += 1
            env["attempts"] = attempts
            env["last_error"] = f"{type(e).__name__}: {e}"

            # remove old raw from processing
            await redis_client.lrem(OUTBOX_PROCESSING, 1, raw)

            if attempts >= MAX_ATTEMPTS:
                await redis_client.rpush(OUTBOX_DLQ, json.dumps(env))
                print(
                    "[availability-service] outbox -> DLQ "
                    f"rk={routing_key} attempts={attempts} err={type(e).__name__}: {e}"
                )
            else:
                # retry later
                await redis_client.rpush(OUTBOX_PENDING, json.dumps(env))
                print(
                    "[availability-service] outbox retry "
                    f"rk={routing_key} attempts={attempts} err={type(e).__name__}: {e}"
                )

            return True


worker = OutboxWorker()
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode


DEFAULT_EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "domain_events")


@dataclass(frozen=True)
class RabbitConfig:
    url: Optional[str]
    exchange_name: str = DEFAULT_EXCHANGE_NAME

    @staticmethod
    def from_env(required: bool = False) -> "RabbitConfig":
        url = os.getenv("RABBIT_URL")
        if required and not url:
            raise RuntimeError("RABBIT_URL environment variable is not set")
        return RabbitConfig(url=url, exchange_name=DEFAULT_EXCHANGE_NAME)


class RabbitPublisher:
    """
    Robust, best-effort publisher.

    Design goals:
      - service startup MUST NOT fail if RabbitMQ is temporarily down
      - publish() may fail (caller/outbox retries)
      - reconnects lazily on publish
    """

    def __init__(self, cfg: RabbitConfig):
        self.cfg = cfg
        self.enabled = bool(cfg.url)
        self._conn: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def start(self) -> None:
        """
        Best-effort start.
        If connection fails, do NOT raise; keep enabled but not ready.
        """
        if not self.enabled:
            return

        # already ready
        if self._conn and not self._conn.is_closed and self._exchange is not None:
            return

        try:
            self._conn = await aio_pika.connect_robust(self.cfg.url)  # type: ignore[arg-type]
            self._channel = await self._conn.channel(publisher_confirms=True)
            self._exchange = await self._channel.declare_exchange(
                self.cfg.exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )
        except Exception as e:
            # Do not crash service on startup
            print(f"[shared.mq] publisher.start() failed (will retry on publish): {type(e).__name__}: {e}")
            # clean partial state
            await self.close()

    async def close(self) -> None:
        try:
            if self._channel and not self._channel.is_closed:
                await self._channel.close()
        except Exception:
            pass
        finally:
            self._channel = None
            self._exchange = None

        try:
            if self._conn and not self._conn.is_closed:
                await self._conn.close()
        except Exception:
            pass
        finally:
            self._conn = None

    async def _ensure_ready(self) -> None:
        """
        Ensure we have a working exchange.
        Raises if cannot connect (caller should retry later).
        """
        if not self.enabled:
            raise RuntimeError("RabbitPublisher disabled (no RABBIT_URL)")

        if self._exchange is not None and self._conn and not self._conn.is_closed:
            return

        # try reconnect
        self._conn = await aio_pika.connect_robust(self.cfg.url)  # type: ignore[arg-type]
        self._channel = await self._conn.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self.cfg.exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

    async def publish(
        self,
        *,
        routing_key: str,
        payload: dict,
        message_id: str | None = None,
        headers: dict | None = None,
    ) -> None:
        """
        Publish a JSON message.

        If RabbitMQ is down, raises so the outbox can retry.
        """
        if not self.enabled:
            return

        await self._ensure_ready()

        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        msg = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=message_id,
            headers=headers or {},
        )
        await self._exchange.publish(msg, routing_key=routing_key)  # type: ignore[union-attr]


async def rabbit_connect(cfg: RabbitConfig) -> aio_pika.RobustConnection | None:
    """
    Consumer-side connection helper.
    If cfg.url is None, returns None (events disabled).
    """
    if not cfg.url:
        return None
    return await aio_pika.connect_robust(cfg.url)
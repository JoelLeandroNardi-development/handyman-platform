from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message


@dataclass(frozen=True)
class RabbitConfig:
    url: Optional[str]
    exchange_name: str

    @staticmethod
    def from_env(required: bool = False) -> "RabbitConfig":
        """
        Read config from environment at CALL TIME (not import-time),
        so docker-compose / env_file values are always respected.
        """
        url = os.getenv("RABBIT_URL")
        if required and not url:
            raise RuntimeError("RABBIT_URL environment variable is not set")

        exchange_name = os.getenv("EXCHANGE_NAME", "domain_events").strip()
        if not exchange_name:
            exchange_name = "domain_events"

        return RabbitConfig(url=url, exchange_name=exchange_name)


class RabbitPublisher:
    """
    Robust, best-effort publisher.

    Design goals:
      - service startup MUST NOT fail if RabbitMQ is temporarily down
      - publish() may fail (caller/outbox retries)
      - reconnects lazily on publish
      - detects unroutable messages (mandatory publish) so outbox doesn't mark SENT incorrectly
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

        if self._conn and not self._conn.is_closed and self._exchange is not None:
            return

        try:
            self._conn = await aio_pika.connect_robust(self.cfg.url)
            self._channel = await self._conn.channel(publisher_confirms=True)
            self._exchange = await self._channel.declare_exchange(
                self.cfg.exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )
            print(f"[shared.mq] publisher ready exchange={self.cfg.exchange_name}")
        except Exception as e:
            print(
                f"[shared.mq] publisher.start() failed (will retry on publish): "
                f"{type(e).__name__}: {e}"
            )
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

        self._conn = await aio_pika.connect_robust(self.cfg.url)
        self._channel = await self._conn.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self.cfg.exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        print(f"[shared.mq] publisher reconnected exchange={self.cfg.exchange_name}")

    async def publish(
        self,
        *,
        routing_key: str,
        payload: dict,
        message_id: str | None = None,
        headers: dict | None = None,
        mandatory: bool = True,
    ) -> None:
        """
        Publish a JSON message.

        If RabbitMQ is down, raises so the outbox can retry.

        mandatory=True will raise if the message is unroutable (no bindings),
        preventing the outbox from marking the event as SENT incorrectly.
        """
        if not self.enabled:
            return

        rk = (routing_key or "").strip()
        if not rk:
            raise ValueError("routing_key is required")

        await self._ensure_ready()
        assert self._exchange is not None

        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        msg = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=message_id,
            headers=headers or {},
        )

        try:
            await self._exchange.publish(msg, routing_key=rk, mandatory=mandatory)
            print(
                f"[shared.mq] published exchange={self.cfg.exchange_name} rk={rk} message_id={message_id}"
            )
        except Exception as e:
            print(
                f"[shared.mq] publish failed exchange={self.cfg.exchange_name} rk={rk} "
                f"message_id={message_id} err={type(e).__name__}: {e}"
            )
            raise


async def rabbit_connect(cfg: RabbitConfig) -> aio_pika.RobustConnection | None:
    """
    Consumer-side connection helper.
    If cfg.url is None, returns None (events disabled).
    """
    if not cfg.url:
        return None
    return await aio_pika.connect_robust(cfg.url)
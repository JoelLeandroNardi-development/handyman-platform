from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class NotificationHub:
    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def subscribe(self, user_email: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[user_email].add(queue)
        return queue

    async def unsubscribe(self, user_email: str, queue: asyncio.Queue) -> None:
        subscribers = self._queues.get(user_email)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._queues.pop(user_email, None)

    async def publish(self, user_email: str, payload: dict[str, Any]) -> None:
        for queue in list(self._queues.get(user_email, set())):
            await queue.put(payload)


hub = NotificationHub()

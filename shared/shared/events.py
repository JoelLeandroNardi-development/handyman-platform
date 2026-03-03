from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_event(
    event_type: str,
    data: Dict[str, Any],
    *,
    source: str,
    event_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Standard domain event envelope used across all services.

    Contract:
      - routing_key == event_type
      - occurred_at is ISO8601 UTC string
      - source is the producing service name
    """
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": occurred_at or utc_now_iso(),
        "source": source,
        "data": data or {},
    }
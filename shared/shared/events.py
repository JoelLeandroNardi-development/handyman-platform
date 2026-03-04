from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from fastapi.encoders import jsonable_encoder as _jsonable_encoder
except Exception:
    _jsonable_encoder = None


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


def build_event_jsonable(
    event_type: str,
    data: Dict[str, Any],
    *,
    source: str,
    event_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Same as build_event(), but guarantees the returned object is JSON-serializable.

    Use this when:
      - storing events into SQLAlchemy JSON columns (outbox pattern)
      - publishing to a message bus as JSON
      - returning events as API responses

    It will convert nested datetimes (e.g. desired_start) into ISO strings.
    """
    evt = build_event(
        event_type,
        data,
        source=source,
        event_id=event_id,
        occurred_at=occurred_at,
    )

    if _jsonable_encoder is None:
        return evt

    return _jsonable_encoder(evt)
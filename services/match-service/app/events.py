import uuid
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder


def build_event(event_type: str, data: dict) -> dict:
    evt = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc),
        "data": data,
    }
    return jsonable_encoder(evt)
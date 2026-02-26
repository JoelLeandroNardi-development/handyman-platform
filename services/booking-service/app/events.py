import json
import uuid
from datetime import datetime, timezone

def build_event(event_type: str, data: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

def to_json(event: dict) -> str:
    return json.dumps(event, separators=(",", ":"), ensure_ascii=False)
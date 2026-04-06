from datetime import datetime, timezone
from dateutil import parser
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def parse_dt(x: Any) -> datetime:
    if isinstance(x, datetime):
        return as_utc(x)
    if isinstance(x, str):
        return as_utc(parser.isoparse(x))
    raise ValueError(f"Unsupported datetime type: {type(x).__name__}")
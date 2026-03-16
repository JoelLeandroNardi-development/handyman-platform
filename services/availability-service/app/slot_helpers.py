from __future__ import annotations

from dateutil import parser


def avail_key(email: str) -> str:
    return f"availability:{email}"


def parse_raw_slot(raw: str):
    try:
        s, e = raw.split("|")
        return parser.isoparse(s), parser.isoparse(e)
    except Exception:
        return None

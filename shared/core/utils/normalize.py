from typing import Any

def norm(s: str) -> str:
    return (s or "").strip().lower()

def safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default

def safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default

def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
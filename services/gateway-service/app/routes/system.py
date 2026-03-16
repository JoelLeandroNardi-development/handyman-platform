import asyncio
import httpx
from fastapi import APIRouter, Depends, Request, HTTPException
from typing import List, Dict, Any

from ..security import get_current_user
from ..rbac import require_role
from ..helpers import (
    _breaker_registry,
    _service_urls,
    _fetch_json,
    _overall_status,
)

router = APIRouter()


@router.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "gateway-service"}


@router.get("/system/health", tags=["System"])
async def system_health(request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    services = _service_urls("/health")

    async with httpx.AsyncClient(timeout=2.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_json(client=client, name=n, url=u, request_id=request.state.request_id)
                for n, u in services.items()
            ]
        )

    results.sort(key=lambda x: x["service"])
    return {"status": _overall_status(results), "services": results}


@router.get("/system/rabbit", tags=["System"])
async def system_rabbit(request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    services = _service_urls("/debug/rabbit")

    async with httpx.AsyncClient(timeout=2.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_json(client=client, name=n, url=u, request_id=request.state.request_id)
                for n, u in services.items()
            ]
        )

    results.sort(key=lambda x: x["service"])
    return {"status": _overall_status(results), "services": results}


@router.get("/system/outbox", tags=["System"])
async def system_outbox(request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    services = _service_urls("/health")

    async with httpx.AsyncClient(timeout=2.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_json(client=client, name=n, url=u, request_id=request.state.request_id)
                for n, u in services.items()
            ]
        )

    compact: List[Dict[str, Any]] = []
    for r in results:
        data = r.get("data") or {}
        outbox = None
        exchange_name = None
        events_enabled = None

        if isinstance(data, dict):
            outbox = data.get("outbox")
            exchange_name = data.get("exchange_name")
            events_enabled = data.get("events_enabled")

        compact.append(
            {
                "service": r["service"],
                "status": r.get("status"),
                "http_status": r.get("http_status"),
                "latency_ms": r.get("latency_ms"),
                "exchange_name": exchange_name,
                "events_enabled": events_enabled,
                "outbox": outbox,
            }
        )

    compact.sort(key=lambda x: x["service"])
    overall = "up" if all(x.get("status") == "up" for x in compact) else "degraded"
    return {"status": overall, "services": compact}


@router.get("/system/breakers", tags=["System"])
async def breakers_status(user=Depends(get_current_user)):
    require_role(user, ["admin"])
    statuses = await asyncio.gather(*[b.status() for b in _breaker_registry().values()])
    statuses.sort(key=lambda x: x["name"])
    return {"breakers": statuses}


@router.post("/system/breakers/{name}/close", tags=["System"])
async def breaker_close(name: str, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    b = _breaker_registry().get(name)
    if not b:
        raise HTTPException(status_code=404, detail="Breaker not found")
    await b.close()
    return {"message": "closed", "breaker": await b.status()}


@router.post("/system/breakers/{name}/open", tags=["System"])
async def breaker_open(name: str, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    b = _breaker_registry().get(name)
    if not b:
        raise HTTPException(status_code=404, detail="Breaker not found")
    await b.open()
    return {"message": "opened", "breaker": await b.status()}

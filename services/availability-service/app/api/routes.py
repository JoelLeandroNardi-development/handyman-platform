from __future__ import annotations

from fastapi import APIRouter, Query

from ..application.commands.availability_command_service import AvailabilityCommandService
from ..application.queries.availability_query_service import AvailabilityQueryService
from ..domain.schemas import SetAvailability, OverlapRequest

router = APIRouter()

@router.get("/availability/{email}")
async def get_availability(email: str):
    return await AvailabilityQueryService().get_availability(email)

@router.get("/availability")
async def list_all_availability(
    limit: int = Query(200, ge=1, le=1000),
    cursor: int = Query(0, ge=0),
):
    return await AvailabilityQueryService().list_all_availability(limit, cursor)

@router.get("/reservations/{booking_id}")
async def get_reservation_endpoint(booking_id: str):
    return await AvailabilityQueryService().get_reservation(booking_id)

@router.post("/availability/{email}")
async def set_availability(email: str, data: SetAvailability):
    return await AvailabilityCommandService().set_availability(email, data)

@router.delete("/availability/{email}")
async def clear_availability(email: str):
    return await AvailabilityCommandService().clear_availability(email)

@router.post("/availability/{email}/overlap")
async def check_overlap(email: str, req: OverlapRequest):
    return await AvailabilityCommandService().check_overlap(email, req)

@router.delete("/reservations/{booking_id}")
async def delete_reservation_endpoint(booking_id: str):
    return await AvailabilityCommandService().delete_reservation(booking_id)
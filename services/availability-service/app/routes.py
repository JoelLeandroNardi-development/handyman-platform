from fastapi import APIRouter, HTTPException
from .redis_client import redis_client
from .schemas import SetAvailability

router = APIRouter()


def redis_key(email: str) -> str:
    return f"availability:{email}"


@router.post("/availability/{email}")
async def set_availability(email: str, data: SetAvailability):
    key = redis_key(email)

    # Overwrite existing slots
    await redis_client.delete(key)

    for slot in data.slots:
        value = f"{slot.start}|{slot.end}"
        await redis_client.rpush(key, value)

    return {"message": "Availability updated"}


@router.get("/availability/{email}")
async def get_availability(email: str):
    key = redis_key(email)

    slots = await redis_client.lrange(key, 0, -1)

    parsed = []
    for slot in slots:
        start, end = slot.split("|")
        parsed.append({"start": start, "end": end})

    return {"email": email, "slots": parsed}


@router.delete("/availability/{email}")
async def clear_availability(email: str):
    key = redis_key(email)
    await redis_client.delete(key)

    return {"message": "Availability cleared"}

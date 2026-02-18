import math
import httpx

HANDYMAN_SERVICE_URL = "http://handyman-service:8000"


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def fetch_handymen():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{HANDYMAN_SERVICE_URL}/handymen")
        return response.json()

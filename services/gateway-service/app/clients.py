import httpx
from .config import (
    AUTH_SERVICE_URL,
    USER_SERVICE_URL,
    HANDYMAN_SERVICE_URL,
    AVAILABILITY_SERVICE_URL,
    MATCH_SERVICE_URL,
)


async def post(url: str, payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def put(url: str, payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.put(url, json=payload)
        response.raise_for_status()
        return response.json()


async def get(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def delete(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.delete(url)
        response.raise_for_status()
        return response.json()


# -------- AUTH --------

async def register_user(data: dict):
    return await post(f"{AUTH_SERVICE_URL}/register", data)


async def login_user(data: dict):
    return await post(f"{AUTH_SERVICE_URL}/login", data)


# -------- USER --------

async def create_user(data: dict):
    return await post(f"{USER_SERVICE_URL}/users", data)


async def update_user_location(email: str, data: dict):
    return await put(f"{USER_SERVICE_URL}/users/{email}/location", data)


async def get_user(email: str):
    return await get(f"{USER_SERVICE_URL}/users/{email}")


# -------- HANDYMAN --------

async def create_handyman(data: dict):
    return await post(f"{HANDYMAN_SERVICE_URL}/handymen", data)


async def update_handyman_location(email: str, data: dict):
    return await put(f"{HANDYMAN_SERVICE_URL}/handymen/{email}/location", data)


async def get_handyman(email: str):
    return await get(f"{HANDYMAN_SERVICE_URL}/handymen/{email}")


async def list_handymen():
    return await get(f"{HANDYMAN_SERVICE_URL}/handymen")


# -------- AVAILABILITY --------

async def set_availability(email: str, data: dict):
    return await post(f"{AVAILABILITY_SERVICE_URL}/availability/{email}", data)


async def get_availability(email: str):
    return await get(f"{AVAILABILITY_SERVICE_URL}/availability/{email}")


async def clear_availability(email: str):
    return await delete(f"{AVAILABILITY_SERVICE_URL}/availability/{email}")


# -------- MATCH --------

async def match_request(data: dict):
    return await post(f"{MATCH_SERVICE_URL}/match", data)

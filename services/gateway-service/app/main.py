from fastapi import FastAPI
from typing import List

from .schemas import *
from .clients import *

app = FastAPI(title="Smart API Gateway")


@app.get("/health")
async def health():
    return {"status": "gateway running"}


# ================= AUTH =================

@app.post("/register")
async def register(data: Register):
    return await register_user(data.model_dump())


@app.post("/login", response_model=TokenResponse)
async def login(data: Login):
    return await login_user(data.model_dump())


# ================= USER =================

@app.post("/users")
async def create_user_endpoint(data: CreateUser):
    return await create_user(data.model_dump())


@app.put("/users/{email}/location")
async def update_user_location_endpoint(email: str, data: UpdateUserLocation):
    return await update_user_location(email, data.model_dump())


@app.get("/users/{email}")
async def get_user_endpoint(email: str):
    return await get_user(email)


# ================= HANDYMAN =================

@app.post("/handymen")
async def create_handyman_endpoint(data: CreateHandyman):
    return await create_handyman(data.model_dump())


@app.put("/handymen/{email}/location")
async def update_handyman_location_endpoint(email: str, data: UpdateHandymanLocation):
    return await update_handyman_location(email, data.model_dump())


@app.get("/handymen/{email}")
async def get_handyman_endpoint(email: str):
    return await get_handyman(email)


@app.get("/handymen")
async def list_handymen_endpoint():
    return await list_handymen()


# ================= AVAILABILITY =================

@app.post("/availability/{email}")
async def set_availability_endpoint(email: str, data: SetAvailability):
    return await set_availability(email, data.model_dump())


@app.get("/availability/{email}")
async def get_availability_endpoint(email: str):
    return await get_availability(email)


@app.delete("/availability/{email}")
async def clear_availability_endpoint(email: str):
    return await clear_availability(email)


# ================= MATCH =================

@app.post("/match", response_model=List[MatchResult])
async def match_endpoint(data: MatchRequest):
    return await match_request(data.model_dump())

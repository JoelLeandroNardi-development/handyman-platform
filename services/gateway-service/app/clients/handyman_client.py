from .base_client import call_with_breaker
from ..breakers.circuit_breakers import cb_handyman
from ..config import HANDYMAN_SERVICE_URL

async def create_handyman(data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_handyman, "POST", f"{HANDYMAN_SERVICE_URL}/handymen", data, request_id, user_payload)

async def update_handyman_location(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_handyman, "PUT", f"{HANDYMAN_SERVICE_URL}/handymen/{email}/location", data, request_id, user_payload)

async def update_handyman(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_handyman, "PUT", f"{HANDYMAN_SERVICE_URL}/handymen/{email}", data, request_id, user_payload)

async def delete_handyman(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_handyman, "DELETE", f"{HANDYMAN_SERVICE_URL}/handymen/{email}", None, request_id, user_payload)

async def get_handyman(email: str, request_id: str | None = None, user_payload: dict | None = None):
    return await call_with_breaker(cb_handyman, "GET", f"{HANDYMAN_SERVICE_URL}/handymen/{email}", None, request_id, user_payload)

async def list_handymen(request_id: str | None = None, user_payload: dict | None = None, limit: int = 200, offset: int = 0):
    return await call_with_breaker(cb_handyman, "GET", f"{HANDYMAN_SERVICE_URL}/handymen?limit={limit}&offset={offset}", None, request_id, user_payload)

async def update_handyman_location_and_fetch(email: str, data: dict, request_id: str | None = None, user_payload: dict | None = None):
    await update_handyman_location(email, data, request_id, user_payload)
    return await get_handyman(email, request_id, user_payload)

async def get_skills_catalog(
    request_id: str | None = None,
    user_payload: dict | None = None,
    active_only: bool = True,
):
    active_q = "true" if active_only else "false"
    return await call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/skills-catalog?active_only={active_q}",
        None,
        request_id,
        user_payload,
    )

async def get_skills_catalog_flat(
    request_id: str | None = None,
    user_payload: dict | None = None,
    active_only: bool = True,
):
    active_q = "true" if active_only else "false"
    return await call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/skills-catalog/flat?active_only={active_q}",
        None,
        request_id,
        user_payload,
    )

async def replace_skills_catalog(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await call_with_breaker(
        cb_handyman,
        "PUT",
        f"{HANDYMAN_SERVICE_URL}/admin/skills-catalog",
        data,
        request_id,
        user_payload,
    )

async def patch_skills_catalog(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await call_with_breaker(
        cb_handyman,
        "PATCH",
        f"{HANDYMAN_SERVICE_URL}/admin/skills-catalog",
        data,
        request_id,
        user_payload,
    )

async def get_handymen_with_invalid_skills(
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/admin/handymen/invalid-skills",
        None,
        request_id,
        user_payload,
    )

async def create_handyman_review(
    data: dict,
    request_id: str | None = None,
    user_payload: dict | None = None,
):
    return await call_with_breaker(
        cb_handyman,
        "POST",
        f"{HANDYMAN_SERVICE_URL}/handymen/reviews",
        data,
        request_id,
        user_payload,
    )

async def list_handyman_reviews(
    email: str,
    request_id: str | None = None,
    user_payload: dict | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return await call_with_breaker(
        cb_handyman,
        "GET",
        f"{HANDYMAN_SERVICE_URL}/handymen/{email}/reviews?limit={limit}&offset={offset}",
        None,
        request_id,
        user_payload,
    )
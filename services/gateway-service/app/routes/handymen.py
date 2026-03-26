from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import List

from ..schemas import (
    CreateHandyman,
    UpdateHandymanLocation,
    UpdateHandyman,
    HandymanResponse,
    HandymanReviewResponse,
    SkillCatalogReplaceRequest,
    SkillCatalogPatchRequest,
    SkillCatalogFlatResponse,
    InvalidHandymanSkillsResponse,
    DeleteHandymanResponse,
    SkillsCatalogReplaceResponse,
    SkillsCatalogPatchResponse,
)
from ..clients.handyman_client import (
    list_handymen,
    create_handyman,
    get_handyman,
    update_handyman_location_and_fetch,
    update_handyman,
    delete_handyman,
    list_handyman_reviews,
    get_skills_catalog,
    get_skills_catalog_flat,
    replace_skills_catalog,
    patch_skills_catalog,
    get_handymen_with_invalid_skills,
)
from ..clients.auth_client import get_auth_user_by_email
from ..security import get_current_user
from ..rbac import require_role
from ..helpers import (
    _user_email,
    _has_role,
    _auth_user_has_any_role,
)

router = APIRouter()


@router.get("/handymen", response_model=List[HandymanResponse], tags=["Handymen"])
async def list_handymen_endpoint(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_role(user, ["user", "handyman", "admin"])
    return await list_handymen(request_id=request.state.request_id, user_payload=user, limit=limit, offset=offset)


@router.post("/handymen", response_model=HandymanResponse, tags=["Handymen"])
async def create_handyman_endpoint(data: CreateHandyman, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])

    try:
        auth_user = await get_auth_user_by_email(data.email, request_id=request.state.request_id, user_payload=user)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=422, detail="Auth user must exist before creating handyman profile")
        raise

    if not _auth_user_has_any_role(auth_user, ["handyman", "admin"]):
        raise HTTPException(status_code=422, detail="Auth user must have role handyman or admin")

    return await create_handyman(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.get("/handymen/{email}", response_model=HandymanResponse, tags=["Handymen"])
async def get_handyman_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await get_handyman(email, request_id=request.state.request_id, user_payload=user)


@router.put("/handymen/{email}/location", response_model=HandymanResponse, tags=["Handymen"])
async def update_handyman_location_endpoint(email: str, data: UpdateHandymanLocation, request: Request, user=Depends(get_current_user)):
    if not _has_role(user, "admin") and _user_email(user) != email:
        raise HTTPException(status_code=403, detail="Cannot update another handyman's location")
    require_role(user, ["handyman", "admin"])
    return await update_handyman_location_and_fetch(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.put("/handymen/{email}", response_model=HandymanResponse, tags=["Handymen"])
async def admin_update_handyman_endpoint(email: str, data: UpdateHandyman, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await update_handyman(email, data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.delete("/handymen/{email}", response_model=DeleteHandymanResponse, tags=["Handymen"])
async def admin_delete_handyman_endpoint(email: str, request: Request, user=Depends(get_current_user)):
    require_role(user, ["admin"])
    return await delete_handyman(email, request_id=request.state.request_id, user_payload=user)


@router.get("/me/handyman", response_model=HandymanResponse, tags=["Handymen"])
async def get_me_handyman(request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await get_handyman(_user_email(user), request_id=request.state.request_id, user_payload=user)


@router.put("/me/handyman", response_model=HandymanResponse, tags=["Handymen"])
async def update_me_handyman(data: UpdateHandyman, request: Request, user=Depends(get_current_user)):
    require_role(user, ["handyman", "admin"])
    return await update_handyman(_user_email(user), data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.get("/handymen/{email}/reviews", response_model=List[HandymanReviewResponse], tags=["Handymen"])
async def list_handyman_reviews_endpoint(
    email: str,
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    require_role(user, ["user", "handyman", "admin"])
    return await list_handyman_reviews(
        email,
        request_id=request.state.request_id,
        user_payload=user,
        limit=limit,
        offset=offset,
    )


@router.get("/skills-catalog", response_model=dict[str, List[str]], tags=["Handymen"])
async def get_skills_catalog_endpoint(
    request: Request,
    active_only: bool = Query(True),
):
    return await get_skills_catalog(
        request_id=request.state.request_id,
        user_payload=None,
        active_only=active_only,
    )


@router.get("/skills-catalog/flat", response_model=SkillCatalogFlatResponse, tags=["Handymen"])
async def get_skills_catalog_flat_endpoint(
    request: Request,
    active_only: bool = Query(True),
):
    return await get_skills_catalog_flat(
        request_id=request.state.request_id,
        user_payload=None,
        active_only=active_only,
    )


@router.put("/admin/skills-catalog", response_model=SkillsCatalogReplaceResponse, tags=["Handymen"])
async def replace_skills_catalog_endpoint(
    data: SkillCatalogReplaceRequest,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await replace_skills_catalog(
        data.model_dump(),
        request_id=request.state.request_id,
        user_payload=user,
    )


@router.patch("/admin/skills-catalog", response_model=SkillsCatalogPatchResponse, tags=["Handymen"])
async def patch_skills_catalog_endpoint(
    data: SkillCatalogPatchRequest,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await patch_skills_catalog(
        data.model_dump(),
        request_id=request.state.request_id,
        user_payload=user,
    )


@router.get("/admin/handymen/invalid-skills", response_model=InvalidHandymanSkillsResponse, tags=["Handymen"])
async def invalid_handymen_skills_endpoint(
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await get_handymen_with_invalid_skills(
        request_id=request.state.request_id,
        user_payload=user,
    )

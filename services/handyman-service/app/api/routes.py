from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.commands.handyman_command_service import HandymanCommandService
from ..application.commands.skill_command_service import SkillCommandService
from ..application.queries.handyman_query_service import HandymanQueryService
from ..application.queries.skill_query_service import SkillQueryService
from ..domain.schemas import (
    CreateHandyman, HandymanResponse, UpdateHandyman, UpdateLocation,
    CreateHandymanReview, HandymanReviewResponse, InvalidHandymanSkillsResponse,
    DeleteHandymanResponse, SkillCatalogReplaceRequest, SkillsCatalogReplaceResponse,
    SkillCatalogFlatResponse, SkillCatalogPatchRequest, SkillsCatalogPatchResponse
)
from ..infrastructure.db import SessionLocal
from shared.core.db.session import make_get_db

router = APIRouter()
get_db = make_get_db(SessionLocal)

@router.get("/handymen", response_model=list[HandymanResponse])
async def list_handymen(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    return await HandymanQueryService(db).list_handymen(limit=limit, offset=offset)

@router.get("/handymen/{email}", response_model=HandymanResponse)
async def get_handyman(email: str, db: AsyncSession = Depends(get_db)):
    return await HandymanQueryService(db).get_handyman(email=email)

@router.get("/handymen/{email}/reviews", response_model=list[HandymanReviewResponse])
async def list_handyman_reviews(
    email: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    return await HandymanQueryService(db).list_handyman_reviews(email=email, limit=limit, offset=offset)

@router.get("/admin/handymen/invalid-skills", response_model=InvalidHandymanSkillsResponse)
async def get_invalid_handyman_skills(db: AsyncSession = Depends(get_db)):
    return await HandymanQueryService(db).get_handymen_with_invalid_skills()

@router.get("/skills-catalog", response_model=dict[str, list[str]])
async def get_skills_catalog(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db)
):
    return await SkillQueryService(db).get_skills_catalog(active_only=active_only)

@router.get("/skills-catalog/flat", response_model=SkillCatalogFlatResponse)
async def get_skills_catalog_flat(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db)
):
    return await SkillQueryService(db).get_skills_catalog_flat(active_only=active_only)

@router.post("/handymen", response_model=HandymanResponse)
async def create_handyman(data: CreateHandyman, db: AsyncSession = Depends(get_db)):
    return await HandymanCommandService(db).create_handyman(data)

@router.put("/handymen/{email}/location", response_model=HandymanResponse)
async def update_location(email: str, data: UpdateLocation, db: AsyncSession = Depends(get_db)):
    return await HandymanCommandService(db).update_location(email=email, data=data)

@router.put("/handymen/{email}", response_model=HandymanResponse)
async def update_handyman(email: str, data: UpdateHandyman, db: AsyncSession = Depends(get_db)):
    return await HandymanCommandService(db).update_handyman(email=email, data=data)

@router.delete("/handymen/{email}", response_model=DeleteHandymanResponse)
async def delete_handyman(email: str, db: AsyncSession = Depends(get_db)):
    return await HandymanCommandService(db).delete_handyman(email=email)

@router.post("/handymen/reviews", response_model=HandymanReviewResponse)
async def create_handyman_review(data: CreateHandymanReview, db: AsyncSession = Depends(get_db)):
    return await HandymanCommandService(db).create_handyman_review(data)

@router.put("/admin/skills-catalog", response_model=SkillsCatalogReplaceResponse)
async def replace_skills_catalog(data: SkillCatalogReplaceRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await SkillCommandService(db).replace_catalog(data.catalog)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.patch("/admin/skills-catalog", response_model=SkillsCatalogPatchResponse)
async def patch_skills_catalog_endpoint(data: SkillCatalogPatchRequest, db: AsyncSession = Depends(get_db)):
    return await SkillCommandService(db).patch_catalog(data.model_dump())
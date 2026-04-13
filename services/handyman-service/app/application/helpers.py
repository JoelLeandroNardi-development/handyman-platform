from typing import Iterable

from sqlalchemy import select, func

from ..domain.models import Handyman, HandymanReview, SkillCatalogItem

async def refresh_handyman_rating(db, handyman_email: str) -> None:
    res = await db.execute(
        select(
            func.count(HandymanReview.id),
            func.avg(HandymanReview.rating),
        ).where(HandymanReview.handyman_email == handyman_email)
    )
    count_value, avg_value = res.one()

    handyman_res = await db.execute(select(Handyman).where(Handyman.email == handyman_email))
    handyman = handyman_res.scalar_one_or_none()
    if handyman is None:
        return

    handyman.rating_count = int(count_value or 0)
    handyman.avg_rating = round(float(avg_value or 0), 2)

def label_from_key(key: str) -> str:
    return (key or "").replace("_", " ").strip().title()

def normalize_skill_key(value: str) -> str:
    return (value or "").strip().lower()

def normalize_catalog(payload: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}

    for raw_category, raw_skills in (payload or {}).items():
        category_key = normalize_skill_key(raw_category)
        if not category_key:
            continue

        seen: set[str] = set()
        clean_skills: list[str] = []

        for raw_skill in raw_skills or []:
            skill_key = normalize_skill_key(raw_skill)
            if not skill_key or skill_key in seen:
                continue
            seen.add(skill_key)
            clean_skills.append(skill_key)

        if clean_skills:
            normalized[category_key] = clean_skills

    return normalized

def validate_catalog_shape(payload: dict[str, list[str]]) -> None:
    normalized = normalize_catalog(payload)
    if not normalized:
        raise ValueError("Catalog must contain at least one category with at least one skill")

    seen_skills: set[str] = set()
    duplicates: list[str] = []

    for skills in normalized.values():
        for skill in skills:
            if skill in seen_skills:
                duplicates.append(skill)
            seen_skills.add(skill)

    if duplicates:
        raise ValueError(f"Duplicate skill keys across categories are not allowed: {sorted(set(duplicates))}")

def normalize_skills_input(skills: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    for raw in skills or []:
        skill = normalize_skill_key(raw)
        if not skill or skill in seen:
            continue
        seen.add(skill)
        out.append(skill)

    return out

async def find_invalid_skills(db, skills: Iterable[str] | None) -> list[str]:
    normalized = normalize_skills_input(skills)
    allowed = await get_allowed_skill_keys(db,active_only=True)
    invalid = [s for s in normalized if s not in allowed]
    return sorted(invalid)

async def get_allowed_skill_keys(db, *, active_only: bool = True) -> set[str]:
    stmt = select(SkillCatalogItem.skill_key)
    if active_only:
        stmt = stmt.where(SkillCatalogItem.is_active.is_(True))

    res = await db.execute(stmt)
    return {str(x) for x in res.scalars().all()}
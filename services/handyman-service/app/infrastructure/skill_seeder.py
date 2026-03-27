from sqlalchemy import select

from ..application.helpers import normalize_catalog, _label_from_key
from ..domain.models import SkillsCategory, SkillCatalogItem
from ..domain.skills_catalog import DEFAULT_SKILLS_CATALOG
from ..infrastructure.db import SessionLocal

async def seed_default_catalog_if_empty() -> dict:
    async with SessionLocal() as db:
        res = await db.execute(select(SkillCatalogItem.id).limit(1))
        exists = res.scalar_one_or_none()

        if exists is not None:
            count_res = await db.execute(select(SkillCatalogItem.id))
            count = len(list(count_res.scalars().all()))
            return {"seeded": False, "reason": "already_present", "count": count}

        payload = normalize_catalog(DEFAULT_SKILLS_CATALOG)

        cat_order = 0
        skill_total = 0

        for category_key, skills in payload.items():
            db.add(
                SkillsCategory(
                    key=category_key,
                    label=_label_from_key(category_key),
                    is_active=True,
                    sort_order=cat_order,
                )
            )

            for skill_order, skill_key in enumerate(skills):
                db.add(
                    SkillCatalogItem(
                        category_key=category_key,
                        skill_key=skill_key,
                        category_label=_label_from_key(category_key),
                        skill_label=_label_from_key(skill_key),
                        is_active=True,
                        sort_order=skill_order,
                    )
                )
                skill_total += 1

            cat_order += 1

        await db.commit()
        return {"seeded": True, "reason": "bootstrapped", "count": skill_total}
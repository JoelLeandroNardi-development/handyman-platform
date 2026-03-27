from collections import defaultdict

from fastapi import Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.models import SkillsCategory, SkillCatalogItem
from ...domain.schemas import SkillCatalogFlatResponse

class SkillQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_skills_catalog(
        self,
        active_only: bool = Query(True),
    ) -> dict[str, list[str]]:
        cats_stmt = select(SkillsCategory).order_by(
            SkillsCategory.sort_order.asc(),
            SkillsCategory.key.asc(),
        )
        skills_stmt = select(SkillCatalogItem).order_by(
            SkillCatalogItem.category_key.asc(),
            SkillCatalogItem.sort_order.asc(),
            SkillCatalogItem.skill_key.asc(),
        )

        if active_only:
            cats_stmt = cats_stmt.where(SkillsCategory.is_active.is_(True))
            skills_stmt = skills_stmt.where(SkillCatalogItem.is_active.is_(True))

        cats_res = await self.db.execute(cats_stmt)
        skills_res = await self.db.execute(skills_stmt)

        cats = list(cats_res.scalars().all())
        items = list(skills_res.scalars().all())

        grouped: dict[str, list[str]] = {}
        active_categories = {cat.key for cat in cats}

        for category_key in active_categories:
            grouped[category_key] = []

        for item in items:
            if item.category_key in active_categories:
                grouped.setdefault(item.category_key, []).append(item.skill_key)

        return grouped

    async def get_skills_catalog_flat(
        self,
        active_only: bool = Query(True),
    ) -> SkillCatalogFlatResponse:
        cats_stmt = select(SkillsCategory).order_by(
            SkillsCategory.sort_order.asc(),
            SkillsCategory.key.asc(),
        )
        skills_stmt = select(SkillCatalogItem).order_by(
            SkillCatalogItem.category_key.asc(),
            SkillCatalogItem.sort_order.asc(),
            SkillCatalogItem.skill_key.asc(),
        )

        if active_only:
            cats_stmt = cats_stmt.where(SkillsCategory.is_active.is_(True))
            skills_stmt = skills_stmt.where(SkillCatalogItem.is_active.is_(True))

        cats_res = await self.db.execute(cats_stmt)
        skills_res = await self.db.execute(skills_stmt)

        cats = list(cats_res.scalars().all())
        items = list(skills_res.scalars().all())

        by_category: dict[str, list[dict]] = defaultdict(list)
        allowed_skill_keys: list[str] = []

        for item in items:
            by_category[item.category_key].append(
                {
                    "key": item.skill_key,
                    "label": item.skill_label,
                    "active": item.is_active,
                    "sort_order": item.sort_order,
                }
            )
            if item.is_active:
                allowed_skill_keys.append(item.skill_key)

        categories: list[dict] = []
        for cat in cats:
            categories.append(
                {
                    "key": cat.key,
                    "label": cat.label,
                    "active": cat.is_active,
                    "sort_order": cat.sort_order,
                    "skills": by_category.get(cat.key, []),
                }
            )

        return {
            "categories": categories,
            "allowed_skill_keys": sorted(set(allowed_skill_keys)),
        }

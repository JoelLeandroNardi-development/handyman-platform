from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.skill_query_service import SkillQueryService
from app.application.helpers import normalize_catalog, normalize_skills_input, _label_from_key, validate_catalog_shape
from app.domain.models import SkillCatalogItem, SkillsCategory
from app.domain.schemas import SkillsCatalogPatchResponse, SkillsCatalogReplaceResponse

class SkillCommandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def patch_catalog(self,data: dict) -> SkillsCatalogPatchResponse:
        upserts = normalize_catalog(data.get("upserts") or {})
        activate_skills = normalize_skills_input(data.get("activate_skills") or [])
        deactivate_skills = normalize_skills_input(data.get("deactivate_skills") or [])
        activate_categories = normalize_skills_input(data.get("activate_categories") or [])
        deactivate_categories = normalize_skills_input(data.get("deactivate_categories") or [])

        added_categories = 0
        added_skills = 0

        for category_key, skills in upserts.items():
            cat_res = await self.db.execute(
                select(SkillsCategory).where(SkillsCategory.key == category_key)
            )
            category = cat_res.scalar_one_or_none()

            if category is None:
                existing_count_res = await self.db.execute(select(SkillsCategory.id))
                next_sort = len(list(existing_count_res.scalars().all()))
                category = SkillsCategory(
                    key=category_key,
                    label=_label_from_key(category_key),
                    is_active=True,
                    sort_order=next_sort,
                )
                self.db.add(category)
                added_categories += 1
            else:
                category.is_active = True
                if not category.label:
                    category.label = _label_from_key(category_key)

            for skill_key in skills:
                item_res = await self.db.execute(
                    select(SkillCatalogItem).where(SkillCatalogItem.skill_key == skill_key)
                )
                item = item_res.scalar_one_or_none()

                if item is None:
                    same_cat_count_res = await self.db.execute(
                        select(SkillCatalogItem.id).where(SkillCatalogItem.category_key == category_key)
                    )
                    next_sort = len(list(same_cat_count_res.scalars().all()))
                    self.db.add(
                        SkillCatalogItem(
                            category_key=category_key,
                            skill_key=skill_key,
                            category_label=_label_from_key(category_key),
                            skill_label=_label_from_key(skill_key),
                            is_active=True,
                            sort_order=next_sort,
                        )
                    )
                    added_skills += 1
                else:
                    item.category_key = category_key
                    item.category_label = _label_from_key(category_key)
                    item.skill_label = _label_from_key(skill_key)
                    item.is_active = True

        if activate_categories:
            await self.db.execute(
                update(SkillsCategory)
                .where(SkillsCategory.key.in_(activate_categories))
                .values(is_active=True)
            )
            await self.db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.category_key.in_(activate_categories))
                .values(is_active=True)
            )

        if deactivate_categories:
            await self.db.execute(
                update(SkillsCategory)
                .where(SkillsCategory.key.in_(deactivate_categories))
                .values(is_active=False)
            )
            await self.db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.category_key.in_(deactivate_categories))
                .values(is_active=False)
            )

        if activate_skills:
            await self.db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.skill_key.in_(activate_skills))
                .values(is_active=True)
            )

        if deactivate_skills:
            await self.db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.skill_key.in_(deactivate_skills))
                .values(is_active=False)
            )

        await self.db.commit()

        flat = await SkillQueryService(self.db).get_skills_catalog_flat(active_only=False)
        return {
            "message": "skills catalog patched",
            "added_categories": added_categories,
            "added_skills": added_skills,
            "catalog": flat,
        }

    async def replace_catalog(self, data: dict[str, list[str]]) -> SkillsCatalogReplaceResponse:
        validate_catalog_shape(data)
        normalized = normalize_catalog(data)

        await self.db.execute(delete(SkillCatalogItem))
        await self.db.execute(delete(SkillsCategory))

        cat_order = 0
        skill_total = 0

        for category_key, skills in normalized.items():
            self.db.add(
                SkillsCategory(
                    key=category_key,
                    label=_label_from_key(category_key),
                    is_active=True,
                    sort_order=cat_order,
                )
            )

            for skill_order, skill_key in enumerate(skills):
                self.db.add(
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

        await self.db.commit()

        return {
            "message": "skills catalog replaced",
            "categories": len(normalized),
            "skills": skill_total,
        }
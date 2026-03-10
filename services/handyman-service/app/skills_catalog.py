from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy import delete, select, update

from .db import SessionLocal
from .models import SkillsCategory, SkillCatalogItem, Handyman


DEFAULT_SKILLS_CATALOG: dict[str, list[str]] = {
    "construction_structural": [
        "carpentry",
        "furniture_assembly",
        "cabinet_installation",
        "drywall_installation",
        "drywall_repair",
        "framing",
        "deck_building_repair",
        "fence_installation_repair",
        "stair_repair",
        "door_installation",
        "window_installation",
    ],
    "finishing_interior": [
        "interior_painting",
        "exterior_painting",
        "wallpaper_installation_removal",
        "tile_installation",
        "tile_repair",
        "caulking_sealing",
        "trim_molding_installation",
        "flooring_installation",
        "grout_repair",
        "plaster_repair",
    ],
    "plumbing": [
        "faucet_installation_repair",
        "sink_installation",
        "toilet_installation_repair",
        "showerhead_installation",
        "leak_detection_repair",
        "pipe_replacement",
        "drain_unclogging",
        "garbage_disposal_installation",
        "dishwasher_hookup",
    ],
    "electrical_basic": [
        "light_fixture_installation",
        "ceiling_fan_installation",
        "switch_outlet_replacement",
        "smart_switch_installation",
        "doorbell_installation",
        "led_lighting_upgrades",
        "basic_electrical_troubleshooting",
    ],
    "outdoor_exterior": [
        "gutter_cleaning_repair",
        "pressure_washing",
        "shed_assembly",
        "patio_installation",
        "fence_painting_staining",
        "weatherproofing",
        "minor_roof_repairs",
        "landscaping_maintenance",
        "irrigation_repair",
    ],
    "furniture_fixtures": [
        "furniture_repair",
        "flatpack_assembly",
        "shelf_installation",
        "closet_system_installation",
        "tv_wall_mounting",
        "curtain_rod_installation",
        "mirror_mounting",
        "picture_hanging",
    ],
    "maintenance_repair": [
        "general_home_maintenance",
        "lock_replacement_repair",
        "door_alignment_hinge_repair",
        "window_screen_repair",
        "weatherstripping_installation",
        "appliance_installation",
        "small_appliance_repair",
    ],
    "modern_handyman": [
        "smart_home_device_installation",
        "security_camera_installation",
        "wifi_doorbell_installation",
        "ev_charger_installation",
        "solar_light_installation",
    ],
}


def _label_from_key(key: str) -> str:
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


async def get_grouped_catalog(*, active_only: bool = True) -> dict[str, list[str]]:
    async with SessionLocal() as db:
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

        cats_res = await db.execute(cats_stmt)
        skills_res = await db.execute(skills_stmt)

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


async def get_catalog_flat(*, active_only: bool = True) -> dict:
    async with SessionLocal() as db:
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

        cats_res = await db.execute(cats_stmt)
        skills_res = await db.execute(skills_stmt)

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


async def get_allowed_skill_keys(*, active_only: bool = True) -> set[str]:
    async with SessionLocal() as db:
        stmt = select(SkillCatalogItem.skill_key)
        if active_only:
            stmt = stmt.where(SkillCatalogItem.is_active.is_(True))

        res = await db.execute(stmt)
        return {str(x) for x in res.scalars().all()}


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


async def find_invalid_skills(skills: Iterable[str] | None) -> list[str]:
    normalized = normalize_skills_input(skills)
    allowed = await get_allowed_skill_keys(active_only=True)
    invalid = [s for s in normalized if s not in allowed]
    return sorted(invalid)


async def replace_catalog(payload: dict[str, list[str]]) -> dict:
    validate_catalog_shape(payload)
    normalized = normalize_catalog(payload)

    async with SessionLocal() as db:
        await db.execute(delete(SkillCatalogItem))
        await db.execute(delete(SkillsCategory))

        cat_order = 0
        skill_total = 0

        for category_key, skills in normalized.items():
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

    return {
        "message": "skills catalog replaced",
        "categories": len(normalized),
        "skills": skill_total,
    }


async def patch_catalog(payload: dict) -> dict:
    upserts = normalize_catalog(payload.get("upserts") or {})
    activate_skills = normalize_skills_input(payload.get("activate_skills") or [])
    deactivate_skills = normalize_skills_input(payload.get("deactivate_skills") or [])
    activate_categories = normalize_skills_input(payload.get("activate_categories") or [])
    deactivate_categories = normalize_skills_input(payload.get("deactivate_categories") or [])

    async with SessionLocal() as db:
        added_categories = 0
        added_skills = 0

        for category_key, skills in upserts.items():
            cat_res = await db.execute(
                select(SkillsCategory).where(SkillsCategory.key == category_key)
            )
            category = cat_res.scalar_one_or_none()

            if category is None:
                existing_count_res = await db.execute(select(SkillsCategory.id))
                next_sort = len(list(existing_count_res.scalars().all()))
                category = SkillsCategory(
                    key=category_key,
                    label=_label_from_key(category_key),
                    is_active=True,
                    sort_order=next_sort,
                )
                db.add(category)
                added_categories += 1
            else:
                category.is_active = True
                if not category.label:
                    category.label = _label_from_key(category_key)

            for skill_key in skills:
                item_res = await db.execute(
                    select(SkillCatalogItem).where(SkillCatalogItem.skill_key == skill_key)
                )
                item = item_res.scalar_one_or_none()

                if item is None:
                    same_cat_count_res = await db.execute(
                        select(SkillCatalogItem.id).where(SkillCatalogItem.category_key == category_key)
                    )
                    next_sort = len(list(same_cat_count_res.scalars().all()))
                    db.add(
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
            await db.execute(
                update(SkillsCategory)
                .where(SkillsCategory.key.in_(activate_categories))
                .values(is_active=True)
            )
            await db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.category_key.in_(activate_categories))
                .values(is_active=True)
            )

        if deactivate_categories:
            await db.execute(
                update(SkillsCategory)
                .where(SkillsCategory.key.in_(deactivate_categories))
                .values(is_active=False)
            )
            await db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.category_key.in_(deactivate_categories))
                .values(is_active=False)
            )

        if activate_skills:
            await db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.skill_key.in_(activate_skills))
                .values(is_active=True)
            )

        if deactivate_skills:
            await db.execute(
                update(SkillCatalogItem)
                .where(SkillCatalogItem.skill_key.in_(deactivate_skills))
                .values(is_active=False)
            )

        await db.commit()

    flat = await get_catalog_flat(active_only=False)
    return {
        "message": "skills catalog patched",
        "added_categories": added_categories,
        "added_skills": added_skills,
        "catalog": flat,
    }


async def get_handymen_with_invalid_skills() -> dict:
    allowed = await get_allowed_skill_keys(active_only=True)

    async with SessionLocal() as db:
        res = await db.execute(select(Handyman).order_by(Handyman.email.asc()))
        rows = list(res.scalars().all())

    items: list[dict] = []
    for handyman in rows:
        current_skills = normalize_skills_input(list(handyman.skills or []))
        invalid_skills = sorted([skill for skill in current_skills if skill not in allowed])

        if not invalid_skills:
            continue

        valid_skills = [skill for skill in current_skills if skill in allowed]
        items.append(
            {
                "email": handyman.email,
                "current_skills": current_skills,
                "invalid_skills": invalid_skills,
                "valid_skills": valid_skills,
            }
        )

    return {
        "items": items,
        "count": len(items),
    }
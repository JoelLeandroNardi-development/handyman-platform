from __future__ import annotations

import httpx
import json

from ..application.normalizers import normalize_handyman
from ..domain.constants import ProjectionSource, SeedReason
from ..infrastructure.availability_projection import clean_slots, get_availability_slots, delete_availability_projection, availability_projection_count
from ..infrastructure.clients import fetch_handymen_http, fetch_completed_jobs_counts_batch, fetch_availability_http
from ..infrastructure.projections import get_handyman_projection, handyman_projection_count, list_projected_handymen_by_skill, redis_client
from ..infrastructure.redis_keys import (
    PROJ_HANDYMAN_KEY,
    PROJ_HANDYMEN_INDEX,
    PROJ_HANDYMEN_SKILL_INDEX,
    PROJ_AVAIL_KEY,
    PROJ_AVAIL_INDEX
)
from shared.core.utils.datetime import utc_now_iso
from shared.core.utils.normalize import norm

async def upsert_handyman_projection(doc: dict) -> None:
    normalized = normalize_handyman(doc)
    email = normalized.get("email")
    if not email:
        return

    old = await get_handyman_projection(email)
    old_skills = set((old or {}).get("skills") or [])
    new_skills = set(normalized.get("skills") or [])

    pipe = redis_client.pipeline()
    pipe.set(PROJ_HANDYMAN_KEY.format(email=email), json.dumps(normalized))
    pipe.sadd(PROJ_HANDYMEN_INDEX, email)

    for s in (old_skills - new_skills):
        pipe.srem(PROJ_HANDYMEN_SKILL_INDEX.format(skill=s), email)

    for s in new_skills:
        pipe.sadd(PROJ_HANDYMEN_SKILL_INDEX.format(skill=s), email)

    await pipe.execute()

async def delete_handyman_projection(email: str) -> dict | None:
    if not email:
        return None

    old = await get_handyman_projection(email)
    old_skills = set((old or {}).get("skills") or [])

    pipe = redis_client.pipeline()
    pipe.delete(PROJ_HANDYMAN_KEY.format(email=email))
    pipe.srem(PROJ_HANDYMEN_INDEX, email)
    for s in old_skills:
        pipe.srem(PROJ_HANDYMEN_SKILL_INDEX.format(skill=s), email)
    await pipe.execute()
    return old

async def upsert_availability_projection(*, email: str, slots: list[dict]) -> None:
    if not email:
        return

    cleaned_slots = clean_slots(slots)

    if not cleaned_slots:
        await delete_availability_projection(email)
        return

    payload = {"email": email, "slots": cleaned_slots, "updated_at": utc_now_iso()}

    pipe = redis_client.pipeline()
    pipe.set(PROJ_AVAIL_KEY.format(email=email), json.dumps(payload))
    pipe.sadd(PROJ_AVAIL_INDEX, email)
    await pipe.execute()

async def hydrate_completed_jobs_counts(handymen: list[dict]) -> list[dict]:
    if not handymen:
        return handymen

    emails = [str(h.get("email")).strip() for h in handymen if isinstance(h, dict) and h.get("email")]
    counts = await fetch_completed_jobs_counts_batch(emails)

    for h in handymen:
        if not isinstance(h, dict):
            continue
        email = h.get("email")
        if isinstance(email, str) and email in counts:
            h["completed_jobs_count"] = counts[email]
            continue
        try:
            h["completed_jobs_count"] = int(h.get("completed_jobs_count") or 0)
        except Exception:
            h["completed_jobs_count"] = 0

    return handymen

async def projections_have_any_availability() -> bool:
    return (await availability_projection_count()) > 0

async def get_effective_availability_slots(email: str) -> tuple[list[dict] | None, str]:
    projected = await get_availability_slots(email)
    if projected is not None:
        return projected, ProjectionSource.PROJECTION

    live = await fetch_availability_http(email)
    if live is None:
        return None, ProjectionSource.MISSING

    await upsert_availability_projection(email=email, slots=live)
    return live, ProjectionSource.LIVE

async def seed_handyman_projection_if_empty() -> dict:
    existing = await handyman_projection_count()
    if existing > 0:
        return {"seeded": False, "reason": SeedReason.ALREADY_PRESENT, "count": existing}

    try:
        handymen = await fetch_handymen_http()
    except Exception as e:
        return {"seeded": False, "reason": f"fetch_failed: {type(e).__name__}: {e}", "count": 0}

    ok = 0
    for h in handymen or []:
        try:
            await upsert_handyman_projection(h)
            ok += 1
        except Exception:
            continue

    return {"seeded": True, "reason": SeedReason.BOOTSTRAPPED, "count": ok}

async def get_live_handymen_for_skill(skill: str) -> list[dict]:
    skill = norm(skill)
    if not skill:
        return []

    all_handymen = await fetch_handymen_http()
    matched: list[dict] = []

    for h in all_handymen:
        skills = [norm(s) for s in (h.get("skills") or [])]
        if skill in skills:
            matched.append(h)
            try:
                await upsert_handyman_projection(h)
            except Exception:
                pass

    return matched

async def get_effective_handymen_for_skill(skill: str) -> tuple[list[dict], str]:
    skill = norm(skill)
    if not skill:
        return [], ProjectionSource.EMPTY_SKILL

    projected = await list_projected_handymen_by_skill(skill)
    if projected:
        return projected, ProjectionSource.PROJECTION

    live = await get_live_handymen_for_skill(skill)
    return live, ProjectionSource.LIVE
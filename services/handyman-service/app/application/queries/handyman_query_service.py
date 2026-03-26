from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.helpers import normalize_skills_input, get_allowed_skill_keys
from app.application.mappers import _review_to_response, _to_response
from app.domain.models import Handyman, HandymanReview
from app.domain.schemas import HandymanResponse, InvalidHandymanSkillsResponse, HandymanReviewResponse
from shared.shared.crud_helpers import fetch_or_404

class HandymanQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_handymen(self, limit: int, offset: int) -> list[HandymanResponse]:
        res = await self.db.execute(
            select(Handyman).order_by(Handyman.id.asc()).limit(limit).offset(offset)
        )
        rows = res.scalars().all()
        return [_to_response(h) for h in rows]

    async def get_handyman(self, email: str) -> HandymanResponse:
        h = await fetch_or_404(self.db, Handyman, filter_column=Handyman.email, filter_value=email, detail="Handyman not found")
        return _to_response(h)
    
    async def get_handymen_with_invalid_skills(self) -> InvalidHandymanSkillsResponse:
        allowed = await get_allowed_skill_keys(self.db, active_only=True)

        res = await self.db.execute(select(Handyman).order_by(Handyman.email.asc()))
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
    
    async def list_handyman_reviews(self, email: str,limit: int, offset: int) -> list[HandymanReviewResponse]:
        handyman = await fetch_or_404(self.db, Handyman, filter_column=Handyman.email, filter_value=email, detail="Handyman not found")

        res = await self.db.execute(
            select(HandymanReview)
            .where(HandymanReview.handyman_email == email)
            .order_by(HandymanReview.created_at.desc(), HandymanReview.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = res.scalars().all()
        return [_review_to_response(r) for r in rows]
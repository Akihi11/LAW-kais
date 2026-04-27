from __future__ import annotations

from pydantic import BaseModel

from app.schemas.domain import ReviewRole


class CreateReviewRequest(BaseModel):
    review_role: ReviewRole

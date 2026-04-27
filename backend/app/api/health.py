from __future__ import annotations

from fastapi import APIRouter

from app.schemas.response import HealthResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(ok=True)

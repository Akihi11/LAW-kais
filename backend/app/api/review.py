from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile

from app.schemas.response import CreateReviewResponse, ReviewResultResponse, ReviewStatusResponse
from app.services.review_service import ReviewService


router = APIRouter(prefix="/reviews", tags=["reviews"])


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


@router.post("", response_model=CreateReviewResponse, status_code=201, deprecated=True)
async def create_review(
    file: Annotated[UploadFile, File(...)],
    review_role: Annotated[str, Form(...)],
    visitor_biz_id: Annotated[str | None, Header(alias="X-Visitor-Biz-ID")] = None,
    review_service: Annotated[ReviewService, Depends(get_review_service)] = None,
) -> CreateReviewResponse:
    print("[backend] raw review_role =", repr(review_role))
    return await review_service.create_review(file=file, review_role=review_role, visitor_biz_id=visitor_biz_id)


@router.get("/{task_id}", response_model=ReviewStatusResponse, deprecated=True)
async def get_review_status(
    task_id: str,
    review_service: Annotated[ReviewService, Depends(get_review_service)] = None,
) -> ReviewStatusResponse:
    return await review_service.get_status(task_id)


@router.get("/{task_id}/result", response_model=ReviewResultResponse, deprecated=True)
async def get_review_result(
    task_id: str,
    review_service: Annotated[ReviewService, Depends(get_review_service)] = None,
) -> ReviewResultResponse:
    return await review_service.get_result(task_id)

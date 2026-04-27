from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import contract_review, health, review
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.providers.mock_provider import MockProvider
from app.providers.tencent_yuanqi_async_provider import TencentYuanqiAsyncProvider
from app.providers.tencent_yuanqi_provider import TencentYuanqiProvider
from app.providers.tencent_yuanqi_sse_provider import TencentYuanqiSseProvider
from app.repositories.task_repository import TaskRepository
from app.schemas.response import ErrorResponse
from app.services.result_mapper import ResultMapper
from app.services.review_service import ReviewService
from app.services.task_service import TaskService
from app.utils.file_storage import FileStorage
from app.utils.logger import get_logger, reset_request_id, set_request_id


logger = get_logger(__name__)


def build_provider(settings: Settings):
    if settings.review_provider == "mock":
        return MockProvider(settings.mock_result_path, fast_complete=settings.mock_fast_complete)
    if settings.review_provider == "tencent_yuanqi_async":
        return TencentYuanqiAsyncProvider(settings)
    if settings.review_provider == "tencent_yuanqi":
        logger.warning("Provider tencent_yuanqi is legacy and should not be used as the main workflow path.")
        return TencentYuanqiProvider(settings)
    if settings.review_provider == "tencent_yuanqi_sse":
        logger.warning("Provider tencent_yuanqi_sse is legacy and should not be used as the main workflow path.")
        return TencentYuanqiSseProvider(settings)
    raise RuntimeError(f"Unsupported REVIEW_PROVIDER: {settings.review_provider}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    file_storage = FileStorage(settings)
    file_storage.ensure_directories()
    provider = build_provider(settings)

    repository = TaskRepository(settings.task_db_path)
    repository.ensure_schema()
    task_service = TaskService(repository)
    review_service = ReviewService(
        provider=provider,
        task_service=task_service,
        file_storage=file_storage,
        result_mapper=ResultMapper(),
        settings=settings,
    )

    app.state.settings = settings
    app.state.file_storage = file_storage
    app.state.task_service = task_service
    app.state.review_service = review_service
    app.state.provider = provider
    logger.info(
        "Application services initialized with provider=%s mock_fast_complete=%s public_file_base_url=%s task_db_path=%s",
        settings.review_provider,
        settings.mock_fast_complete,
        settings.public_file_base_url,
        settings.task_db_path,
    )
    try:
        yield
    finally:
        try:
            await provider.close()
        except Exception as exc:
            logger.exception("Failed to close provider resources: %s", exc)


app = FastAPI(
    title="??????? Backend",
    version="0.1.0",
    lifespan=lifespan,
)

_static_settings = get_settings()
app.mount(
    "/storage/uploads",
    StaticFiles(directory=str(_static_settings.uploads_dir), check_dir=False),
    name="storage-uploads",
)

app.include_router(health.router, prefix="/api")
app.include_router(contract_review.router, prefix="/api")
app.include_router(review.router, prefix="/api")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", uuid4().hex)
    request.state.request_id = request_id
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
    finally:
        reset_request_id(token)

    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("Handled application error: code=%s message=%s", exc.code, exc.message)
    payload = ErrorResponse(code=exc.code, message=exc.message, detail=exc.detail)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    payload = ErrorResponse(
        code="request_validation_error",
        message="Request validation failed.",
        detail={"errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    payload = ErrorResponse(
        code="internal_error",
        message="An unexpected internal error occurred.",
        detail=None,
    )
    return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))

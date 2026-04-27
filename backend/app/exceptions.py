from __future__ import annotations

from typing import Any

from app.schemas.domain import ReviewRole


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
        self.details = detail


class UnsupportedFileTypeError(AppError):
    def __init__(self, filename: str, allowed_extensions: list[str]) -> None:
        super().__init__(
            status_code=400,
            code="invalid_file_type",
            message="Invalid file type.",
            detail={"filename": filename, "allowedExtensions": allowed_extensions},
        )


class FileTooLargeError(AppError):
    def __init__(self, max_size_mb: float) -> None:
        super().__init__(
            status_code=413,
            code="file_too_large",
            message="Uploaded file is too large.",
            detail={"maxSizeMB": max_size_mb},
        )


class InvalidReviewRoleError(AppError):
    def __init__(self, review_role: str) -> None:
        super().__init__(
            status_code=400,
            code="invalid_review_role",
            message="Invalid review role.",
            detail={"reviewRole": review_role, "allowedValues": [role.value for role in ReviewRole]},
        )


class TaskNotFoundError(AppError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            status_code=404,
            code="task_not_found",
            message="Task not found.",
            detail={"taskId": task_id},
        )


class ResultNotReadyError(AppError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            status_code=409,
            code="result_not_ready",
            message="Result is not ready.",
            detail={"taskId": task_id},
        )


class ResultNotFoundError(AppError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            status_code=404,
            code="result_not_found",
            message="Result not found.",
            detail={"taskId": task_id},
        )


class TaskFailedError(AppError):
    def __init__(self, task_id: str, error_message: str | None = None) -> None:
        super().__init__(
            status_code=409,
            code="task_failed",
            message="Task failed.",
            detail={"taskId": task_id, "errorMessage": error_message},
        )


class ProviderExecutionError(AppError):
    def __init__(
        self,
        provider_name: str,
        message: str,
        detail: Any = None,
        *,
        code: str = "provider_error",
        status_code: int = 502,
    ) -> None:
        super().__init__(
            status_code=status_code,
            code=code,
            message=message,
            detail={"provider": provider_name, "detail": detail},
        )


class ProviderNotConfiguredError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Provider is not configured.",
            detail,
            code="provider_not_configured",
            status_code=500,
        )


class ProviderNotImplementedError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Provider is not implemented.",
            detail,
            code="provider_not_implemented",
            status_code=501,
        )


class ProviderInvalidUrlError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Tencent Yuanqi request URL is invalid.",
            detail,
            code="provider_invalid_url",
            status_code=502,
        )


class ProviderAuthFailedError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Tencent Yuanqi authentication failed.",
            detail,
            code="provider_auth_failed",
            status_code=502,
        )


class ProviderRequestFailedError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Tencent Yuanqi request failed.",
            detail,
            code="provider_request_failed",
            status_code=502,
        )


class ProviderResponseInvalidError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Tencent Yuanqi response is invalid.",
            detail,
            code="provider_response_invalid",
            status_code=502,
        )


class DocumentParseFailedError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Document text extraction failed.",
            detail,
            code="document_parse_failed",
            status_code=400,
        )


class DocumentEmptyError(ProviderExecutionError):
    def __init__(self, provider_name: str, detail: Any = None) -> None:
        super().__init__(
            provider_name,
            "Document contains no extractable text.",
            detail,
            code="document_empty",
            status_code=400,
        )


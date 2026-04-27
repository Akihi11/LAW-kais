from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from app.config import Settings
from app.exceptions import (
    DocumentEmptyError,
    DocumentParseFailedError,
    ProviderAuthFailedError,
    ProviderInvalidUrlError,
    ProviderNotConfiguredError,
    ProviderRequestFailedError,
    ProviderResponseInvalidError,
)
from app.providers.base import BaseProvider
from app.schemas.domain import (
    ProviderCreateReviewRequest,
    ProviderName,
    ProviderResultPayload,
    ProviderStatus,
    ProviderTaskHandle,
    StageCode,
    TaskRecord,
    TaskStatus,
    get_stage_label,
)
from app.utils.document_parser import DocumentParser
from app.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class YuanqiExecutionResult:
    raw_response: dict[str, Any]
    normalized_payload: dict[str, Any]
    usage: dict[str, Any] | None
    steps: list[dict[str, Any]] | None
    response_text_length: int
    parsed_successfully: bool


@dataclass
class YuanqiJob:
    request: ProviderCreateReviewRequest
    task_id: str
    provider_task_id: str
    api_url: str
    assistant_id: str
    review_role: str
    file_name: str
    file_url: str
    document_text: str | None = None
    status: TaskStatus = TaskStatus.QUEUED
    stage: StageCode = StageCode.UPLOADING
    progress: int = 8
    raw_response: dict[str, Any] | None = None
    normalized_response: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    steps: list[dict[str, Any]] | None = None
    error: Exception | None = None
    runner: asyncio.Task[None] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    used_variable_mode: bool = False
    used_text_fallback: bool = False
    upstream_status_code: int | None = None
    response_text_length: int = 0
    parsed_successfully: bool = False


class TencentYuanqiProvider(BaseProvider):
    """Deprecated as a node-status source. Legacy chat/completions provider kept for compatibility."""
    name = ProviderName.TENCENT_YUANQI

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._document_parser = DocumentParser(self.name)
        self._jobs: dict[str, YuanqiJob] = {}
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=settings.yuanqi_request_timeout_seconds)

    async def close(self) -> None:
        async with self._lock:
            runners = [job.runner for job in self._jobs.values() if job.runner and not job.runner.done()]

        for runner in runners:
            runner.cancel()

        if runners:
            await asyncio.gather(*runners, return_exceptions=True)

        if not self._client.is_closed:
            await self._client.aclose()

    async def create_review(self, request: ProviderCreateReviewRequest) -> ProviderTaskHandle:
        self._ensure_minimum_configured(request)

        provider_task_id = f"yuanqi_{request.task_id}_{uuid4().hex[:8]}"
        preview = {
            "provider": self.name.value,
            "apiUrl": self._settings.yuanqi_api_url,
            "assistantId": self._settings.yuanqi_app_id,
            "reviewRole": request.review_role.value,
            "usesVariableMode": True,
            "variablesFieldName": self._settings.yuanqi_variables_field_name,
            "variableKeys": self._variable_keys,
            "usesTextFallback": False,
            "fileName": request.file_info.original_filename,
        }

        logger.info(
            "Prepared Tencent Yuanqi task taskId=%s provider=%s api_url=%s assistant_id=%s review_role=%s uses_variable_mode=%s variables_field_name=%s variable_keys=%s uses_text_fallback=%s",
            request.task_id,
            self.name.value,
            self._settings.yuanqi_api_url,
            self._settings.yuanqi_app_id,
            request.review_role.value,
            True,
            self._settings.yuanqi_variables_field_name,
            self._variable_keys,
            False,
        )

        job = YuanqiJob(
            request=request,
            task_id=request.task_id,
            provider_task_id=provider_task_id,
            api_url=self._settings.yuanqi_api_url,
            assistant_id=self._settings.yuanqi_app_id,
            review_role=request.review_role.value,
            file_name=request.file_info.original_filename,
            file_url=request.public_file_url or "",
        )

        async with self._lock:
            self._jobs[provider_task_id] = job
            job.runner = asyncio.create_task(self._execute_job(job))

        return ProviderTaskHandle(
            provider_task_id=provider_task_id,
            raw_request=preview,
            raw_response={"accepted": True, "provider": self.name.value},
        )

    async def get_status(self, task: TaskRecord) -> ProviderStatus:
        job = await self._get_job(task.provider_task_id)
        if job.error is not None:
            raise job.error

        return ProviderStatus(
            status=job.status,
            current_stage=job.stage,
            current_stage_label=get_stage_label(job.stage),
            progress=job.progress,
        )

    async def get_result(self, task: TaskRecord) -> ProviderResultPayload:
        job = await self._get_job(task.provider_task_id)
        if job.error is not None:
            raise job.error
        if job.status != TaskStatus.SUCCEEDED:
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "taskId": task.task_id,
                    "providerTaskId": task.provider_task_id,
                    "status": job.status.value,
                },
            )

        raw_payload = dict(job.normalized_response or {})
        raw_payload["_source_document_text"] = job.document_text or ""
        raw_payload["_source_file_name"] = job.file_name
        raw_payload["_source_file_url"] = job.file_url

        return ProviderResultPayload(raw=raw_payload, usage=job.usage, steps=job.steps)

    async def _get_job(self, provider_task_id: str) -> YuanqiJob:
        async with self._lock:
            job = self._jobs.get(provider_task_id)

        if job is None:
            raise ProviderRequestFailedError(
                self.name.value,
                detail={"providerTaskId": provider_task_id, "reason": "job_not_found"},
            )
        return job

    async def _execute_job(self, job: YuanqiJob) -> None:
        try:
            job.status = TaskStatus.RUNNING
            job.stage = StageCode.PARSING
            job.progress = 24
            document_text = await self._extract_document_text(job, required=True)

            result = await self._submit_openapi_request(
                job=job,
                document_text=document_text,
                use_variable_mode=True,
            )

            await self._finalize_success(job, result)
        except asyncio.CancelledError:
            logger.warning(
                "Tencent Yuanqi task cancelled taskId=%s provider=%s file=%s",
                job.task_id,
                self.name.value,
                job.file_name,
            )
            raise
        except Exception as exc:
            await self._fail_job(job, exc)

    async def _submit_openapi_request(
        self,
        *,
        job: YuanqiJob,
        document_text: str,
        use_variable_mode: bool,
    ) -> YuanqiExecutionResult:
        payload, preview = self._build_payload(job=job, document_text=document_text, use_variable_mode=use_variable_mode)
        job.used_variable_mode = use_variable_mode
        job.used_text_fallback = False
        job.stage = StageCode.REVIEWING
        job.progress = 68

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._auth_secret}",
        }
        request_snapshot = self._build_request_snapshot(
            job=job,
            payload=payload,
            headers=headers,
            use_variable_mode=use_variable_mode,
        )
        mode_decision = self._build_mode_decision(job=job, use_variable_mode=use_variable_mode)

        logger.info(
            "Tencent Yuanqi request preview taskId=%s provider=%s api_url=%s assistant_id=%s review_role=%s contract_text_length=%s uses_variable_mode=%s variables_field_name=%s variable_keys=%s variable_mode_message_text=%s message_text_length=%s uses_text_fallback=%s body_summary=%s",
            job.task_id,
            self.name.value,
            job.api_url,
            job.assistant_id,
            job.review_role,
            len(document_text),
            use_variable_mode,
            self._settings.yuanqi_variables_field_name,
            preview["variableKeys"],
            preview["variable_mode_message_text"],
            preview["message_text_length"],
            False,
            preview,
        )
        logger.info(
            "Tencent Yuanqi mode decision taskId=%s provider=%s decision=%s",
            job.task_id,
            self.name.value,
            json.dumps(mode_decision, ensure_ascii=False),
        )
        logger.info(
            "Tencent Yuanqi final request snapshot taskId=%s provider=%s request=%s",
            job.task_id,
            self.name.value,
            json.dumps(request_snapshot, ensure_ascii=False),
        )

        try:
            response = await self._client.post(job.api_url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "reason": str(exc),
                    "usesVariableMode": True,
                    "variablesFieldName": self._settings.yuanqi_variables_field_name,
                    "variableKeys": preview["variableKeys"],
                },
            ) from exc

        job.upstream_status_code = response.status_code
        response_debug = self._build_response_debug(response)

        if response.status_code in {401, 403}:
            logger.warning(
                "Tencent Yuanqi upstream auth failure taskId=%s provider=%s response=%s",
                job.task_id,
                self.name.value,
                json.dumps(response_debug, ensure_ascii=False),
            )
            raise ProviderAuthFailedError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "statusCode": response.status_code,
                },
            )

        if response.status_code >= 400:
            logger.warning(
                "Tencent Yuanqi upstream error taskId=%s provider=%s response=%s",
                job.task_id,
                self.name.value,
                json.dumps(response_debug, ensure_ascii=False),
            )
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "statusCode": response.status_code,
                    "responseSnippet": response.text[:500],
                    "usesVariableMode": True,
                    "variablesFieldName": self._settings.yuanqi_variables_field_name,
                    "variableKeys": preview["variableKeys"],
                    "responseHeaders": response_debug["headers"],
                    "traceHeaders": response_debug["traceHeaders"],
                    "responseTextRepr": response_debug["textRepr"],
                    "responseContentLength": response_debug["contentLength"],
                },
            )

        try:
            raw_payload = response.json()
        except ValueError as exc:
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "statusCode": response.status_code,
                    "reason": "non_json_response",
                    "responseSnippet": response.text[:500],
                },
            ) from exc

        if not isinstance(raw_payload, dict):
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "statusCode": response.status_code,
                    "reason": "non_object_response",
                },
            )

        steps = self._extract_steps(raw_payload)
        usage = self._extract_usage(raw_payload)
        primary_text = self._extract_primary_text(raw_payload)
        normalized_payload = self._normalize_response_payload(
            raw_payload=raw_payload,
            primary_text=primary_text,
            steps=steps,
            usage=usage,
        )
        parsed_successfully = bool(primary_text or self._looks_like_structured_result(normalized_payload))
        if not parsed_successfully:
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "statusCode": response.status_code,
                    "reason": "missing_parseable_content",
                    "responseSummary": self._summarize_payload(raw_payload),
                },
            )

        logger.info(
            "Tencent Yuanqi upstream response taskId=%s provider=%s api_url=%s status_code=%s parsed_result=%s response_summary=%s",
            job.task_id,
            self.name.value,
            job.api_url,
            response.status_code,
            parsed_successfully,
            self._summarize_payload(raw_payload),
        )

        return YuanqiExecutionResult(
            raw_response=raw_payload,
            normalized_payload=normalized_payload,
            usage=usage,
            steps=steps,
            response_text_length=len(primary_text),
            parsed_successfully=parsed_successfully,
        )

    async def _finalize_success(self, job: YuanqiJob, result: YuanqiExecutionResult) -> None:
        job.stage = StageCode.SUMMARIZING
        job.progress = 92
        job.raw_response = result.raw_response
        job.normalized_response = result.normalized_payload
        job.usage = result.usage
        job.steps = result.steps
        job.response_text_length = result.response_text_length
        job.parsed_successfully = result.parsed_successfully
        job.status = TaskStatus.SUCCEEDED
        job.stage = StageCode.COMPLETED
        job.progress = 100

        logger.info(
            "Tencent Yuanqi request succeeded taskId=%s provider=%s api_url=%s assistant_id=%s review_role=%s contract_text_length=%s uses_variable_mode=%s variables_field_name=%s variable_keys=%s uses_text_fallback=%s upstream_status_code=%s parsed_result=%s",
            job.task_id,
            self.name.value,
            job.api_url,
            job.assistant_id,
            job.review_role,
            len(job.document_text or ""),
            job.used_variable_mode,
            self._settings.yuanqi_variables_field_name,
            self._variable_keys if job.used_variable_mode else [],
            job.used_text_fallback,
            job.upstream_status_code,
            job.parsed_successfully,
        )

    async def _fail_job(self, job: YuanqiJob, exc: Exception) -> None:
        if isinstance(
            exc,
            (
                ProviderAuthFailedError,
                ProviderInvalidUrlError,
                ProviderNotConfiguredError,
                ProviderRequestFailedError,
                ProviderResponseInvalidError,
                DocumentParseFailedError,
                DocumentEmptyError,
            ),
        ):
            job.error = exc
            failure_summary = self._unwrap_error_detail(exc)
        else:
            job.error = ProviderRequestFailedError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "providerTaskId": job.provider_task_id,
                    "reason": str(exc),
                },
            )
            failure_summary = self._unwrap_error_detail(job.error)

        job.status = TaskStatus.FAILED
        job.progress = 100

        logger.warning(
            "Tencent Yuanqi provider failed taskId=%s provider=%s api_url=%s assistant_id=%s review_role=%s contract_text_length=%s uses_variable_mode=%s variables_field_name=%s variable_keys=%s uses_text_fallback=%s upstream_status_code=%s reason=%s",
            job.task_id,
            self.name.value,
            job.api_url,
            job.assistant_id,
            job.review_role,
            len(job.document_text or ""),
            job.used_variable_mode,
            self._settings.yuanqi_variables_field_name,
            self._variable_keys if job.used_variable_mode else [],
            job.used_text_fallback,
            job.upstream_status_code,
            failure_summary,
        )

    async def _extract_document_text(self, job: YuanqiJob, *, required: bool) -> str:
        if job.document_text is not None:
            return job.document_text

        try:
            document_text = await asyncio.to_thread(self._document_parser.extract_text, job.request.file_info)
        except (DocumentParseFailedError, DocumentEmptyError):
            raise

        job.document_text = document_text
        logger.info(
            "Document text extracted taskId=%s provider=%s review_role=%s contract_text_length=%s",
            job.task_id,
            self.name.value,
            job.review_role,
            len(document_text),
        )
        return document_text

    def _build_payload(
        self,
        *,
        job: YuanqiJob,
        document_text: str,
        use_variable_mode: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        message_text = self._build_user_message(
            review_role=job.review_role,
            file_name=job.file_name,
            contract_text=document_text,
            use_variable_mode=use_variable_mode,
        )
        payload: dict[str, Any] = {
            "assistant_id": self._settings.yuanqi_app_id,
            "user_id": job.task_id,
            "stream": False,
        }

        if use_variable_mode:
            payload[self._settings.yuanqi_variables_field_name] = {
                "contract_text": document_text,
                "review_role": job.review_role,
                "file_name": job.file_name,
            }

        payload["messages"] = [
            {
                "role": "user",
                "content": [{"type": "text", "text": message_text}],
            }
        ]

        preview = {
            "topLevelKeys": list(payload.keys()),
            "messageCount": len(payload["messages"]),
            "contentType": type(payload["messages"][0]["content"]).__name__,
            "contentLength": len(payload["messages"][0]["content"]),
            "usesVariableMode": True,
            "variablesFieldName": self._settings.yuanqi_variables_field_name,
            "variableKeys": self._variable_keys,
            "variableValueTypes": self._variable_value_types(document_text, job.review_role, job.file_name),
            "variableValueLengths": self._variable_value_lengths(document_text, job.review_role, job.file_name),
            "variable_mode_message_text": message_text if use_variable_mode else "",
            "message_text_length": len(message_text),
            "usesTextFallback": False,
            "contractTextLength": len(document_text),
        }
        return payload, preview

    def _build_user_message(
        self,
        *,
        review_role: str,
        file_name: str,
        contract_text: str,
        use_variable_mode: bool,
    ) -> str:
        if use_variable_mode:
            return "请执行合同审查工作流。"

        common_lines = [
            f"你是合同审查助手。请从{review_role}视角审查合同，并输出结构化、稳定、可解析的结果。",
            "请至少输出：合同基本信息、总体风险等级、高中低风险统计、总体结论、完整报告、逐条重点问题，以及每个问题的风险说明、证据引用、修改建议、原文与建议修订。",
            f"合同文件名：{file_name}",
            f"审查视角：{review_role}",
        ]
        common_lines.extend(["以下是合同全文：", contract_text])
        return "\n".join(common_lines)

    def _build_request_snapshot(
        self,
        *,
        job: YuanqiJob,
        payload: dict[str, Any],
        headers: dict[str, str],
        use_variable_mode: bool,
    ) -> dict[str, Any]:
        variables_field_name = self._settings.yuanqi_variables_field_name
        return {
            "url": job.api_url,
            "headers": self._sanitize_headers(headers),
            "jsonBody": payload,
            "assistant_id": payload.get("assistant_id"),
            "messages": payload.get("messages"),
            "custom_variables_field_name": variables_field_name,
            "custom_variables": payload.get(variables_field_name),
            "visitor_biz_id": job.request.visitor_biz_id,
            "request_id": None,
            "request_id_source": "not present in outgoing chat/completions payload or headers",
            "stream": payload.get("stream"),
            "uses_variable_mode": use_variable_mode,
        }

    def _build_mode_decision(self, *, job: YuanqiJob, use_variable_mode: bool) -> dict[str, Any]:
        return {
            "api_url": job.api_url,
            "api_mode": "chat/completions",
            "still_using_chat_completions": True,
            "decision_source": "_execute_job hardcodes use_variable_mode=True when calling _submit_openapi_request",
            "use_variable_mode_argument": use_variable_mode,
            "supports_variable_mode": self._supports_variable_mode,
            "supports_variable_mode_reason": (
                "YUANQI_VARIABLES_FIELD_NAME is non-empty"
                if self._supports_variable_mode
                else "YUANQI_VARIABLES_FIELD_NAME is empty"
            ),
            "variables_field_name": self._settings.yuanqi_variables_field_name,
            "variable_keys": self._variable_keys,
            "uses_text_fallback": False,
            "text_fallback_reason": "TencentYuanqiProvider currently has no fallback branch in _execute_job or _submit_openapi_request",
            "message_mode": "workflow trigger text plus custom_variables" if use_variable_mode else "plain contract text prompt",
            "visitor_biz_id": job.request.visitor_biz_id,
        }

    @staticmethod
    def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
        sanitized = dict(headers)
        authorization = sanitized.get("Authorization")
        if authorization:
            sanitized["Authorization"] = TencentYuanqiProvider._mask_authorization(authorization)
        return sanitized

    @staticmethod
    def _mask_authorization(value: str) -> str:
        prefix = "Bearer "
        if not value.startswith(prefix):
            return "***"
        secret = value[len(prefix) :]
        if len(secret) <= 8:
            return f"{prefix}***"
        return f"{prefix}{secret[:4]}...{secret[-4:]}"

    @staticmethod
    def _build_response_debug(response: httpx.Response) -> dict[str, Any]:
        headers = dict(response.headers)
        trace_headers = {
            "x-request-id": headers.get("x-request-id"),
            "trace-id": headers.get("trace-id"),
            "tc-trace-id": headers.get("tc-trace-id"),
        }
        return {
            "statusCode": response.status_code,
            "headers": headers,
            "traceHeaders": trace_headers,
            "textRepr": repr(response.text),
            "contentLength": len(response.content),
        }

    def _normalize_response_payload(
        self,
        *,
        raw_payload: dict[str, Any],
        primary_text: str,
        steps: list[dict[str, Any]] | None,
        usage: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized = dict(raw_payload)
        if primary_text:
            normalized.setdefault("reportText", primary_text)
            if not isinstance(normalized.get("choices"), list):
                message: dict[str, Any] = {"content": primary_text}
                if steps:
                    message["steps"] = steps
                normalized["choices"] = [{"message": message}]

        if usage and not isinstance(normalized.get("usage"), dict):
            normalized["usage"] = usage
        if steps and not isinstance(normalized.get("steps"), list):
            normalized["steps"] = steps
        return normalized

    def _extract_usage(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        usage = payload.get("usage")
        if isinstance(usage, dict):
            return usage
        return None

    def _extract_steps(self, payload: dict[str, Any]) -> list[dict[str, Any]] | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return None
        message = first_choice.get("message")
        if not isinstance(message, dict):
            return None
        steps = message.get("steps")
        if isinstance(steps, list):
            return [step for step in steps if isinstance(step, dict)]
        return None

    def _extract_primary_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return ""
        message = first_choice.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    value = item.strip()
                    if value:
                        chunks.append(value)
                    continue
                if isinstance(item, dict):
                    value = item.get("text") or item.get("content") or item.get("value")
                    if isinstance(value, str) and value.strip():
                        chunks.append(value.strip())
            return "\n".join(chunks).strip()
        return ""

    def _looks_like_structured_result(self, payload: dict[str, Any]) -> bool:
        keys = set(payload.keys())
        markers = {
            "basicInfo",
            "summary",
            "stats",
            "workflow",
            "fullReport",
            "issues",
            "contractSections",
            "reportText",
            "report",
            "analysis",
            "conclusion",
            "choices",
        }
        return bool(keys & markers)

    def _ensure_minimum_configured(self, request: ProviderCreateReviewRequest) -> None:
        missing: list[str] = []
        if not self._settings.yuanqi_api_url:
            missing.append("YUANQI_API_URL")
        if not self._auth_secret:
            missing.append("YUANQI_APP_KEY")
        if not self._settings.yuanqi_app_id:
            missing.append("YUANQI_APP_ID")
        if not request.review_role.value:
            missing.append("review_role")
        if not self._supports_variable_mode:
            missing.append("YUANQI_VARIABLES_FIELD_NAME")

        if missing:
            raise ProviderNotConfiguredError(self.name.value, detail={"missing": missing})

        self._ensure_valid_http_url(self._settings.yuanqi_api_url, "YUANQI_API_URL")

    def _ensure_valid_http_url(self, value: str, field_name: str) -> None:
        if not value:
            raise ProviderInvalidUrlError(self.name.value, detail={"field": field_name, "reason": "missing"})
        try:
            parsed = httpx.URL(value)
        except Exception as exc:
            raise ProviderInvalidUrlError(
                self.name.value,
                detail={"field": field_name, "reason": str(exc), "value": value},
            ) from exc
        if parsed.scheme not in {"http", "https"} or not parsed.host:
            raise ProviderInvalidUrlError(
                self.name.value,
                detail={"field": field_name, "reason": "invalid_http_url", "value": value},
            )

    @property
    def _auth_secret(self) -> str:
        return self._settings.yuanqi_app_key or self._settings.yuanqi_api_key

    @property
    def _supports_variable_mode(self) -> bool:
        return bool(self._settings.yuanqi_variables_field_name.strip())

    @property
    def _variable_keys(self) -> list[str]:
        return ["contract_text", "review_role", "file_name"]

    @staticmethod
    def _variable_value_types(contract_text: str, review_role: str, file_name: str) -> dict[str, str]:
        return {
            "contract_text": type(contract_text).__name__,
            "review_role": type(review_role).__name__,
            "file_name": type(file_name).__name__,
        }

    @staticmethod
    def _variable_value_lengths(contract_text: str, review_role: str, file_name: str) -> dict[str, int]:
        return {
            "contract_text": len(contract_text),
            "review_role": len(review_role),
            "file_name": len(file_name),
        }


    @staticmethod
    def _unwrap_error_detail(exc: Exception) -> Any:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict) and "detail" in detail:
            return detail.get("detail")
        return detail or str(exc)

    def _summarize_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            summary: dict[str, Any] = {"keys": list(payload.keys())[:12]}
            choices = payload.get("choices")
            if isinstance(choices, list):
                summary["choicesCount"] = len(choices)
            usage = payload.get("usage")
            if isinstance(usage, dict):
                summary["usageKeys"] = list(usage.keys())
            summary["hasPrimaryText"] = bool(self._extract_primary_text(payload))
            return summary
        if isinstance(payload, list):
            return {"type": "list", "length": len(payload)}
        if isinstance(payload, str):
            return {"type": "text", "length": len(payload)}
        return {"type": type(payload).__name__}





















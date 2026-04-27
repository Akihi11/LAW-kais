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
    WorkflowExecutionStatus,
    get_stage_label,
)
from app.utils.document_parser import DocumentParser
from app.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class YuanqiSseExecutionResult:
    raw_response: dict[str, Any]
    normalized_payload: dict[str, Any]
    usage: dict[str, Any] | None
    steps: list[dict[str, Any]] | None
    parsed_successfully: bool


@dataclass
class YuanqiSseJob:
    request: ProviderCreateReviewRequest
    task_id: str
    provider_task_id: str
    api_url: str
    bot_app_key: str
    request_id: str
    session_id: str
    visitor_biz_id: str
    review_role: str
    file_name: str
    file_url: str
    document_text: str | None = None
    contract_text_sent: str = ""
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
    upstream_status_code: int | None = None
    latest_event_message: str | None = None
    event_records: list[dict[str, Any]] = field(default_factory=list)
    workflow_snapshots: list[dict[str, Any]] = field(default_factory=list)
    text_chunks: list[str] = field(default_factory=list)
    has_run_nodes: bool = False
    has_workflow_procedure: bool = False
    latest_status_summary: str | None = None
    parsed_successfully: bool = False


class TencentYuanqiSseProvider(BaseProvider):
    """Deprecated: legacy SSE experiment provider. Keep only for compatibility/testing."""
    name = ProviderName.TENCENT_YUANQI_SSE

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._document_parser = DocumentParser(self.name)
        self._jobs: dict[str, YuanqiSseJob] = {}
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

        provider_task_id = f"yuanqi_sse_{request.task_id}_{uuid4().hex[:8]}"
        session_id = str(uuid4())
        preview = {
            "provider": self.name.value,
            "apiUrl": self._settings.yuanqi_sse_api_url,
            "botAppKeyMasked": self._mask_secret(self._bot_app_key),
            "botAppKeySource": self._bot_app_key_source,
            "requestId": request.task_id,
            "officialMinimalMode": self._settings.yuanqi_sse_official_minimal_mode,
            "sessionId": session_id,
            "visitorBizId": self._settings.yuanqi_sse_visitor_biz_id,
            "workflowStatus": self._settings.yuanqi_sse_workflow_status,
            "stream": self._settings.yuanqi_sse_stream,
            "variableKeys": self._variable_keys,
            "contentText": self._variable_mode_message_text,
        }

        logger.info(
            "Prepared Tencent Yuanqi SSE task taskId=%s provider=%s api_url=%s bot_app_key_masked=%s bot_app_key_source=%s request_id=%s session_id=%s visitor_biz_id=%s workflow_status=%s stream=%s official_minimal_mode=%s variable_keys=%s",
            request.task_id,
            self.name.value,
            self._settings.yuanqi_sse_api_url,
            self._mask_secret(self._bot_app_key),
            self._bot_app_key_source,
            request.task_id,
            session_id,
            self._settings.yuanqi_sse_visitor_biz_id,
            self._settings.yuanqi_sse_workflow_status,
            self._settings.yuanqi_sse_stream,
            self._settings.yuanqi_sse_official_minimal_mode,
            self._variable_keys,
        )

        job = YuanqiSseJob(
            request=request,
            task_id=request.task_id,
            provider_task_id=provider_task_id,
            api_url=self._settings.yuanqi_sse_api_url,
            bot_app_key=self._bot_app_key,
            request_id=request.task_id,
            session_id=session_id,
            visitor_biz_id=self._settings.yuanqi_sse_visitor_biz_id,
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
        steps = self._build_steps(job)
        workflow_groups = self._build_workflow_groups(job, steps) if steps else None
        return ProviderStatus(
            status=job.status,
            current_stage=job.stage,
            current_stage_label=get_stage_label(job.stage),
            progress=job.progress,
            error_message=self._status_message(job),
            workflow_groups=workflow_groups,
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

    async def _get_job(self, provider_task_id: str) -> YuanqiSseJob:
        async with self._lock:
            job = self._jobs.get(provider_task_id)

        if job is None:
            raise ProviderRequestFailedError(
                self.name.value,
                detail={"providerTaskId": provider_task_id, "reason": "job_not_found"},
            )
        return job

    async def _execute_job(self, job: YuanqiSseJob) -> None:
        try:
            job.status = TaskStatus.RUNNING
            job.stage = StageCode.PARSING
            job.progress = 18
            document_text = await self._extract_document_text(job)
            contract_text_sent = self._clip_custom_variable(document_text)
            job.contract_text_sent = contract_text_sent

            result = await self._consume_sse(job=job, contract_text_sent=contract_text_sent)
            await self._finalize_success(job, result)
        except asyncio.CancelledError:
            logger.warning(
                "Tencent Yuanqi SSE task cancelled taskId=%s provider=%s session_id=%s",
                job.task_id,
                self.name.value,
                job.session_id,
            )
            raise
        except Exception as exc:
            await self._fail_job(job, exc)

    async def _consume_sse(self, *, job: YuanqiSseJob, contract_text_sent: str) -> YuanqiSseExecutionResult:
        payload, preview = self._build_payload(job=job, contract_text_sent=contract_text_sent)
        job.stage = StageCode.REVIEWING
        job.progress = 42

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        logger.info(
            "Tencent Yuanqi SSE request preview taskId=%s provider=%s official_minimal_mode=%s api_url=%s bot_app_key_masked=%s payload_top_level_keys=%s workflow_status=%s stream=%s has_custom_variables=%s has_authorization_header=%s request_id=%s session_id=%s visitor_biz_id=%s content_text=%s variable_keys=%s variable_value_lengths=%s",
            job.task_id,
            self.name.value,
            preview["officialMinimalMode"],
            job.api_url,
            self._mask_secret(job.bot_app_key),
            preview["payloadTopLevelKeys"],
            preview["workflowStatus"],
            preview["stream"],
            preview["hasCustomVariables"],
            preview["hasAuthorizationHeader"],
            job.request_id,
            job.session_id,
            job.visitor_biz_id,
            preview["contentText"],
            preview["variableKeys"],
            preview["variableValueLengths"],
        )

        try:
            async with self._client.stream("POST", job.api_url, json=payload, headers=headers) as response:
                job.upstream_status_code = response.status_code
                content_type = response.headers.get("content-type", "")
                logger.info(
                    "Tencent Yuanqi SSE response opened taskId=%s provider=%s status_code=%s content_type=%s",
                    job.task_id,
                    self.name.value,
                    response.status_code,
                    content_type,
                )

                if response.status_code in {401, 403}:
                    raise ProviderAuthFailedError(
                        self.name.value,
                        detail={
                            "taskId": job.task_id,
                            "requestUrl": job.api_url,
                            "statusCode": response.status_code,
                        },
                    )

                if response.status_code >= 400:
                    error_text = await response.aread()
                    raise ProviderRequestFailedError(
                        self.name.value,
                        detail={
                            "taskId": job.task_id,
                            "requestUrl": job.api_url,
                            "statusCode": response.status_code,
                            "responseSnippet": error_text.decode("utf-8", errors="ignore")[:500],
                        },
                    )

                event_name: str | None = None
                data_lines: list[str] = []

                async for line in response.aiter_lines():
                    if line == "":
                        self._record_sse_event(job, event_name, data_lines)
                        event_name = None
                        data_lines = []
                        continue

                    if not line or line.startswith(":"):
                        continue

                    field, _, value = line.partition(":")
                    if field == "event":
                        event_name = value.strip()
                    elif field == "data":
                        data_lines.append(value.lstrip())
                    else:
                        data_lines.append(line)

                self._record_sse_event(job, event_name, data_lines)
        except httpx.RequestError as exc:
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "reason": str(exc),
                    "requestId": job.request_id,
                    "sessionId": job.session_id,
                },
            ) from exc

        if not job.event_records:
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "reason": "no_sse_events",
                },
            )

        steps = self._build_steps(job)
        workflow_groups = self._build_workflow_groups(job, steps)
        report_text = "\n\n".join(job.text_chunks).strip() or "SSE 工作流验证已完成。"
        normalized_payload = {
            "reportText": report_text,
            "workflow": {"groups": workflow_groups},
            "steps": steps,
            "sse": {
                "sessionId": job.session_id,
                "requestId": job.request_id,
                "visitorBizId": job.visitor_biz_id,
                "eventCount": len(job.event_records),
                "hasRunNodes": job.has_run_nodes,
                "hasWorkflowProcedure": job.has_workflow_procedure,
                "latestStatusSummary": job.latest_status_summary,
                "events": job.event_records[-50:],
                "workflowSnapshots": job.workflow_snapshots[-10:],
            },
        }
        usage = {
            "provider": self.name.value,
            "eventCount": len(job.event_records),
            "hasRunNodes": job.has_run_nodes,
            "hasWorkflowProcedure": job.has_workflow_procedure,
            "upstreamStatusCode": job.upstream_status_code,
        }
        parsed_successfully = bool(report_text or steps or workflow_groups)
        if not parsed_successfully:
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "reason": "missing_sse_workflow_content",
                },
            )

        logger.info(
            "Tencent Yuanqi SSE stream consumed taskId=%s provider=%s event_count=%s has_run_nodes=%s has_workflow_procedure=%s latest_status_summary=%s",
            job.task_id,
            self.name.value,
            len(job.event_records),
            job.has_run_nodes,
            job.has_workflow_procedure,
            job.latest_status_summary,
        )

        return YuanqiSseExecutionResult(
            raw_response=normalized_payload,
            normalized_payload=normalized_payload,
            usage=usage,
            steps=steps,
            parsed_successfully=parsed_successfully,
        )

    async def _finalize_success(self, job: YuanqiSseJob, result: YuanqiSseExecutionResult) -> None:
        job.stage = StageCode.SUMMARIZING
        job.progress = 92
        job.raw_response = result.raw_response
        job.normalized_response = result.normalized_payload
        job.usage = result.usage
        job.steps = result.steps
        job.parsed_successfully = result.parsed_successfully
        job.status = TaskStatus.SUCCEEDED
        job.stage = StageCode.COMPLETED
        job.progress = 100
        job.latest_event_message = None

        logger.info(
            "Tencent Yuanqi SSE request succeeded taskId=%s provider=%s session_id=%s request_id=%s event_count=%s has_run_nodes=%s has_workflow_procedure=%s",
            job.task_id,
            self.name.value,
            job.session_id,
            job.request_id,
            len(job.event_records),
            job.has_run_nodes,
            job.has_workflow_procedure,
        )

    async def _fail_job(self, job: YuanqiSseJob, exc: Exception) -> None:
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
        job.latest_event_message = self._trim_text(self._stringify(failure_summary), 240)

        logger.warning(
            "Tencent Yuanqi SSE provider failed taskId=%s provider=%s session_id=%s request_id=%s upstream_status_code=%s latest_event=%s reason=%s",
            job.task_id,
            self.name.value,
            job.session_id,
            job.request_id,
            job.upstream_status_code,
            job.latest_event_message,
            failure_summary,
        )

    async def _extract_document_text(self, job: YuanqiSseJob) -> str:
        if job.document_text is not None:
            return job.document_text

        try:
            document_text = await asyncio.to_thread(self._document_parser.extract_text, job.request.file_info)
        except (DocumentParseFailedError, DocumentEmptyError):
            raise

        job.document_text = document_text
        logger.info(
            "Tencent Yuanqi SSE document text extracted taskId=%s provider=%s review_role=%s contract_text_length=%s",
            job.task_id,
            self.name.value,
            job.review_role,
            len(document_text),
        )
        return document_text

    def _build_payload(self, *, job: YuanqiSseJob, contract_text_sent: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if self._settings.yuanqi_sse_official_minimal_mode:
            payload = {
                "session_id": job.session_id,
                "bot_app_key": job.bot_app_key,
                "visitor_biz_id": job.visitor_biz_id,
                "content": "\u4f60\u597d",
                "incremental": True,
                "streaming_throttle": 10,
                "visitor_labels": [],
                "custom_variables": {},
                "search_network": "disable",
                "stream": "enable",
                "workflow_status": "disable",
                "tcadp_user_id": "",
            }
            preview = {
                "topLevelKeys": list(payload.keys()),
                "payloadTopLevelKeys": list(payload.keys()),
                "variableKeys": [],
                "variableValueLengths": {},
                "contentText": "\u4f60\u597d",
                "messageTextLength": 2,
                "workflowStatus": "disable",
                "stream": "enable",
                "officialMinimalMode": True,
                "hasCustomVariables": False,
                "hasAuthorizationHeader": False,
            }
            return payload, preview

        custom_variables = {
            "contract_text": contract_text_sent,
            "review_role": self._clip_custom_variable(job.review_role),
            "file_name": self._clip_custom_variable(job.file_name),
        }
        payload = {
            "bot_app_key": job.bot_app_key,
            "session_id": job.session_id,
            "visitor_biz_id": job.visitor_biz_id,
            "request_id": job.request_id,
            "content": self._variable_mode_message_text,
            "custom_variables": custom_variables,
            "workflow_status": self._settings.yuanqi_sse_workflow_status,
            "stream": self._settings.yuanqi_sse_stream,
        }
        preview = {
            "topLevelKeys": list(payload.keys()),
            "payloadTopLevelKeys": list(payload.keys()),
            "variableKeys": list(custom_variables.keys()),
            "variableValueLengths": {key: len(value) for key, value in custom_variables.items()},
            "contentText": self._variable_mode_message_text,
            "messageTextLength": len(self._variable_mode_message_text),
            "workflowStatus": self._settings.yuanqi_sse_workflow_status,
            "stream": self._settings.yuanqi_sse_stream,
            "officialMinimalMode": False,
            "hasCustomVariables": bool(custom_variables),
            "hasAuthorizationHeader": False,
        }
        return payload, preview

    def _record_sse_event(self, job: YuanqiSseJob, event_name: str | None, data_lines: list[str]) -> None:
        if not event_name and not data_lines:
            return

        raw_text = "\n".join(data_lines).strip()
        if not raw_text:
            return
        if raw_text == "[DONE]":
            job.latest_event_message = "收到 SSE 结束事件。"
            job.progress = max(job.progress, 88)
            job.stage = StageCode.SUMMARIZING
            logger.info(
                "Tencent Yuanqi SSE event taskId=%s provider=%s event=%s summary=%s",
                job.task_id,
                self.name.value,
                event_name or "message",
                job.latest_event_message,
            )
            return

        payload = self._parse_sse_payload(raw_text)
        error_detail = self._extract_error_detail(payload)
        event_record = self._summarize_sse_event(event_name or "message", payload, raw_text)
        job.event_records.append(event_record)
        if len(job.event_records) > 100:
            job.event_records = job.event_records[-100:]

        workflow_snapshot = self._extract_workflow_snapshot(event_name or "message", payload)
        if workflow_snapshot is not None:
            job.workflow_snapshots.append(workflow_snapshot)
            if len(job.workflow_snapshots) > 20:
                job.workflow_snapshots = job.workflow_snapshots[-20:]
            if workflow_snapshot.get("runNodes"):
                job.has_run_nodes = True
            if workflow_snapshot.get("workflowProcedure"):
                job.has_workflow_procedure = True
            if workflow_snapshot.get("statusSummary"):
                job.latest_status_summary = workflow_snapshot.get("statusSummary")

        text_fragment = self._extract_text_fragment(payload)
        if text_fragment:
            if text_fragment not in job.text_chunks:
                job.text_chunks.append(text_fragment)
            job.stage = StageCode.SUMMARIZING
            job.progress = max(job.progress, 84)
        elif workflow_snapshot is not None:
            job.stage = StageCode.EXTRACTING
            job.progress = max(job.progress, 66)
        else:
            job.stage = StageCode.REVIEWING
            job.progress = max(job.progress, 52)

        job.latest_event_message = event_record["summaryText"]

        logger.info(
            "Tencent Yuanqi SSE event taskId=%s provider=%s event=%s summary=%s",
            job.task_id,
            self.name.value,
            event_record["event"],
            event_record["summaryText"],
        )

        if error_detail:
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "taskId": job.task_id,
                    "requestUrl": job.api_url,
                    "requestId": job.request_id,
                    "sessionId": job.session_id,
                    "event": event_record["event"],
                    "error": error_detail,
                    "eventSummary": event_record,
                },
            )

    def _summarize_sse_event(self, event_name: str, payload: Any, raw_text: str) -> dict[str, Any]:
        keys = list(payload.keys())[:12] if isinstance(payload, dict) else []
        run_nodes = self._extract_named_value(payload, {"runnodes"})
        workflow_procedure = self._extract_named_value(payload, {"workflowprocedure"})
        status_summary = self._extract_named_value(payload, {"statussummary"})
        text_fragment = self._extract_text_fragment(payload) or self._trim_text(raw_text, 120)

        summary_parts = [f"event={event_name}"]
        if isinstance(run_nodes, list):
            summary_parts.append(f"run_nodes={len(run_nodes)}")
        if isinstance(workflow_procedure, list):
            summary_parts.append(f"workflow_procedure={len(workflow_procedure)}")
        if isinstance(status_summary, str) and status_summary.strip():
            summary_parts.append(f"status_summary={self._trim_text(status_summary, 80)}")
        if text_fragment:
            summary_parts.append(f"text={self._trim_text(text_fragment, 80)}")
        elif keys:
            summary_parts.append(f"keys={','.join(keys[:6])}")

        return {
            "event": event_name,
            "keys": keys,
            "summaryText": " | ".join(summary_parts),
            "rawTextSnippet": self._trim_text(raw_text, 200),
        }

    def _extract_workflow_snapshot(self, event_name: str, payload: Any) -> dict[str, Any] | None:
        run_nodes = self._extract_named_value(payload, {"runnodes"})
        workflow_procedure = self._extract_named_value(payload, {"workflowprocedure"})
        status = self._extract_named_value(payload, {"status"})
        status_summary = self._extract_named_value(payload, {"statussummary"})

        if not any([run_nodes, workflow_procedure, status, status_summary]):
            return None

        return {
            "event": event_name,
            "status": self._stringify(status),
            "statusSummary": self._stringify(status_summary),
            "runNodes": self._summarize_nodes(run_nodes if isinstance(run_nodes, list) else []),
            "workflowProcedure": self._summarize_nodes(
                workflow_procedure if isinstance(workflow_procedure, list) else []
            ),
        }

    def _build_steps(self, job: YuanqiSseJob) -> list[dict[str, Any]]:
        latest = job.workflow_snapshots[-1] if job.workflow_snapshots else None
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()

        for collection_name in ("runNodes", "workflowProcedure"):
            if not isinstance(latest, dict):
                continue
            for node in latest.get(collection_name) or []:
                name = self._stringify(node.get("name"))
                if not name or name in seen:
                    continue
                seen.add(name)
                nodes.append(
                    {
                        "name": name,
                        "status": self._normalize_workflow_status(node.get("status")),
                    }
                )

        return nodes[:20]

    def _build_workflow_groups(self, job: YuanqiSseJob, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not steps:
            status = WorkflowExecutionStatus.FAILED.value if job.status == TaskStatus.FAILED else WorkflowExecutionStatus.RUNNING.value
            return [{"name": "SSE 工作流验证", "status": status, "nodes": []}]

        statuses = {step.get("status") for step in steps}
        if WorkflowExecutionStatus.FAILED.value in statuses or job.status == TaskStatus.FAILED:
            group_status = WorkflowExecutionStatus.FAILED.value
        elif statuses == {WorkflowExecutionStatus.DONE.value}:
            group_status = WorkflowExecutionStatus.DONE.value
        elif WorkflowExecutionStatus.RUNNING.value in statuses:
            group_status = WorkflowExecutionStatus.RUNNING.value
        else:
            group_status = WorkflowExecutionStatus.PENDING.value

        return [{"name": "SSE 工作流验证", "status": group_status, "nodes": steps}]

    def _extract_text_fragment(self, payload: Any) -> str:
        candidates = self._collect_named_values(
            payload,
            {"answer", "content", "text", "message", "finalanswer", "reply"},
        )
        for candidate in candidates:
            if isinstance(candidate, str):
                value = candidate.strip()
                if value and len(value) <= 2000:
                    return value
            if isinstance(candidate, list):
                chunks: list[str] = []
                for item in candidate:
                    if isinstance(item, str) and item.strip():
                        chunks.append(item.strip())
                    elif isinstance(item, dict):
                        for key in ("text", "content", "value"):
                            value = item.get(key)
                            if isinstance(value, str) and value.strip():
                                chunks.append(value.strip())
                                break
                if chunks:
                    return "\n".join(chunks)[:2000]
        return ""

    def _extract_error_detail(self, payload: Any) -> dict[str, Any] | str | None:
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return {
                    "message": self._coalesce(
                        self._stringify(error.get("message")),
                        self._stringify(error.get("msg")),
                    ),
                    "code": self._stringify(error.get("code")),
                }
            if isinstance(error, str) and error.strip():
                return error.strip()

            for key in ("errmsg", "error_message"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _extract_named_value(self, payload: Any, names: set[str]) -> Any:
        values = self._collect_named_values(payload, names)
        return values[0] if values else None

    def _collect_named_values(self, payload: Any, names: set[str]) -> list[Any]:
        collected: list[Any] = []

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    normalized_key = self._normalize_key_name(str(key))
                    if normalized_key in names:
                        collected.append(item)
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(payload)
        return collected

    def _parse_sse_payload(self, raw_text: str) -> Any:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            return raw_text

    def _summarize_nodes(self, items: list[Any]) -> list[dict[str, Any]]:
        summarized: list[dict[str, Any]] = []
        for index, item in enumerate(items[:20], start=1):
            if isinstance(item, dict):
                name = self._coalesce(
                    self._stringify(item.get("name")),
                    self._stringify(item.get("NodeName")),
                    self._stringify(item.get("title")),
                    self._stringify(item.get("Title")),
                    f"node_{index}",
                )
                status = self._coalesce(
                    self._stringify(item.get("status")),
                    self._stringify(item.get("Status")),
                    self._stringify(item.get("status_summary")),
                    self._stringify(item.get("StatusSummary")),
                )
                summarized.append({"name": name, "status": self._normalize_workflow_status(status)})
            elif isinstance(item, str) and item.strip():
                summarized.append({"name": item.strip(), "status": WorkflowExecutionStatus.RUNNING.value})
        return summarized

    def _normalize_workflow_status(self, value: Any) -> str:
        text = self._normalize_key_name(self._stringify(value))
        if any(token in text for token in ("fail", "error", "exception")):
            return WorkflowExecutionStatus.FAILED.value
        if any(token in text for token in ("done", "success", "finish", "complete", "completed")):
            return WorkflowExecutionStatus.DONE.value
        if any(token in text for token in ("run", "process", "doing", "executing", "pending")):
            return WorkflowExecutionStatus.RUNNING.value
        return WorkflowExecutionStatus.PENDING.value

    def _ensure_minimum_configured(self, request: ProviderCreateReviewRequest) -> None:
        missing: list[str] = []
        if not self._settings.yuanqi_sse_api_url:
            missing.append("YUANQI_SSE_API_URL")
        if not self._settings.yuanqi_bot_app_key:
            missing.append("YUANQI_BOT_APP_KEY")
        if not request.review_role.value:
            missing.append("review_role")

        if missing:
            raise ProviderNotConfiguredError(self.name.value, detail={"missing": missing})

        self._ensure_valid_http_url(self._settings.yuanqi_sse_api_url, "YUANQI_SSE_API_URL")

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

    def _status_message(self, job: YuanqiSseJob) -> str | None:
        if job.status == TaskStatus.FAILED:
            return job.latest_event_message or self._render_failure_message(job.error)
        if job.status == TaskStatus.RUNNING:
            return job.latest_event_message
        return None

    def _render_failure_message(self, exc: Exception | None) -> str | None:
        if exc is None:
            return None
        return self._trim_text(self._stringify(self._unwrap_error_detail(exc)), 240)

    def _clip_custom_variable(self, value: str) -> str:
        return value.strip()[: self._settings.yuanqi_sse_contract_text_max_length]

    @property
    def _bot_app_key(self) -> str:
        return self._settings.yuanqi_bot_app_key

    @property
    def _auth_secret(self) -> str:
        return self._settings.yuanqi_app_key or self._settings.yuanqi_api_key

    @property
    def _bot_app_key_source(self) -> str:
        return "YUANQI_BOT_APP_KEY"

    @property
    def _auth_secret_source(self) -> str:
        if self._settings.yuanqi_app_key:
            return "YUANQI_APP_KEY"
        if self._settings.yuanqi_api_key:
            return "YUANQI_API_KEY"
        return "<empty>"

    @property
    def _variable_keys(self) -> list[str]:
        return ["contract_text", "review_role", "file_name"]

    @property
    def _variable_mode_message_text(self) -> str:
        return "请执行合同审查工作流。"

    @staticmethod
    def _normalize_key_name(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _trim_text(value: str, max_length: int) -> str:
        text = value.strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].rstrip() + "..."

    @staticmethod
    def _mask_secret(value: str) -> str:
        if not value:
            return "<empty>"
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    @staticmethod
    def _coalesce(*values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _unwrap_error_detail(exc: Exception) -> Any:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict) and "detail" in detail:
            return detail.get("detail")
        return detail or str(exc)


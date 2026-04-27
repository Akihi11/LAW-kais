from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings
from app.exceptions import (
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
    TaskNodeState,
    TaskNodeStatus,
    TaskRecord,
    TaskStatus,
    WorkflowExecutionStatus,
    WorkflowGroupState,
    WorkflowNodeState,
    get_stage_label,
)
from app.utils.document_parser import DocumentParser
from app.utils.logger import get_logger
from app.utils.workflow_display import sort_task_nodes_for_display


logger = get_logger(__name__)


class TencentYuanqiAsyncProvider(BaseProvider):
    """Tencent Cloud workflow async provider using the official LKE workflow APIs."""

    name = ProviderName.TENCENT_YUANQI_ASYNC

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._document_parser = DocumentParser(self.name)
        self._client = httpx.AsyncClient(timeout=settings.yuanqi_request_timeout_seconds)

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()

    async def create_review(self, request: ProviderCreateReviewRequest) -> ProviderTaskHandle:
        self._ensure_minimum_configured(request)

        document_text = await asyncio.to_thread(self._document_parser.extract_text, request.file_info)
        visitor_id = request.visitor_biz_id or self._settings.yuanqi_default_visitor_biz_id
        payload = {
            "AppBizId": self._app_biz_id,
            "RunEnv": self._settings.yuanqi_async_run_env,
            "Query": self._build_query(request),
            "CustomVariables": self._build_custom_variables(request, document_text),
            "VisitorId": visitor_id,
        }
        preview = {
            "provider": self.name.value,
            "endpoint": self._settings.yuanqi_async_endpoint,
            "action": "CreateWorkflowRun",
            "appBizId": self._app_biz_id,
            "runEnv": self._settings.yuanqi_async_run_env,
            "visitorId": visitor_id,
            "query": payload["Query"],
            "customVariables": [
                {
                    "name": item["Name"],
                    "valueType": type(item["Value"]).__name__,
                    "valueLength": len(str(item["Value"])),
                }
                for item in payload["CustomVariables"]
            ],
        }

        response_payload, request_id = await self._call_action("CreateWorkflowRun", payload)
        workflow_run_id = self._stringify(response_payload.get("WorkflowRunId"))
        if not workflow_run_id:
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "action": "CreateWorkflowRun",
                    "reason": "missing_workflow_run_id",
                    "response": self._sanitize_for_logging(response_payload),
                },
            )

        logger.info(
            "Tencent workflow create accepted x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s",
            "CreateWorkflowRun",
            self._app_biz_id,
            workflow_run_id,
            request_id,
            None,
            0,
        )

        return ProviderTaskHandle(
            provider_task_id=workflow_run_id,
            raw_request=preview,
            raw_response={"Response": response_payload, "RequestId": request_id},
            request_id=request_id,
            visitor_biz_id=visitor_id,
            app_id=self._app_biz_id,
            business_id=self._app_biz_id,
            message="Workflow created; waiting for async execution.",
        )

    def _ensure_minimum_configured(self, request: ProviderCreateReviewRequest) -> None:
        missing: list[str] = []
        if not self._settings.yuanqi_async_endpoint:
            missing.append("YUANQI_ASYNC_ENDPOINT")
        if not self._settings.yuanqi_tc_secret_id:
            missing.append("YUANQI_TC_SECRET_ID")
        if not self._settings.yuanqi_tc_secret_key:
            missing.append("YUANQI_TC_SECRET_KEY")
        if not self._app_biz_id:
            missing.append("YUANQI_APP_BIZ_ID")
        if not request.review_role.value:
            missing.append("review_role")

        if missing:
            raise ProviderNotConfiguredError(self.name.value, detail={"missing": missing})

        self._ensure_valid_http_url(self._settings.yuanqi_async_endpoint, "YUANQI_ASYNC_ENDPOINT")

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
    def _app_biz_id(self) -> str:
        return self._settings.yuanqi_app_biz_id or self._settings.yuanqi_app_id

    async def get_status(self, task: TaskRecord) -> ProviderStatus:
        snapshot = await self._fetch_workflow_snapshot(task)
        workflow_run = snapshot["workflow_run"]
        nodes = snapshot["nodes"]
        status = self._map_workflow_status(workflow_run.get("State"))
        current_node = self._pick_current_node(nodes)
        error_message = self._build_error_message(workflow_run, nodes)

        logger.info(
            "Tencent workflow status mapped x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s mapped_status=%s",
            "DescribeWorkflowRun",
            self._task_app_biz_id(task),
            task.provider_task_id,
            snapshot["request_id"],
            workflow_run.get("State"),
            len(snapshot["node_runs"]),
            status.value,
        )

        return ProviderStatus(
            status=status,
            current_stage=self._map_stage(status),
            current_stage_label=self._build_current_stage_label(status, workflow_run, current_node),
            progress=self._calculate_progress(status, nodes),
            error_message=error_message,
            request_id=snapshot["request_id"],
            visitor_biz_id=task.visitor_biz_id,
            nodes=nodes,
            workflow_groups=snapshot["workflow_groups"],
            raw=snapshot["raw"],
            message=self._build_status_message(status, current_node, error_message),
        )

    async def get_result(self, task: TaskRecord) -> ProviderResultPayload:
        snapshot = await self._fetch_workflow_snapshot(task)
        workflow_run = snapshot["workflow_run"]
        status = self._map_workflow_status(workflow_run.get("State"))
        if status != TaskStatus.SUCCEEDED:
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "taskId": task.task_id,
                    "workflowRunId": task.provider_task_id,
                    "status": status.value,
                    "workflowState": workflow_run.get("State"),
                },
            )

        nodes = snapshot["nodes"]
        workflow_groups = snapshot["workflow_groups"]
        extraction = await self._extract_final_result_payload(task, workflow_run, nodes)
        output_payload = extraction["payload"]
        if not isinstance(output_payload, dict) or not self._has_meaningful_result_payload(output_payload):
            logger.warning(
                "Tencent workflow result extraction failed workflow_run_id=%s final_state=%s found_terminal_node=%s found_final_result_field=%s result_source=%s reason=%s",
                task.provider_task_id,
                workflow_run.get("State"),
                extraction["found_terminal_node"],
                extraction["found_final_result_field"],
                extraction["source"],
                extraction["reason"],
            )
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "action": "GetWorkflowResult",
                    "workflowRunId": task.provider_task_id,
                    "reason": extraction["reason"],
                    "source": extraction["source"],
                    "foundTerminalNode": extraction["found_terminal_node"],
                    "foundFinalResultField": extraction["found_final_result_field"],
                },
            )

        steps = [
            {
                "name": node.node_name,
                "status": self._task_status_to_step_status(node.status),
            }
            for node in nodes
        ]

        output_payload["workflow"] = {"groups": [group.model_dump(mode="json") for group in workflow_groups]}
        output_payload["steps"] = steps
        output_payload.setdefault("workflowRun", workflow_run)
        output_payload.setdefault("nodeRuns", [node.model_dump(mode="json") for node in nodes])
        if snapshot["graph"] is not None:
            output_payload.setdefault("workflowGraph", snapshot["graph"])
        if not self._stringify(output_payload.get("reportText")):
            output_payload["reportText"] = extraction.get("report_text") or self._extract_text_from_output(output_payload)

        document_text = await asyncio.to_thread(self._document_parser.extract_text, task.file_info)
        output_payload["_source_document_text"] = document_text
        output_payload["_source_file_name"] = task.file_info.original_filename

        usage = {
            "provider": self.name.value,
            "requestId": snapshot["request_id"],
            "workflowRunId": task.provider_task_id,
            "state": workflow_run.get("State"),
            "runEnv": workflow_run.get("RunEnv"),
            "resultSource": extraction["source"],
            "resultNodeRunId": extraction.get("node_run_id"),
            "resultNodeName": extraction.get("node_name"),
            "foundTerminalNode": extraction["found_terminal_node"],
            "foundFinalResultField": extraction["found_final_result_field"],
            "resultExtractionReason": extraction["reason"],
        }

        logger.info(
            "Tencent workflow result extracted workflow_run_id=%s final_state=%s found_terminal_node=%s found_final_result_field=%s result_source=%s result_node=%s",
            task.provider_task_id,
            workflow_run.get("State"),
            extraction["found_terminal_node"],
            extraction["found_final_result_field"],
            extraction["source"],
            extraction.get("node_name"),
        )
        return ProviderResultPayload(raw=output_payload, usage=usage, steps=steps)

    async def list_workflow_runs(self, *, page_number: int = 1, page_size: int = 20) -> tuple[dict[str, Any], str | None]:
        payload = {
            "AppBizId": self._app_biz_id,
            "PageNumber": page_number,
            "PageSize": page_size,
        }
        return await self._call_action("ListWorkflowRuns", payload)

    async def stop_workflow_run(self, workflow_run_id: str) -> tuple[dict[str, Any], str | None]:
        payload = {
            "AppBizId": self._app_biz_id,
            "WorkflowRunId": workflow_run_id,
        }
        return await self._call_action("StopWorkflowRun", payload)

    async def _fetch_workflow_snapshot(self, task: TaskRecord) -> dict[str, Any]:
        describe_payload: dict[str, Any] = {
            "AppBizId": self._task_app_biz_id(task),
            "WorkflowRunId": task.provider_task_id,
        }
        if self._settings.yuanqi_async_include_workflow_graph:
            describe_payload["IncludeWorkflowGraph"] = True

        describe_response, request_id = await self._call_action(
            "DescribeWorkflowRun",
            describe_payload,
            workflow_run_id=task.provider_task_id,
        )
        workflow_run = describe_response.get("WorkflowRun") or {}
        if not isinstance(workflow_run, dict):
            workflow_run = {}
        node_runs = describe_response.get("NodeRuns") or []
        if not isinstance(node_runs, list):
            node_runs = []
        graph = self._extract_workflow_graph(workflow_run)

        raw_node_responses: list[dict[str, Any]] = []
        detailed_nodes: list[TaskNodeState] = []
        if self._settings.yuanqi_async_poll_node_details and node_runs:
            detailed_nodes, raw_node_responses = await self._describe_node_runs(task, node_runs)
        if not detailed_nodes:
            detailed_nodes = [self._map_node_state(node, node) for node in node_runs if isinstance(node, dict)]

        ordered_nodes = self._order_nodes(detailed_nodes, graph)
        display_nodes = sort_task_nodes_for_display(ordered_nodes)
        display_order_by_node_id = {
            node.node_id: node.display_order
            for node in display_nodes
            if node.display_order is not None
        }
        ordered_nodes = [
            node.model_copy(update={"display_order": display_order_by_node_id.get(node.node_id)})
            for node in ordered_nodes
        ]
        workflow_groups = self._build_workflow_groups(workflow_run, ordered_nodes, graph)
        raw = {
            "describeWorkflowRun": {"RequestId": request_id, "Response": describe_response},
            "describeNodeRuns": raw_node_responses,
            "workflowRun": workflow_run,
            "nodeRuns": node_runs,
            "nodeDetails": [node.model_dump(mode="json") for node in ordered_nodes],
            "workflowGraph": graph,
        }
        return {
            "request_id": request_id,
            "workflow_run": workflow_run,
            "node_runs": node_runs,
            "nodes": ordered_nodes,
            "workflow_groups": workflow_groups,
            "graph": graph,
            "raw": raw,
        }

    async def _describe_node_runs(self, task: TaskRecord, node_runs: list[Any]) -> tuple[list[TaskNodeState], list[dict[str, Any]]]:
        coroutines = []
        for base_node in node_runs:
            if not isinstance(base_node, dict):
                continue
            node_run_id = self._coalesce(base_node.get("NodeRunId"), base_node.get("NodeRunID"), base_node.get("Id"))
            if not node_run_id:
                continue
            coroutines.append(self._describe_single_node(task, node_run_id, base_node))

        if not coroutines:
            return [], []

        results = await asyncio.gather(*coroutines, return_exceptions=True)
        nodes: list[TaskNodeState] = []
        raw_node_responses: list[dict[str, Any]] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            node = result.get("node")
            if isinstance(node, TaskNodeState):
                nodes.append(node)
            raw_response = result.get("raw_response")
            if isinstance(raw_response, dict):
                raw_node_responses.append(raw_response)
        return nodes, raw_node_responses

    async def _describe_single_node(
        self,
        task: TaskRecord,
        node_run_id: str,
        base_node: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "AppBizId": self._task_app_biz_id(task),
            "NodeRunId": node_run_id,
        }
        sub_workflow_node_path = base_node.get("SubWorkflowNodePath")
        if isinstance(sub_workflow_node_path, list) and sub_workflow_node_path:
            payload["SubWorkflowNodePath"] = sub_workflow_node_path

        node_name = self._coalesce(base_node.get("NodeName"), base_node.get("Name")) or "unknown-node"
        logger.info(
            "DescribeNodeRun request workflow_run_id=%s node_run_id=%s node_name=%s request_body=%s",
            task.provider_task_id,
            node_run_id,
            node_name,
            self._sanitize_for_logging(payload),
        )

        try:
            response_payload, request_id = await self._call_action(
                "DescribeNodeRun",
                payload,
                workflow_run_id=task.provider_task_id,
            )
        except ProviderRequestFailedError as exc:
            detail = self._sanitize_for_logging(getattr(exc, "detail", None))
            logger.warning(
                "DescribeNodeRun failed workflow_run_id=%s node_run_id=%s node_name=%s error_type=api_parameter_or_request detail=%s",
                task.provider_task_id,
                node_run_id,
                node_name,
                detail,
            )
            return {
                "node": self._map_node_state(base_node, base_node),
                "raw_response": {
                    "NodeRunId": node_run_id,
                    "NodeName": node_name,
                    "Error": detail,
                },
            }

        node_detail = response_payload.get("NodeRun") or base_node
        if not isinstance(node_detail, dict):
            node_detail = dict(base_node)
        else:
            node_detail = dict(node_detail)

        await self._hydrate_node_output_from_refs(node_detail, node_run_id=node_run_id)
        output_candidate = self._first_non_empty(node_detail.get("TaskOutput"), node_detail.get("Output"))
        logger.info(
            "DescribeNodeRun response workflow_run_id=%s node_run_id=%s node_name=%s top_keys=%s output_empty=%s",
            task.provider_task_id,
            node_run_id,
            self._coalesce(node_detail.get("NodeName"), node_detail.get("Name"), base_node.get("NodeName"), base_node.get("Name")) or "unknown-node",
            list(response_payload.keys()),
            output_candidate in (None, "", {}, []),
        )
        return {
            "node": self._map_node_state(base_node, node_detail),
            "raw_response": {
                "NodeRunId": node_run_id,
                "NodeName": self._coalesce(node_detail.get("NodeName"), node_detail.get("Name"), node_name) or node_name,
                "RequestId": request_id,
                "Response": response_payload,
            },
        }

    async def _hydrate_node_output_from_refs(self, node_detail: dict[str, Any], *, node_run_id: str) -> None:
        if self._first_non_empty(node_detail.get("TaskOutput"), node_detail.get("Output")) not in (None, "", {}, []):
            return

        for ref_key, output_key in (("TaskOutputRef", "TaskOutput"), ("OutputRef", "Output")):
            ref = self._stringify(node_detail.get(ref_key))
            if not ref:
                continue
            text = await self._fetch_reference_text(ref, node_run_id=node_run_id, ref_key=ref_key)
            if text:
                node_detail[output_key] = text
                return

    async def _fetch_reference_text(self, url: str, *, node_run_id: str, ref_key: str) -> str | None:
        try:
            response = await self._client.get(url)
        except httpx.RequestError as exc:
            logger.warning(
                "DescribeNodeRun output ref request failed node_run_id=%s ref_key=%s error_type=request_error detail=%s",
                node_run_id,
                ref_key,
                str(exc),
            )
            return None

        if response.status_code >= 400:
            logger.warning(
                "DescribeNodeRun output ref request failed node_run_id=%s ref_key=%s error_type=bad_status status_code=%s",
                node_run_id,
                ref_key,
                response.status_code,
            )
            return None

        text = response.text.strip()
        logger.info(
            "DescribeNodeRun output ref loaded node_run_id=%s ref_key=%s content_length=%s",
            node_run_id,
            ref_key,
            len(text),
        )
        return text or None

    async def _call_action(
        self,
        action: str,
        payload: dict[str, Any],
        workflow_run_id: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        self._ensure_valid_http_url(self._settings.yuanqi_async_endpoint, "YUANQI_ASYNC_ENDPOINT")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        timestamp = int(time.time())
        headers = self._build_tc3_headers(action=action, body=body, timestamp=timestamp)
        app_biz_id = self._stringify(payload.get("AppBizId"))
        run_id = workflow_run_id or self._stringify(payload.get("WorkflowRunId")) or None

        try:
            response = await self._client.post(
                self._settings.yuanqi_async_endpoint,
                content=body.encode("utf-8"),
                headers=headers,
            )
        except httpx.RequestError as exc:
            logger.warning(
                "Tencent workflow request failed x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s error=%s",
                action,
                app_biz_id,
                run_id,
                None,
                None,
                0,
                str(exc),
            )
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "action": action,
                    "endpoint": self._settings.yuanqi_async_endpoint,
                    "reason": str(exc),
                },
            ) from exc

        try:
            payload_json = response.json()
        except ValueError as exc:
            response_text = response.text[:800]
            logger.warning(
                "Tencent workflow invalid json x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s status_code=%s response=%s",
                action,
                app_biz_id,
                run_id,
                None,
                None,
                0,
                response.status_code,
                self._sanitize_for_logging(response_text),
            )
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "action": action,
                    "statusCode": response.status_code,
                    "responseText": response_text,
                },
            ) from exc

        if not isinstance(payload_json, dict) or not isinstance(payload_json.get("Response"), dict):
            logger.warning(
                "Tencent workflow invalid envelope x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s status_code=%s response=%s",
                action,
                app_biz_id,
                run_id,
                None,
                None,
                0,
                response.status_code,
                self._sanitize_for_logging(payload_json),
            )
            raise ProviderResponseInvalidError(
                self.name.value,
                detail={
                    "action": action,
                    "statusCode": response.status_code,
                    "payload": self._sanitize_for_logging(payload_json),
                },
            )

        response_body = payload_json["Response"]
        request_id = self._stringify(response_body.get("RequestId")) or None
        workflow_run = response_body.get("WorkflowRun")
        node_run = response_body.get("NodeRun")
        node_runs = response_body.get("NodeRuns")
        node_runs_count = len(node_runs) if isinstance(node_runs, list) else 0
        state_value = None
        if isinstance(workflow_run, dict):
            state_value = workflow_run.get("State")
        elif isinstance(node_run, dict):
            state_value = node_run.get("State")

        error = response_body.get("Error")
        if isinstance(error, dict):
            sanitized_error_response = self._sanitize_for_logging(response_body)
            logger.warning(
                "Tencent workflow upstream error x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s status_code=%s response=%s",
                action,
                app_biz_id,
                run_id,
                request_id,
                state_value,
                node_runs_count,
                response.status_code,
                sanitized_error_response,
            )
            detail = {
                "action": action,
                "requestId": request_id,
                "code": error.get("Code"),
                "message": error.get("Message"),
                "response": sanitized_error_response,
            }
            if response.status_code in {401, 403} or str(error.get("Code", "")).lower().startswith("auth"):
                raise ProviderAuthFailedError(self.name.value, detail=detail)
            raise ProviderRequestFailedError(self.name.value, detail=detail)

        if response.status_code >= 400:
            sanitized_error_response = self._sanitize_for_logging(response_body)
            logger.warning(
                "Tencent workflow bad status x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s status_code=%s response=%s",
                action,
                app_biz_id,
                run_id,
                request_id,
                state_value,
                node_runs_count,
                response.status_code,
                sanitized_error_response,
            )
            raise ProviderRequestFailedError(
                self.name.value,
                detail={
                    "action": action,
                    "statusCode": response.status_code,
                    "requestId": request_id,
                    "response": sanitized_error_response,
                },
            )

        logger.info(
            "Tencent workflow action succeeded x_tc_action=%s app_biz_id=%s workflow_run_id=%s request_id=%s state=%s node_runs=%s",
            action,
            app_biz_id,
            run_id or self._stringify(response_body.get("WorkflowRunId")) or None,
            request_id,
            state_value,
            node_runs_count,
        )
        return response_body, request_id

    def _build_tc3_headers(self, *, action: str, body: str, timestamp: int) -> dict[str, str]:
        secret_id = self._settings.yuanqi_tc_secret_id
        secret_key = self._settings.yuanqi_tc_secret_key
        host = httpx.URL(self._settings.yuanqi_async_endpoint).host
        if not host:
            raise ProviderInvalidUrlError(self.name.value, detail={"field": "YUANQI_ASYNC_ENDPOINT"})

        date = datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")
        canonical_headers = (
            "content-type:application/json; charset=utf-8\n"
            f"host:{host}\n"
            f"x-tc-action:{action.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()
        canonical_request = "\n".join(
            [
                "POST",
                "/",
                "",
                canonical_headers,
                signed_headers,
                hashed_request_payload,
            ]
        )
        credential_scope = f"{date}/{self._settings.yuanqi_async_service}/tc3_request"
        string_to_sign = "\n".join(
            [
                "TC3-HMAC-SHA256",
                str(timestamp),
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        secret_date = hmac.new(("TC3" + secret_key).encode("utf-8"), date.encode("utf-8"), hashlib.sha256).digest()
        secret_service = hmac.new(secret_date, self._settings.yuanqi_async_service.encode("utf-8"), hashlib.sha256).digest()
        secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            "TC3-HMAC-SHA256 "
            f"Credential={secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Version": self._settings.yuanqi_async_version,
            "X-TC-Region": self._settings.yuanqi_async_region,
            "X-TC-Timestamp": str(timestamp),
        }

    def _build_query(self, request: ProviderCreateReviewRequest) -> str:
        return f"Review contract {request.file_info.original_filename} from the {request.review_role.value} perspective."

    def _build_custom_variables(self, request: ProviderCreateReviewRequest, document_text: str) -> list[dict[str, str]]:
        return [
            {"Name": "contract_text", "Value": document_text},
            {"Name": "review_role", "Value": request.review_role.value},
            {"Name": "file_name", "Value": request.file_info.original_filename},
        ]

    def _extract_workflow_graph(self, workflow_run: dict[str, Any]) -> Any:
        graph = workflow_run.get("WorkflowGraph")
        if isinstance(graph, str):
            return self._maybe_parse_json(graph)
        return graph

    def _map_workflow_status(self, value: Any) -> TaskStatus:
        try:
            state = int(value)
        except (TypeError, ValueError):
            return TaskStatus.RUNNING
        if state == 0:
            return TaskStatus.QUEUED
        if state == 1:
            return TaskStatus.RUNNING
        if state == 2:
            return TaskStatus.SUCCEEDED
        return TaskStatus.FAILED

    def _map_node_state(self, base_node: dict[str, Any], detail_node: dict[str, Any]) -> TaskNodeState:
        status = self._map_node_status(detail_node.get("State", base_node.get("State")))
        finished_at = self._parse_datetime(
            self._coalesce(
                detail_node.get("FinishedAt"),
                detail_node.get("UpdatedAt"),
                detail_node.get("EndTime"),
                base_node.get("FinishedAt"),
                base_node.get("UpdatedAt"),
                base_node.get("EndTime"),
            )
        )
        if status not in {TaskNodeStatus.SUCCESS, TaskNodeStatus.FAILED}:
            finished_at = None

        return TaskNodeState(
            node_id=self._coalesce(
                detail_node.get("NodeRunId"),
                base_node.get("NodeRunId"),
                detail_node.get("NodeId"),
                base_node.get("NodeId"),
                detail_node.get("Id"),
                base_node.get("Id"),
            )
            or self._stringify(detail_node.get("NodeName"))
            or self._stringify(base_node.get("NodeName"))
            or "unknown-node",
            node_name=self._coalesce(
                detail_node.get("NodeName"),
                base_node.get("NodeName"),
                detail_node.get("Name"),
                base_node.get("Name"),
            )
            or "unknown-node",
            status=status,
            started_at=self._parse_datetime(
                self._coalesce(
                    detail_node.get("StartedAt"),
                    detail_node.get("CreatedAt"),
                    detail_node.get("StartTime"),
                    base_node.get("StartedAt"),
                    base_node.get("CreatedAt"),
                    base_node.get("StartTime"),
                )
            ),
            finished_at=finished_at,
            input=self._normalize_payload_value(
                self._first_non_empty(
                    detail_node.get("Input"),
                    detail_node.get("TaskInput"),
                    base_node.get("Input"),
                    base_node.get("TaskInput"),
                )
            ),
            output=self._normalize_payload_value(
                self._first_non_empty(
                    detail_node.get("Output"),
                    detail_node.get("TaskOutput"),
                    base_node.get("Output"),
                    base_node.get("TaskOutput"),
                )
            ),
            error=self._coalesce(
                detail_node.get("FailMessage"),
                detail_node.get("ErrorMessage"),
                base_node.get("FailMessage"),
                base_node.get("ErrorMessage"),
            )
            or None,
            node_type=self._stringify(self._first_non_empty(detail_node.get("NodeType"), base_node.get("NodeType"))) or None,
            raw=detail_node,
        )

    def _map_node_status(self, value: Any) -> TaskNodeStatus:
        try:
            state = int(value)
        except (TypeError, ValueError):
            text = self._stringify(value).lower()
            if any(token in text for token in ("success", "done", "finish", "complete")):
                return TaskNodeStatus.SUCCESS
            if any(token in text for token in ("fail", "error", "cancel")):
                return TaskNodeStatus.FAILED
            if any(token in text for token in ("run", "process", "execut")):
                return TaskNodeStatus.RUNNING
            return TaskNodeStatus.WAITING

        if state == 0:
            return TaskNodeStatus.WAITING
        if state == 1:
            return TaskNodeStatus.RUNNING
        if state == 2:
            return TaskNodeStatus.SUCCESS
        return TaskNodeStatus.FAILED

    def _build_workflow_groups(
        self,
        workflow_run: dict[str, Any],
        nodes: list[TaskNodeState],
        graph: Any,
    ) -> list[WorkflowGroupState]:
        workflow_name = self._extract_workflow_name(workflow_run, graph)
        display_nodes = sort_task_nodes_for_display(nodes)
        workflow_nodes = [
            WorkflowNodeState(
                name=node.node_name,
                status=self._task_node_to_workflow_status(node.status),
                display_order=node.display_order,
            )
            for node in display_nodes
        ]
        group_status = self._derive_group_status(nodes, workflow_nodes)
        return [WorkflowGroupState(name=workflow_name, status=group_status, nodes=workflow_nodes)]

    def _derive_group_status(
        self,
        nodes: list[TaskNodeState],
        workflow_nodes: list[WorkflowNodeState],
    ) -> WorkflowExecutionStatus:
        node_statuses = {node.status for node in nodes}
        workflow_statuses = {node.status for node in workflow_nodes}
        if TaskNodeStatus.FAILED in node_statuses or WorkflowExecutionStatus.FAILED in workflow_statuses:
            return WorkflowExecutionStatus.FAILED
        if TaskNodeStatus.RUNNING in node_statuses or WorkflowExecutionStatus.RUNNING in workflow_statuses:
            return WorkflowExecutionStatus.RUNNING
        if nodes and node_statuses.issubset({TaskNodeStatus.SUCCESS}):
            return WorkflowExecutionStatus.DONE
        if workflow_nodes and workflow_statuses.issubset({WorkflowExecutionStatus.DONE}):
            return WorkflowExecutionStatus.DONE
        return WorkflowExecutionStatus.PENDING

    def _task_node_to_workflow_status(self, status: TaskNodeStatus) -> WorkflowExecutionStatus:
        if status == TaskNodeStatus.SUCCESS:
            return WorkflowExecutionStatus.DONE
        if status == TaskNodeStatus.RUNNING:
            return WorkflowExecutionStatus.RUNNING
        if status == TaskNodeStatus.FAILED:
            return WorkflowExecutionStatus.FAILED
        return WorkflowExecutionStatus.PENDING

    def _map_stage(self, status: TaskStatus) -> StageCode:
        if status == TaskStatus.SUCCEEDED:
            return StageCode.COMPLETED
        if status == TaskStatus.QUEUED:
            return StageCode.PARSING
        return StageCode.REVIEWING

    def _build_current_stage_label(
        self,
        status: TaskStatus,
        workflow_run: dict[str, Any],
        current_node: TaskNodeState | None,
    ) -> str:
        workflow_name = self._extract_workflow_name(workflow_run, self._extract_workflow_graph(workflow_run))
        if status == TaskStatus.QUEUED:
            return "Workflow queued"
        if status == TaskStatus.RUNNING and current_node is not None:
            return f"{workflow_name} running: {current_node.node_name}"
        if status == TaskStatus.SUCCEEDED:
            return f"{workflow_name} completed"
        if status == TaskStatus.FAILED and current_node is not None:
            return f"{workflow_name} failed: {current_node.node_name}"
        if status == TaskStatus.FAILED:
            return "Workflow failed"
        return get_stage_label(self._map_stage(status))

    def _calculate_progress(self, status: TaskStatus, nodes: list[TaskNodeState]) -> int:
        if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
            return 100
        if not nodes:
            return 10 if status == TaskStatus.QUEUED else 45

        total = len(nodes)
        completed = 0.0
        for node in nodes:
            if node.status in {TaskNodeStatus.SUCCESS, TaskNodeStatus.FAILED}:
                completed += 1.0
            elif node.status == TaskNodeStatus.RUNNING:
                completed += 0.5
        return max(5, min(99, int((completed / total) * 100)))

    def _build_error_message(self, workflow_run: dict[str, Any], nodes: list[TaskNodeState]) -> str | None:
        if self._map_workflow_status(workflow_run.get("State")) != TaskStatus.FAILED:
            return None
        for node in nodes:
            if node.status == TaskNodeStatus.FAILED and node.error:
                return node.error
        return self._coalesce(workflow_run.get("FailMessage"), workflow_run.get("ErrorMessage")) or None

    def _build_status_message(
        self,
        status: TaskStatus,
        current_node: TaskNodeState | None,
        error_message: str | None,
    ) -> str:
        if status == TaskStatus.QUEUED:
            return "Workflow queued"
        if status == TaskStatus.RUNNING:
            if current_node is not None:
                return f"Workflow running: {current_node.node_name}"
            return "Workflow running"
        if status == TaskStatus.SUCCEEDED:
            return "Workflow completed"
        if status == TaskStatus.FAILED:
            return error_message or "Workflow failed"
        return get_stage_label(self._map_stage(status))

    async def _extract_final_result_payload(
        self,
        task: TaskRecord,
        workflow_run: dict[str, Any],
        nodes: list[TaskNodeState],
    ) -> dict[str, Any]:
        workflow_candidate = self._build_result_candidate(
            workflow_run.get("Output"),
            workflow_run.get("TaskOutput"),
            self._extract_latest_message(workflow_run.get("LatestMessage")),
        )
        node_candidates = [self._build_node_result_candidate(node, index) for index, node in enumerate(self._sort_nodes_for_execution(nodes))]
        terminal_candidate = self._select_terminal_result_candidate(node_candidates)

        merged_payload: dict[str, Any] = {}
        if workflow_candidate["payload"]:
            merged_payload = self._merge_result_payloads(merged_payload, workflow_candidate["payload"])

        if terminal_candidate and terminal_candidate["payload"]:
            merged_payload = self._merge_result_payloads(merged_payload, terminal_candidate["payload"])

        for candidate in node_candidates:
            if not candidate["payload"]:
                continue
            merged_payload = self._merge_result_payloads(merged_payload, candidate["payload"])

        report_text = (
            terminal_candidate.get("report_text")
            if terminal_candidate and terminal_candidate.get("report_text")
            else workflow_candidate.get("report_text")
        )
        if not report_text:
            for candidate in node_candidates:
                if candidate.get("report_text"):
                    report_text = candidate["report_text"]
                    break

        final_report = self._stringify(merged_payload.get("final_review_report") or merged_payload.get("finalReviewReport"))
        if not final_report and report_text:
            merged_payload["final_review_report"] = report_text
            final_report = report_text

        found_final_field = self._has_meaningful_result_payload(merged_payload)
        source = "assembled"
        if workflow_candidate["has_signal"]:
            source = "workflow"
        if terminal_candidate and terminal_candidate["has_signal"] and final_report:
            source = "node"
        elif terminal_candidate and terminal_candidate["has_signal"] and not workflow_candidate["has_signal"]:
            source = "node"

        reason = "ok" if found_final_field else "missing_final_result_fields"
        logger.info(
            "Tencent workflow final result scan workflow_run_id=%s final_state=%s found_terminal_node=%s found_final_result_field=%s result_source=%s workflow_candidate_score=%s node_candidate_count=%s",
            task.provider_task_id,
            workflow_run.get("State"),
            terminal_candidate is not None,
            found_final_field,
            source,
            workflow_candidate["score"],
            len(node_candidates),
        )
        return {
            "payload": merged_payload,
            "report_text": report_text,
            "source": source,
            "reason": reason,
            "found_terminal_node": terminal_candidate is not None,
            "found_final_result_field": found_final_field,
            "node_run_id": terminal_candidate.get("node_run_id") if terminal_candidate else None,
            "node_name": terminal_candidate.get("node_name") if terminal_candidate else None,
        }

    def _build_result_candidate(self, *values: Any) -> dict[str, Any]:
        best_payload: dict[str, Any] = {}
        best_payload_score = -1
        best_report_text: str | None = None

        for value in values:
            normalized = self._normalize_result_value(value)
            if normalized in (None, "", {}, []):
                continue

            if isinstance(normalized, dict):
                score = self._score_result_payload(normalized)
                if score > best_payload_score:
                    best_payload = normalized
                    best_payload_score = score
                report_text = self._extract_report_markdown(normalized)
                if report_text and (best_report_text is None or len(report_text) > len(best_report_text)):
                    best_report_text = report_text
                continue

            if isinstance(normalized, str):
                if best_report_text is None or len(normalized) > len(best_report_text):
                    best_report_text = normalized

        return {
            "payload": best_payload,
            "report_text": best_report_text,
            "score": max(best_payload_score, 1 if best_report_text else 0),
            "has_signal": best_payload_score > 0 or bool(best_report_text),
        }

    def _build_node_result_candidate(self, node: TaskNodeState, index: int) -> dict[str, Any]:
        candidate = self._build_result_candidate(
            node.output,
            node.raw.get("TaskOutput") if isinstance(node.raw, dict) else None,
            node.raw.get("Output") if isinstance(node.raw, dict) else None,
            node.raw.get("LatestMessage") if isinstance(node.raw, dict) else None,
        )
        candidate["node"] = node
        candidate["node_run_id"] = node.node_id
        candidate["node_name"] = node.node_name
        candidate["sort_index"] = index
        candidate["is_terminal"] = self._looks_like_terminal_result_node(node)
        if candidate["is_terminal"]:
            candidate["score"] += 4
            candidate["has_signal"] = candidate["has_signal"] or candidate["score"] > 0
        return candidate

    def _select_terminal_result_candidate(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        terminal_candidates = [candidate for candidate in candidates if candidate.get("is_terminal") and candidate.get("has_signal")]
        if terminal_candidates:
            return max(terminal_candidates, key=lambda item: (item.get("score", 0), item.get("sort_index", 0)))

        signal_candidates = [candidate for candidate in candidates if candidate.get("has_signal")]
        if signal_candidates:
            return max(signal_candidates, key=lambda item: (item.get("score", 0), item.get("sort_index", 0)))
        return None

    def _looks_like_terminal_result_node(self, node: TaskNodeState) -> bool:
        node_name = self._stringify(node.node_name).lower()
        node_type = self._stringify(node.node_type).lower()
        terminal_keywords = ("\u7ed3\u675f", "\u6c47\u603b", "\u603b\u7ed3", "\u62a5\u544a", "\u8f93\u51fa", "reply", "end", "summary", "report")
        if any(keyword in node_name for keyword in terminal_keywords):
            return True
        return node_type in {"10", "16", "reply", "end"}

    def _sort_nodes_for_execution(self, nodes: list[TaskNodeState]) -> list[TaskNodeState]:
        indexed_nodes = list(enumerate(nodes))
        indexed_nodes.sort(key=lambda item: (self._node_execution_sort_key(item[1]), item[0]))
        return [node for _, node in indexed_nodes]

    def _node_execution_sort_key(self, node: TaskNodeState) -> float:
        marker = node.started_at or node.finished_at
        if marker is None:
            return float("inf")
        return marker.timestamp()

    def _normalize_result_value(self, value: Any) -> dict[str, Any] | str | None:
        normalized = self._normalize_payload_value(value)
        if normalized in (None, "", {}, []):
            return None
        if isinstance(normalized, dict):
            return normalized
        if isinstance(normalized, list):
            return {"reportText": json.dumps(normalized, ensure_ascii=False)}
        if isinstance(normalized, str):
            parsed = self._maybe_parse_json(normalized)
            if isinstance(parsed, dict):
                return parsed
            return normalized
        return self._stringify(normalized) or None

    def _score_result_payload(self, payload: dict[str, Any]) -> int:
        score = 0
        if self._stringify(payload.get("final_review_report") or payload.get("finalReviewReport")):
            score += 8
        if self._stringify(payload.get("contract_type") or payload.get("contractType")):
            score += 3
        if self._stringify(payload.get("overall_conclusion") or payload.get("overallConclusion")):
            score += 4
        if self._stringify(payload.get("overall_risk_level") or payload.get("overallRiskLevel")):
            score += 3
        if isinstance(payload.get("clause_risk_stats"), dict):
            score += 4
        findings = payload.get("clause_ordered_findings")
        if isinstance(findings, list) and findings:
            score += 6
        report_material = payload.get("report_material")
        if isinstance(report_material, dict):
            score += 3
            if isinstance(report_material.get("clause_ordered_findings"), list) and report_material.get("clause_ordered_findings"):
                score += 4
            if self._stringify(report_material.get("overall_conclusion")):
                score += 2
            if self._stringify(report_material.get("overall_risk_level")):
                score += 2
        if self._extract_report_markdown(payload):
            score += 2
        return score

    def _has_meaningful_result_payload(self, payload: dict[str, Any]) -> bool:
        return self._score_result_payload(payload) > 0

    def _extract_report_markdown(self, payload: dict[str, Any]) -> str | None:
        candidate_keys = (
            "final_review_report",
            "finalReviewReport",
            "report_markdown",
            "reportMarkdown",
            "final_report",
            "fullReport",
            "report",
            "markdown",
            "analysis",
        )
        for key in candidate_keys:
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                parsed = self._maybe_parse_json(candidate)
                if isinstance(parsed, (dict, list)):
                    continue
                return candidate.strip()
        return None

    def _merge_result_payloads(self, base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        if not candidate:
            return dict(base)
        if not base:
            return dict(candidate)

        merged = dict(base)
        for key, value in candidate.items():
            if key not in merged or self._is_empty_value(merged[key]):
                merged[key] = value
                continue
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_result_payloads(merged[key], value)
        return merged

    def _is_empty_value(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0
        return False

    def _extract_text_from_output(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in (
                "final_review_report",
                "finalReviewReport",
                "report_markdown",
                "reportMarkdown",
                "fullReport",
                "reportText",
                "report",
                "summary",
                "conclusion",
                "analysis",
            ):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False)
        return self._stringify(value)

    def _extract_latest_message(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("Content", "content", "Text", "text", "Message", "message"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            contents = value.get("Contents") or value.get("contents")
            if isinstance(contents, list):
                parts: list[str] = []
                for item in contents:
                    if isinstance(item, dict):
                        for key in ("Text", "text", "Content", "content", "Value", "value"):
                            candidate = item.get(key)
                            if isinstance(candidate, str) and candidate.strip():
                                parts.append(candidate.strip())
                                break
                if parts:
                    return "\n".join(parts)
        return ""

    def _task_status_to_step_status(self, status: TaskNodeStatus) -> str:
        if status == TaskNodeStatus.SUCCESS:
            return "done"
        if status == TaskNodeStatus.RUNNING:
            return "running"
        if status == TaskNodeStatus.FAILED:
            return "failed"
        return "pending"

    def _extract_workflow_name(self, workflow_run: dict[str, Any], graph: Any) -> str:
        graph_name = ""
        if isinstance(graph, dict):
            graph_name = self._coalesce(
                graph.get("WorkflowName"),
                graph.get("Name"),
                (graph.get("Workflow") or {}).get("Name") if isinstance(graph.get("Workflow"), dict) else None,
            )
        return self._coalesce(workflow_run.get("WorkflowName"), graph_name) or "工作流"

    def _extract_graph_nodes(self, graph: Any) -> list[Any]:
        if not isinstance(graph, dict):
            return []
        for candidate in (
            graph.get("Nodes"),
            graph.get("nodes"),
            (graph.get("Workflow") or {}).get("Nodes") if isinstance(graph.get("Workflow"), dict) else None,
            (graph.get("workflow") or {}).get("nodes") if isinstance(graph.get("workflow"), dict) else None,
        ):
            if isinstance(candidate, list):
                return candidate
        return []

    def _pick_current_node(self, nodes: list[TaskNodeState]) -> TaskNodeState | None:
        for status in (TaskNodeStatus.RUNNING, TaskNodeStatus.FAILED, TaskNodeStatus.WAITING):
            for node in nodes:
                if node.status == status:
                    return node
        return nodes[-1] if nodes else None

    def _task_app_biz_id(self, task: TaskRecord) -> str:
        return self._stringify(task.business_id or task.app_id or self._app_biz_id)

    def _normalize_payload_value(self, value: Any) -> dict[str, Any] | list[Any] | str | None:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            parsed = self._maybe_parse_json(text)
            return parsed if isinstance(parsed, (dict, list)) else text
        return self._stringify(value)

    def _maybe_parse_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return ""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                timestamp = float(value)
                if timestamp > 10_000_000_000:
                    timestamp /= 1000
                return datetime.fromtimestamp(timestamp, UTC)
            except Exception:
                return None
        text = self._stringify(value)
        if not text:
            return None
        if text.isdigit():
            try:
                timestamp = float(text)
                if timestamp > 10_000_000_000:
                    timestamp /= 1000
                return datetime.fromtimestamp(timestamp, UTC)
            except Exception:
                return None
        try:
            if text.endswith("Z"):
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _order_nodes(self, nodes: list[TaskNodeState], graph: Any) -> list[TaskNodeState]:
        if not nodes:
            return []
        order_map: dict[str, int] = {}
        for index, item in enumerate(self._extract_graph_nodes(graph)):
            if not isinstance(item, dict):
                continue
            for key in ("NodeId", "Id", "NodeRunId", "NodeName", "Name"):
                value = self._stringify(item.get(key))
                if value:
                    order_map[value] = index
        return sorted(
            nodes,
            key=lambda node: (
                min((order_map.get(key, 10_000) for key in self._node_keys(node)), default=10_000),
                node.started_at or datetime.max.replace(tzinfo=UTC),
                node.node_name,
            ),
        )

    def _node_keys(self, node: TaskNodeState) -> list[str]:
        keys = [node.node_id, node.node_name]
        if isinstance(node.raw, dict):
            for key in ("NodeRunId", "NodeId", "Id", "NodeName", "Name"):
                value = self._stringify(node.raw.get(key))
                if value:
                    keys.append(value)
        return [key for key in keys if key]

    def _sanitize_for_logging(self, value: Any, *, _key: str | None = None) -> Any:
        key_name = (_key or "").lower()
        if isinstance(value, dict):
            return {key: self._sanitize_for_logging(item, _key=key) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_for_logging(item, _key=_key) for item in value[:20]]
        if isinstance(value, str):
            if any(token in key_name for token in ("secret", "authorization", "signature")):
                return "<redacted>"
            if key_name in {"query", "input", "output", "value", "content", "latestmessage"}:
                return f"<redacted len={len(value)}>"
            if len(value) > 512:
                return f"{value[:256]}...<truncated len={len(value)}>...{value[-128:]}"
            return value
        return value

    @staticmethod
    def _first_non_empty(*values: Any) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str):
                if value.strip():
                    return value
                continue
            return value
        return None

    @staticmethod
    def _coalesce(*values: Any) -> str:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
            if not isinstance(value, str):
                text = str(value).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()



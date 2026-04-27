from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from app.config import Settings
from app.exceptions import AppError, InvalidReviewRoleError, ProviderExecutionError, ResultNotReadyError, TaskFailedError
from app.providers.base import BaseProvider
from app.schemas.domain import ProviderCreateReviewRequest, ReviewRole, StageCode, TaskRecord, TaskStatus, get_stage_label
from app.schemas.request import CreateReviewRequest
from app.schemas.response import CreateReviewResponse, ReviewResultResponse, ReviewStatusResponse, TaskNodeResponse
from app.services.result_mapper import ResultMapper
from app.services.task_service import TaskService
from app.utils.file_storage import FileStorage
from app.utils.logger import get_logger
from app.utils.workflow_display import sort_task_nodes_for_display, sort_workflow_groups_for_display


logger = get_logger(__name__)


class ReviewService:
    def __init__(
        self,
        *,
        provider: BaseProvider,
        task_service: TaskService,
        file_storage: FileStorage,
        result_mapper: ResultMapper,
        settings: Settings,
    ) -> None:
        self.provider = provider
        self.task_service = task_service
        self.file_storage = file_storage
        self.result_mapper = result_mapper
        self.settings = settings

    async def create_review(self, file: UploadFile, review_role: str, visitor_biz_id: str | None = None) -> CreateReviewResponse:
        request_model = CreateReviewRequest(review_role=self._parse_review_role(review_role))
        resolved_visitor_id = self._resolve_visitor_biz_id(visitor_biz_id)
        task_id = self.task_service.generate_task_id()
        file_info = await self.file_storage.save_upload(task_id, file)
        public_file_url = self.file_storage.build_upload_public_url(file_info)

        logger.info(
            "Prepared review task taskId=%s provider=%s file=%s review_role=%s visitor_biz_id=%s public_file_url=%s",
            task_id,
            self.provider.name.value,
            file_info.original_filename,
            request_model.review_role.value,
            resolved_visitor_id,
            public_file_url,
        )

        try:
            provider_handle = await self.provider.create_review(
                ProviderCreateReviewRequest(
                    task_id=task_id,
                    review_role=request_model.review_role,
                    file_info=file_info,
                    public_file_url=public_file_url,
                    visitor_biz_id=resolved_visitor_id,
                )
            )
        except ProviderExecutionError:
            self.file_storage.delete_file(file_info.path)
            raise

        task = TaskRecord(
            task_id=task_id,
            provider_name=self.provider.name,
            provider_task_id=provider_handle.provider_task_id,
            review_role=request_model.review_role,
            file_info=file_info,
            status=TaskStatus.CREATED,
            current_stage=StageCode.UPLOADING,
            current_stage_label=get_stage_label(StageCode.UPLOADING),
            progress=0,
            request_id=provider_handle.request_id,
            visitor_biz_id=provider_handle.visitor_biz_id or resolved_visitor_id,
            app_id=provider_handle.app_id or self.settings.yuanqi_app_biz_id or self.settings.yuanqi_app_id,
            business_id=provider_handle.business_id or self.settings.yuanqi_app_biz_id or self.settings.yuanqi_app_id,
            file_id=file_info.stored_filename,
            document_id=file_info.stored_filename,
            provider_request=provider_handle.raw_request,
            provider_response=provider_handle.raw_response,
            raw_create_response=provider_handle.raw_response,
            metadata={"publicFileUrl": public_file_url},
        )
        await self.task_service.save_task(task)

        return CreateReviewResponse(
            success=True,
            provider=self.provider.name.value,
            taskId=task.task_id,
            requestId=task.request_id,
            status=TaskStatus.CREATED,
            message=provider_handle.message or "\u5de5\u4f5c\u6d41\u4efb\u52a1\u5df2\u521b\u5efa\u3002",
        )

    async def get_status(self, task_id: str) -> ReviewStatusResponse:
        task = await self._refresh_task(task_id)
        completed_at = self._resolve_completed_at(task)
        display_workflow_groups = sort_workflow_groups_for_display(task.workflow_groups or [])
        display_nodes = sort_task_nodes_for_display(task.node_states or [])
        return ReviewStatusResponse(
            success=True,
            provider=task.provider_name.value,
            taskId=task.task_id,
            requestId=task.request_id,
            visitorBizId=task.visitor_biz_id,
            status=task.status,
            currentStage=task.current_stage.value,
            currentStageLabel=task.current_stage_label,
            progress=task.progress,
            errorMessage=task.error_message,
            message=self._build_status_message(task),
            createdAt=task.created_at,
            updatedAt=task.updated_at,
            completedAt=completed_at,
            workflowGroups=display_workflow_groups,
            nodes=[self._map_task_node(node) for node in display_nodes],
            raw=task.raw_status_response,
        )

    async def get_result(self, task_id: str) -> ReviewResultResponse:
        task = await self._refresh_task(task_id)

        if task.status == TaskStatus.FAILED:
            provider_error = self._build_provider_error(task)
            if provider_error is not None:
                raise provider_error
            raise TaskFailedError(task.task_id, task.error_message)

        if task.status != TaskStatus.SUCCEEDED:
            raise ResultNotReadyError(task.task_id)

        task = await self._materialize_result(task, trigger="get_result")
        if task.result_payload is None:
            raise ResultNotReadyError(task.task_id)
        return self.result_mapper.map_result(task, task.result_payload)

    async def _refresh_task(self, task_id: str) -> TaskRecord:
        task = await self.task_service.get_task(task_id)

        if task.status == TaskStatus.FAILED and self._build_provider_error(task) is not None:
            return task

        if task.status == TaskStatus.SUCCEEDED and task.result_payload is not None:
            return await self._materialize_result(task, trigger="status_refresh_cached")

        try:
            provider_status = await self.provider.get_status(task)
        except ProviderExecutionError as exc:
            updated_metadata = dict(task.metadata)
            updated_metadata["provider_error"] = {
                "code": exc.code,
                "statusCode": exc.status_code,
                "message": exc.message,
                "detail": exc.detail,
            }
            failed_task = task.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "error_message": exc.message,
                    "metadata": updated_metadata,
                }
            )
            await self.task_service.update_task(failed_task)
            return failed_task

        updated_task = task.model_copy(
            update={
                "status": provider_status.status,
                "current_stage": provider_status.current_stage,
                "current_stage_label": provider_status.current_stage_label,
                "progress": provider_status.progress,
                "error_message": provider_status.error_message,
                "request_id": provider_status.request_id or task.request_id,
                "visitor_biz_id": provider_status.visitor_biz_id or task.visitor_biz_id,
                "node_states": provider_status.nodes,
                "workflow_groups": provider_status.workflow_groups,
                "provider_response": provider_status.raw or task.provider_response,
                "raw_status_response": provider_status.raw or task.raw_status_response,
            }
        )
        await self.task_service.update_task(updated_task)

        if updated_task.status == TaskStatus.SUCCEEDED:
            return await self._materialize_result(updated_task, trigger="status_refresh")
        return updated_task

    async def _materialize_result(self, task: TaskRecord, *, trigger: str) -> TaskRecord:
        if task.result_payload is not None:
            result_record = self.result_mapper.map_result(task, task.result_payload)
            raw_paths = self._persist_raw_result_artifacts(task, trigger=trigger)
            updated_metadata = dict(task.metadata)
            if raw_paths:
                updated_metadata["raw_result_artifacts"] = raw_paths

            if self._result_file_exists(task):
                if updated_metadata != task.metadata:
                    restored_task = task.model_copy(update={"metadata": updated_metadata})
                    await self.task_service.update_task(restored_task)
                    return restored_task
                return task

            try:
                result_path = self.file_storage.save_result(task.task_id, result_record)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception(
                    "Result file rewrite failed taskId=%s trigger=%s existing_payload=true error=%s",
                    task.task_id,
                    trigger,
                    str(exc),
                )
                return await self._update_result_extraction_state(
                    task,
                    status="failed",
                    trigger=trigger,
                    reason="result_file_write_failed",
                    extra={"error": str(exc)},
                )

            logger.info(
                "Result file restored taskId=%s trigger=%s result_path=%s raw_workflow_path=%s raw_nodes_path=%s",
                task.task_id,
                trigger,
                result_path,
                (raw_paths or {}).get("workflow"),
                (raw_paths or {}).get("nodes"),
            )
            restored_task = task.model_copy(update={"result_path": result_path, "metadata": updated_metadata})
            await self.task_service.update_task(restored_task)
            return restored_task

        try:
            provider_result = await self.provider.get_result(task)
        except ProviderExecutionError as exc:
            logger.warning(
                "Result extraction pending taskId=%s trigger=%s provider=%s workflow_run_id=%s code=%s detail=%s",
                task.task_id,
                trigger,
                task.provider_name.value,
                task.provider_task_id,
                exc.code,
                getattr(exc, "detail", None),
            )
            return await self._update_result_extraction_state(
                task,
                status="failed",
                trigger=trigger,
                reason="provider_result_extraction_failed",
                extra={
                    "code": exc.code,
                    "statusCode": exc.status_code,
                    "message": exc.message,
                    "detail": exc.detail,
                },
            )

        mapped_result = self.result_mapper.map_result(task, provider_result.raw)

        try:
            result_path = self.file_storage.save_result(task.task_id, mapped_result)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Result file write failed taskId=%s trigger=%s provider=%s workflow_run_id=%s error=%s",
                task.task_id,
                trigger,
                task.provider_name.value,
                task.provider_task_id,
                str(exc),
            )
            return await self._update_result_extraction_state(
                task,
                status="failed",
                trigger=trigger,
                reason="result_file_write_failed",
                extra={"error": str(exc)},
            )

        raw_source_task = task.model_copy(
            update={
                "raw_result_response": provider_result.raw if isinstance(provider_result.raw, dict) else task.raw_result_response,
            }
        )
        raw_paths = self._persist_raw_result_artifacts(raw_source_task, trigger=trigger)

        updated_metadata = dict(task.metadata)
        updated_metadata["provider_result_usage"] = provider_result.usage
        updated_metadata["provider_result_steps"] = provider_result.steps
        if raw_paths:
            updated_metadata["raw_result_artifacts"] = raw_paths
        updated_metadata["result_extraction"] = {
            "status": "succeeded",
            "trigger": trigger,
            "resultPath": result_path,
            "workflowRawPath": (raw_paths or {}).get("workflow"),
            "nodesRawPath": (raw_paths or {}).get("nodes"),
            **(provider_result.usage or {}),
        }

        logger.info(
            "Mapped review result taskId=%s provider=%s issues=%s manual_review=%s result_source=%s result_path=%s raw_workflow_path=%s raw_nodes_path=%s",
            task.task_id,
            task.provider_name.value,
            len(mapped_result.issues),
            mapped_result.need_manual_review,
            (provider_result.usage or {}).get("resultSource"),
            result_path,
            (raw_paths or {}).get("workflow"),
            (raw_paths or {}).get("nodes"),
        )

        updated_task = task.model_copy(
            update={
                "result_path": result_path,
                "result_payload": mapped_result.model_dump(mode="json"),
                "provider_response": provider_result.raw if isinstance(provider_result.raw, dict) else task.provider_response,
                "raw_result_response": provider_result.raw if isinstance(provider_result.raw, dict) else task.raw_result_response,
                "metadata": updated_metadata,
            }
        )
        await self.task_service.update_task(updated_task)
        return updated_task

    def _persist_raw_result_artifacts(self, task: TaskRecord, *, trigger: str) -> dict[str, str] | None:
        raw_source = task.raw_status_response if isinstance(task.raw_status_response, dict) else None
        if raw_source is None and isinstance(task.raw_result_response, dict):
            raw_source = task.raw_result_response
        if raw_source is None:
            return None

        try:
            raw_paths = self.file_storage.save_raw_result_artifacts(task.task_id, raw_source)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Raw result artifact write failed taskId=%s trigger=%s error=%s",
                task.task_id,
                trigger,
                str(exc),
            )
            return None

        logger.info(
            "Saved raw provider results taskId=%s trigger=%s workflow_raw_path=%s nodes_raw_path=%s",
            task.task_id,
            trigger,
            raw_paths.get("workflow"),
            raw_paths.get("nodes"),
        )
        return raw_paths

    async def _update_result_extraction_state(
        self,
        task: TaskRecord,
        *,
        status: str,
        trigger: str,
        reason: str,
        extra: dict | None = None,
    ) -> TaskRecord:
        updated_metadata = dict(task.metadata)
        current = dict(updated_metadata.get("result_extraction") or {})
        current.update(
            {
                "status": status,
                "trigger": trigger,
                "reason": reason,
            }
        )
        if extra:
            current.update(extra)
        updated_metadata["result_extraction"] = current
        updated_task = task.model_copy(update={"metadata": updated_metadata})
        await self.task_service.update_task(updated_task)
        return updated_task

    def _resolve_visitor_biz_id(self, visitor_biz_id: str | None) -> str:
        candidate = (visitor_biz_id or "").strip()
        if candidate:
            return candidate
        return self.settings.yuanqi_default_visitor_biz_id

    @staticmethod
    def _parse_review_role(review_role: str) -> ReviewRole:
        raw = (review_role or "").strip()
        alias_map = {
            ReviewRole.PARTY_A.value: ReviewRole.PARTY_A.value,
            ReviewRole.PARTY_B.value: ReviewRole.PARTY_B.value,
            "party_a": ReviewRole.PARTY_A.value,
            "party_b": ReviewRole.PARTY_B.value,
        }
        normalized = alias_map.get(raw)
        if normalized is None:
            raise InvalidReviewRoleError(raw)
        return ReviewRole(normalized)

    @staticmethod
    def _map_task_node(node) -> TaskNodeResponse:
        return TaskNodeResponse(
            nodeId=node.node_id,
            nodeName=node.node_name,
            status=node.status,
            startedAt=node.started_at,
            finishedAt=node.finished_at,
            input=node.input,
            output=node.output,
            error=node.error,
            nodeType=node.node_type,
            display_order=node.display_order,
        )

    @staticmethod
    def _build_status_message(task: TaskRecord) -> str | None:
        if task.status == TaskStatus.CREATED:
            return "\u4efb\u52a1\u5df2\u521b\u5efa\uff0c\u7b49\u5f85\u4e0a\u4f20\u548c\u6267\u884c\u3002"
        if task.status == TaskStatus.QUEUED:
            return "\u4efb\u52a1\u6392\u961f\u4e2d\u3002"
        if task.status == TaskStatus.RUNNING:
            total = len(task.node_states or [])
            finished = len([node for node in task.node_states or [] if node.status.value in {"success", "failed"}])
            return f"\u5de5\u4f5c\u6d41\u6267\u884c\u4e2d\uff0c\u5df2\u5b8c\u6210 {finished}/{total} \u4e2a\u8282\u70b9\u3002" if total else "\u5de5\u4f5c\u6d41\u6267\u884c\u4e2d\u3002"
        if task.status == TaskStatus.SUCCEEDED:
            return "\u5de5\u4f5c\u6d41\u6267\u884c\u5b8c\u6210\u3002"
        if task.status == TaskStatus.FAILED:
            return task.error_message or "\u5de5\u4f5c\u6d41\u6267\u884c\u5931\u8d25\u3002"
        return None

    @staticmethod
    def _build_provider_error(task: TaskRecord) -> AppError | None:
        provider_error = task.metadata.get("provider_error")
        if not isinstance(provider_error, dict):
            return None

        code = provider_error.get("code")
        message = provider_error.get("message")
        status_code = provider_error.get("statusCode")

        if not isinstance(code, str) or not isinstance(message, str) or not isinstance(status_code, int):
            return None

        return AppError(
            status_code=status_code,
            code=code,
            message=message,
            detail=provider_error.get("detail"),
        )

    @staticmethod
    def _result_file_exists(task: TaskRecord) -> bool:
        if not task.result_path:
            return False
        return Path(task.result_path).exists()

    @staticmethod
    def _resolve_completed_at(task: TaskRecord):
        if task.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
            return None

        finished_nodes = [node.finished_at for node in task.node_states or [] if node.finished_at is not None]
        if finished_nodes:
            return max(finished_nodes)
        return task.updated_at

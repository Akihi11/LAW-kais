from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

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
from app.services.result_mapper import build_default_workflow_groups


class MockProvider(BaseProvider):
    name = ProviderName.MOCK

    def __init__(self, sample_result_path: Path, fast_complete: bool = False) -> None:
        self.sample_result_path = sample_result_path
        self.fast_complete = fast_complete

    async def create_review(self, request: ProviderCreateReviewRequest) -> ProviderTaskHandle:
        return ProviderTaskHandle(
            provider_task_id=f"mock_{request.task_id}",
            raw_request={
                "task_id": request.task_id,
                "review_role": request.review_role.value,
                "file_name": request.file_info.original_filename,
            },
            raw_response={"status": TaskStatus.CREATED.value},
        )

    async def get_status(self, task: TaskRecord) -> ProviderStatus:
        if task.status == TaskStatus.FAILED:
            return ProviderStatus(
                status=TaskStatus.FAILED,
                current_stage=task.current_stage,
                current_stage_label=task.current_stage_label,
                progress=task.progress,
                error_message=task.error_message,
            )

        if task.status == TaskStatus.SUCCEEDED:
            return ProviderStatus(
                status=TaskStatus.SUCCEEDED,
                current_stage=StageCode.COMPLETED,
                current_stage_label=get_stage_label(StageCode.COMPLETED),
                progress=100,
            )

        elapsed_seconds = (datetime.now(UTC) - task.created_at).total_seconds()
        stage_duration = 0.2 if self.fast_complete else 1.0
        timeline = [
            (TaskStatus.UPLOADING, StageCode.UPLOADING, 12),
            (TaskStatus.QUEUED, StageCode.PARSING, 28),
            (TaskStatus.RUNNING, StageCode.PARSING, 42),
            (TaskStatus.RUNNING, StageCode.EXTRACTING, 58),
            (TaskStatus.RUNNING, StageCode.REVIEWING, 76),
            (TaskStatus.RUNNING, StageCode.SUMMARIZING, 92),
        ]

        for index, (status, stage, progress) in enumerate(timeline, start=1):
            if elapsed_seconds < index * stage_duration:
                return self._status(status, stage, progress)

        return self._status(TaskStatus.SUCCEEDED, StageCode.COMPLETED, 100)

    async def get_result(self, task: TaskRecord) -> ProviderResultPayload:
        current_status = await self.get_status(task)
        if current_status.status != TaskStatus.SUCCEEDED:
            raise RuntimeError("Mock result requested before task completion.")

        payload = copy.deepcopy(self._load_sample_result())
        payload["taskId"] = task.task_id
        payload["status"] = TaskStatus.SUCCEEDED.value
        payload.setdefault("basicInfo", {})
        payload["basicInfo"]["perspective"] = task.review_role.value
        payload["basicInfo"]["contractName"] = payload["basicInfo"].get("contractName") or Path(
            task.file_info.original_filename
        ).stem
        payload.setdefault("workflow", {})
        payload["workflow"]["groups"] = payload["workflow"].get("groups") or build_default_workflow_groups()

        return ProviderResultPayload(
            raw=payload,
            usage={"provider": self.name.value, "mock": True, "fastComplete": self.fast_complete},
            steps=[
                {"name": "文件收集", "status": "done"},
                {"name": "文档解析", "status": "done"},
                {"name": "条款抽取", "status": "done"},
                {"name": "风险审查", "status": "done"},
                {"name": "报告生成", "status": "done"},
            ],
        )

    def _load_sample_result(self) -> dict:
        return copy.deepcopy(json.loads(self.sample_result_path.read_text(encoding="utf-8-sig")))

    @staticmethod
    def _status(status: TaskStatus, stage: StageCode, progress: int) -> ProviderStatus:
        return ProviderStatus(
            status=status,
            current_stage=stage,
            current_stage_label=get_stage_label(stage),
            progress=progress,
        )

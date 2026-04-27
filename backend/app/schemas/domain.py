from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewRole(str, Enum):
    PARTY_A = "甲方"
    PARTY_B = "乙方"


class TaskStatus(str, Enum):
    CREATED = "created"
    UPLOADING = "uploading"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StageCode(str, Enum):
    UPLOADING = "uploading"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    REVIEWING = "reviewing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"


STAGE_LABELS: dict[StageCode, str] = {
    StageCode.UPLOADING: "?????",
    StageCode.PARSING: "?????",
    StageCode.EXTRACTING: "?????",
    StageCode.REVIEWING: "?????",
    StageCode.SUMMARIZING: "?????",
    StageCode.COMPLETED: "???",
}


def get_stage_label(stage: StageCode) -> str:
    return STAGE_LABELS[stage]


class ProviderName(str, Enum):
    MOCK = "mock"
    TENCENT_YUANQI = "tencent_yuanqi"
    TENCENT_YUANQI_SSE = "tencent_yuanqi_sse"
    TENCENT_YUANQI_ASYNC = "tencent_yuanqi_async"


class WorkflowExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskNodeStatus(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class WorkflowNodeState(BaseModel):
    name: str
    status: WorkflowExecutionStatus = WorkflowExecutionStatus.PENDING
    display_order: int | None = Field(default=None, ge=1)


class WorkflowGroupState(BaseModel):
    name: str
    status: WorkflowExecutionStatus = WorkflowExecutionStatus.PENDING
    nodes: list[WorkflowNodeState] = Field(default_factory=list)


class TaskNodeState(BaseModel):
    node_id: str
    node_name: str
    status: TaskNodeStatus = TaskNodeStatus.WAITING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input: dict[str, Any] | list[Any] | str | None = None
    output: dict[str, Any] | list[Any] | str | None = None
    error: str | None = None
    node_type: str | None = None
    display_order: int | None = Field(default=None, ge=1)
    raw: dict[str, Any] | None = None


class IssueLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevelText(str, Enum):
    HIGH = "?"
    MEDIUM = "?"
    LOW = "?"


class FileInfo(BaseModel):
    original_filename: str
    stored_filename: str
    content_type: str | None = None
    size_bytes: int
    extension: str
    path: str


class ProviderCreateReviewRequest(BaseModel):
    task_id: str
    review_role: ReviewRole
    file_info: FileInfo
    public_file_url: str | None = None
    visitor_biz_id: str | None = None


class ProviderTaskHandle(BaseModel):
    provider_task_id: str
    raw_request: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None
    request_id: str | None = None
    visitor_biz_id: str | None = None
    app_id: str | None = None
    business_id: str | None = None
    message: str | None = None


class ProviderStatus(BaseModel):
    status: TaskStatus
    current_stage: StageCode
    current_stage_label: str
    progress: int = Field(ge=0, le=100)
    error_message: str | None = None
    request_id: str | None = None
    visitor_biz_id: str | None = None
    nodes: list[TaskNodeState] | None = None
    workflow_groups: list[WorkflowGroupState] | None = None
    raw: dict[str, Any] | None = None
    message: str | None = None


class ProviderResultPayload(BaseModel):
    raw: Any
    usage: dict[str, Any] | None = None
    steps: list[dict[str, Any]] | None = None


class TaskRecord(BaseModel):
    task_id: str
    provider_name: ProviderName
    provider_task_id: str
    review_role: ReviewRole
    file_info: FileInfo
    status: TaskStatus = TaskStatus.CREATED
    current_stage: StageCode = StageCode.UPLOADING
    current_stage_label: str = Field(default_factory=lambda: get_stage_label(StageCode.UPLOADING))
    progress: int = Field(default=0, ge=0, le=100)
    error_message: str | None = None
    request_id: str | None = None
    visitor_biz_id: str | None = None
    app_id: str | None = None
    business_id: str | None = None
    file_id: str | None = None
    document_id: str | None = None
    node_states: list[TaskNodeState] | None = None
    workflow_groups: list[WorkflowGroupState] | None = None
    result_path: str | None = None
    result_payload: dict[str, Any] | None = None
    provider_request: dict[str, Any] | None = None
    provider_response: dict[str, Any] | None = None
    raw_create_response: dict[str, Any] | None = None
    raw_status_response: dict[str, Any] | None = None
    raw_result_response: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

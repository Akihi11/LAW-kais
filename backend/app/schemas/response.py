from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.domain import IssueLevel, ReviewRole, TaskNodeStatus, TaskStatus, WorkflowExecutionStatus, WorkflowGroupState


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Any = None


class HealthResponse(BaseModel):
    ok: bool = True


class CreateReviewResponse(BaseModel):
    success: bool = True
    provider: str | None = None
    taskId: str
    requestId: str | None = None
    status: TaskStatus
    message: str | None = None


class TaskNodeResponse(BaseModel):
    nodeId: str
    nodeName: str
    status: TaskNodeStatus
    startedAt: datetime | None = None
    finishedAt: datetime | None = None
    input: dict[str, Any] | list[Any] | str | None = None
    output: dict[str, Any] | list[Any] | str | None = None
    error: str | None = None
    nodeType: str | None = None
    display_order: int | None = Field(default=None, ge=1)


class ReviewStatusResponse(BaseModel):
    success: bool = True
    provider: str | None = None
    taskId: str
    requestId: str | None = None
    visitorBizId: str | None = None
    status: TaskStatus
    currentStage: str
    currentStageLabel: str
    progress: int = Field(ge=0, le=100)
    errorMessage: str | None = None
    message: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    completedAt: datetime | None = None
    workflowGroups: list[WorkflowGroupState] | None = None
    nodes: list[TaskNodeResponse] | None = None
    raw: dict[str, Any] | None = None


class BasicInfo(BaseModel):
    contractName: str | None = None
    contractType: str | None = None
    perspective: ReviewRole | None = None


class SummaryInfo(BaseModel):
    riskLevel: str | None = None
    conclusion: str | None = None


class StatsInfo(BaseModel):
    high: int | None = Field(default=None, ge=0)
    medium: int | None = Field(default=None, ge=0)
    low: int | None = Field(default=None, ge=0)
    manualReview: bool | None = None


class ClauseRiskStats(BaseModel):
    high_count: int | None = Field(default=None, ge=0)
    medium_count: int | None = Field(default=None, ge=0)
    low_count: int | None = Field(default=None, ge=0)
    extra_risk_topic_count: int | None = Field(default=None, ge=0)


class ClauseOrderedFinding(BaseModel):
    clause_order: int | None = None
    clause_title: str | None = None
    clause_type: str | None = None
    core_issue: str | None = None
    evidence_position: str | None = None
    evidence_quote: str | None = None
    need_manual_review: bool | None = None
    revision_suggestion: str | None = None
    proposed_amendment: str | None = None
    risk_level: str | None = None
    risk_reason: str | None = None


class ExtraRiskTopic(BaseModel):
    topic_name: str | None = None
    topic_category: str | None = None
    core_issue: str | None = None
    evidence_position: str | None = None
    evidence_quote: str | None = None
    suggested_action: str | None = None
    need_manual_review: bool | None = None
    risk_level: str | None = None
    why_not_in_13: str | None = None
    related_clause_titles: list[str] = Field(default_factory=list)


class WorkflowNode(BaseModel):
    name: str
    status: WorkflowExecutionStatus | None = None
    display_order: int | None = Field(default=None, ge=1)


class WorkflowGroup(BaseModel):
    name: str
    status: WorkflowExecutionStatus | None = None
    nodes: list[WorkflowNode] = Field(default_factory=list)


class WorkflowInfo(BaseModel):
    groups: list[WorkflowGroup] = Field(default_factory=list)


class IssueItem(BaseModel):
    id: str
    title: str
    level: IssueLevel
    position: str | None = None
    summary: str | None = None
    evidence: str | None = None
    suggestion: str | None = None
    original: str | None = None
    revised: str | None = None
    anchor: str | None = None


class ContractSection(BaseModel):
    id: str
    title: str
    paragraphs: list[str] = Field(default_factory=list)


class ReviewResultResponse(BaseModel):
    taskId: str
    status: TaskStatus
    contract_type: str | None = None
    overall_conclusion: str | None = None
    overall_risk_level: str | None = None
    need_manual_review: bool | None = None
    clause_risk_stats: ClauseRiskStats | None = None
    clause_ordered_findings: list[ClauseOrderedFinding] = Field(default_factory=list)
    extra_risk_topics: list[ExtraRiskTopic] = Field(default_factory=list)
    final_review_report: str | None = None
    workflow: WorkflowInfo | None = None
    contractSections: list[ContractSection] = Field(default_factory=list)
    basicInfo: BasicInfo | None = None
    summary: SummaryInfo | None = None
    stats: StatsInfo | None = None
    fullReport: str | None = None
    issues: list[IssueItem] = Field(default_factory=list)

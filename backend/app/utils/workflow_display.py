from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.schemas.domain import (
    TaskNodeState,
    TaskNodeStatus,
    WorkflowExecutionStatus,
    WorkflowGroupState,
    WorkflowNodeState,
)


DEFAULT_WORKFLOW_NODE_SEQUENCE: tuple[str, ...] = (
    "开始",
    "变量赋值-审查视角",
    "变量赋值-文件文本",
    "代码-截断文本前20行",
    "大模型-提取文件名",
    "条件判断-文件名",
    "变量赋值-filename",
    "变量赋值-contract_name",
    "大模型-合同类型识别",
    "大模型-审查口径约束",
    "大模型-重点条款抽取",
    "条件判断-条款缺失",
    "大模型-missing核查",
    "代码-ArrayObject去重合并",
    "循环",
    "大模型-补充风险主题抽取",
    "知识检索-全局",
    "大模型-全局审查层",
    "大模型-建议一致性校验",
    "代码-风险统计规则",
    "大模型-结构化汇总",
    "大模型-报告生成",
    "结束",
)


def _normalize(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"[\s\-_:：·、（）()\[\]【】,.，。/]+", "", text).lower()


_NORMALIZED_DEFAULT_ORDER = {
    _normalize(name): index
    for index, name in enumerate(DEFAULT_WORKFLOW_NODE_SEQUENCE, start=1)
}


def normalize_workflow_node_name(value: Any) -> str:
    return _normalize(value)


def is_end_workflow_node(name: Any) -> bool:
    normalized = _normalize(name)
    return normalized in {"结束", "end"}


def is_executed_task_node_status(status: TaskNodeStatus | None) -> bool:
    return status in {TaskNodeStatus.SUCCESS, TaskNodeStatus.RUNNING, TaskNodeStatus.FAILED}


def is_executed_workflow_status(status: WorkflowExecutionStatus | str | None) -> bool:
    if isinstance(status, WorkflowExecutionStatus):
        value = status.value
    else:
        value = str(status or "").strip().lower()
    return value in {
        WorkflowExecutionStatus.DONE.value,
        WorkflowExecutionStatus.RUNNING.value,
        WorkflowExecutionStatus.FAILED.value,
    }


def resolve_workflow_node_order_rank(name: Any) -> int | None:
    normalized = _normalize(name)
    if not normalized:
        return None
    return _NORMALIZED_DEFAULT_ORDER.get(normalized)


def sort_task_nodes_for_display(nodes: list[TaskNodeState]) -> list[TaskNodeState]:
    indexed_nodes = [
        (index, node)
        for index, node in enumerate(nodes)
        if is_executed_task_node_status(node.status)
    ]
    indexed_nodes.sort(key=lambda item: _task_node_display_sort_key(item[1], item[0]))
    return [
        node.model_copy(update={"display_order": display_order})
        for display_order, (_, node) in enumerate(indexed_nodes, start=1)
    ]


def sort_workflow_node_payloads(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed_nodes = [
        (index, dict(node))
        for index, node in enumerate(nodes)
        if is_executed_workflow_status(node.get("status"))
    ]
    indexed_nodes.sort(key=lambda item: _workflow_node_display_sort_key(item[1], item[0]))

    normalized: list[dict[str, Any]] = []
    for display_order, (_, node) in enumerate(indexed_nodes, start=1):
        node["display_order"] = display_order
        normalized.append(node)
    return normalized


def sort_workflow_nodes_for_display(nodes: list[WorkflowNodeState]) -> list[WorkflowNodeState]:
    indexed_nodes = [
        (index, node)
        for index, node in enumerate(nodes)
        if is_executed_workflow_status(node.status)
    ]
    indexed_nodes.sort(key=lambda item: _workflow_node_state_display_sort_key(item[1], item[0]))
    return [
        node.model_copy(update={"display_order": display_order})
        for display_order, (_, node) in enumerate(indexed_nodes, start=1)
    ]


def sort_workflow_groups_for_display(groups: list[WorkflowGroupState]) -> list[WorkflowGroupState]:
    indexed_nodes: list[tuple[int, int, int, WorkflowNodeState]] = []
    original_index = 0
    for group_index, group in enumerate(groups):
        for node_index, node in enumerate(group.nodes or []):
            if is_executed_workflow_status(node.status):
                indexed_nodes.append((group_index, node_index, original_index, node))
            original_index += 1

    indexed_nodes.sort(key=lambda item: _workflow_node_state_display_sort_key(item[3], item[2]))
    nodes_by_group: dict[int, list[WorkflowNodeState]] = {}
    for display_order, (group_index, _, _, node) in enumerate(indexed_nodes, start=1):
        nodes_by_group.setdefault(group_index, []).append(node.model_copy(update={"display_order": display_order}))

    normalized_groups: list[WorkflowGroupState] = []
    for group_index, group in enumerate(groups):
        nodes = nodes_by_group.get(group_index, [])
        if nodes:
            normalized_groups.append(group.model_copy(update={"nodes": nodes}))
    return normalized_groups


def _task_node_display_sort_key(node: TaskNodeState, original_index: int) -> tuple[Any, ...]:
    known_rank = resolve_workflow_node_order_rank(node.node_name)
    time_marker = _to_timestamp(node.started_at or node.finished_at)
    return (
        1 if is_end_workflow_node(node.node_name) else 0,
        1 if known_rank is None else 0,
        known_rank if known_rank is not None else 10_000,
        time_marker,
        original_index,
        _normalize(node.node_name),
    )


def _workflow_node_state_display_sort_key(node: WorkflowNodeState, original_index: int) -> tuple[Any, ...]:
    known_rank = resolve_workflow_node_order_rank(node.name)
    return (
        1 if is_end_workflow_node(node.name) else 0,
        1 if known_rank is None else 0,
        known_rank if known_rank is not None else 10_000,
        original_index,
        _normalize(node.name),
    )



def _workflow_node_display_sort_key(node: dict[str, Any], original_index: int) -> tuple[Any, ...]:
    known_rank = resolve_workflow_node_order_rank(node.get("name"))
    return (
        1 if is_end_workflow_node(node.get("name")) else 0,
        1 if known_rank is None else 0,
        known_rank if known_rank is not None else 10_000,
        original_index,
        _normalize(node.get("name")),
    )


def _to_timestamp(value: datetime | None) -> float:
    if value is None:
        return float("inf")
    return value.timestamp()

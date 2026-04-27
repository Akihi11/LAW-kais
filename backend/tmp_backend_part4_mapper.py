from pathlib import Path

root = Path(r'd:\PythonCode\LAW')


def replace(rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'replace target not found in {rel}: {old[:120]!r}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')

replace(
    'backend/app/services/result_mapper.py',
    'from app.schemas.domain import IssueLevel, TaskRecord, TaskStatus, WorkflowExecutionStatus\n',
    'from app.schemas.domain import IssueLevel, TaskRecord, TaskStatus, WorkflowExecutionStatus\nfrom app.utils.workflow_display import sort_workflow_node_payloads\n',
)
replace(
    'backend/app/services/result_mapper.py',
    '        groups = self._value_from_paths(sources, ("workflow", "groups"), ("workflowGroups",))\n        if isinstance(groups, list):\n            return {"groups": groups}\n\n        steps = self._value_from_paths(sources, ("steps",))\n        if isinstance(steps, list) and steps:\n            return {"groups": self._workflow_from_steps(steps)}\n\n        return None\n',
    '        groups = self._value_from_paths(sources, ("workflow", "groups"), ("workflowGroups",))\n        if isinstance(groups, list):\n            normalized_groups = self._normalize_workflow_groups(groups)\n            if normalized_groups:\n                return {"groups": normalized_groups}\n\n        steps = self._value_from_paths(sources, ("steps",))\n        if isinstance(steps, list) and steps:\n            return {"groups": self._workflow_from_steps(steps)}\n\n        return None\n',
)
replace(
    'backend/app/services/result_mapper.py',
    '            revision_suggestion = self._coalesce(\n                self._string_or_none(item.get("revision_suggestion")),\n                self._string_or_none(item.get("revisionSuggestion")),\n                self._string_or_none(item.get("suggestion")),\n                self._string_or_none(item.get("suggested_action")),\n                self._string_or_none(item.get("action")),\n                self._string_or_none(item.get("suggested_direction")),\n            )\n            risk_level = self._normalize_risk_level(item.get("risk_level") or item.get("riskLevel"))\n',
    '            revision_suggestion = self._coalesce(\n                self._string_or_none(item.get("revision_suggestion")),\n                self._string_or_none(item.get("revisionSuggestion")),\n                self._string_or_none(item.get("suggestion")),\n                self._string_or_none(item.get("suggested_action")),\n                self._string_or_none(item.get("action")),\n                self._string_or_none(item.get("suggested_direction")),\n            )\n            proposed_amendment = self._string_or_none(item.get("proposed_amendment"))\n            risk_level = self._normalize_risk_level(item.get("risk_level") or item.get("riskLevel"))\n',
)
replace(
    'backend/app/services/result_mapper.py',
    '                    "need_manual_review": need_manual_review,\n                    "revision_suggestion": revision_suggestion or None,\n                    "risk_level": risk_level,\n                    "risk_reason": risk_reason or None,\n                }\n',
    '                    "need_manual_review": need_manual_review,\n                    "revision_suggestion": revision_suggestion or None,\n                    "proposed_amendment": proposed_amendment or None,\n                    "risk_level": risk_level,\n                    "risk_reason": risk_reason or None,\n                }\n',
)
replace(
    'backend/app/services/result_mapper.py',
    '    def _workflow_from_steps(self, steps: list[Any]) -> list[dict[str, Any]]:\n        nodes: list[dict[str, Any]] = []\n        for step in steps[:24]:\n            if not isinstance(step, dict):\n                continue\n            name = self._coalesce(\n                self._string_or_none(step.get("name")),\n                self._string_or_none(step.get("title")),\n                self._string_or_none(step.get("id")),\n                "未命名节点",\n            )\n            status = self._coalesce(\n                self._string_or_none(step.get("status")),\n                WorkflowExecutionStatus.DONE.value,\n            )\n            nodes.append({"name": name, "status": status})\n\n        return [\n            {\n                "name": "平台执行轨迹",\n                "status": WorkflowExecutionStatus.DONE.value,\n                "nodes": nodes or [{"name": "结果生成", "status": WorkflowExecutionStatus.DONE.value}],\n            }\n        ]\n',
    '    def _workflow_from_steps(self, steps: list[Any]) -> list[dict[str, Any]]:\n        nodes: list[dict[str, Any]] = []\n        for step in steps[:24]:\n            if not isinstance(step, dict):\n                continue\n            name = self._coalesce(\n                self._string_or_none(step.get("name")),\n                self._string_or_none(step.get("title")),\n                self._string_or_none(step.get("id")),\n                "未命名节点",\n            )\n            status = self._coalesce(\n                self._string_or_none(step.get("status")),\n                WorkflowExecutionStatus.DONE.value,\n            )\n            nodes.append({"name": name, "status": status})\n\n        ordered_nodes = sort_workflow_node_payloads(nodes)\n        if not ordered_nodes:\n            return []\n\n        return [\n            {\n                "name": "平台执行轨迹",\n                "status": self._derive_workflow_group_status(ordered_nodes),\n                "nodes": ordered_nodes,\n            }\n        ]\n',
)
replace(
    'backend/app/services/result_mapper.py',
    '    def _value_from_paths(self, sources: list[dict[str, Any]], *paths: JSON_PATH) -> Any:\n',
    '    def _normalize_workflow_groups(self, groups: list[Any]) -> list[dict[str, Any]]:\n        nodes: list[dict[str, Any]] = []\n        group_name = ""\n\n        for group in groups:\n            if not isinstance(group, dict):\n                continue\n            if not group_name:\n                group_name = self._string_or_none(group.get("name")) or ""\n            raw_nodes = group.get("nodes")\n            if not isinstance(raw_nodes, list):\n                continue\n            for node in raw_nodes:\n                if not isinstance(node, dict):\n                    continue\n                node_name = self._coalesce(\n                    self._string_or_none(node.get("name")),\n                    self._string_or_none(node.get("title")),\n                    self._string_or_none(node.get("id")),\n                    "未命名节点",\n                )\n                node_status = self._coalesce(\n                    self._string_or_none(node.get("status")),\n                    WorkflowExecutionStatus.PENDING.value,\n                )\n                nodes.append({"name": node_name, "status": node_status})\n\n        ordered_nodes = sort_workflow_node_payloads(nodes)\n        if not ordered_nodes:\n            return []\n\n        return [\n            {\n                "name": group_name or "平台执行轨迹",\n                "status": self._derive_workflow_group_status(ordered_nodes),\n                "nodes": ordered_nodes,\n            }\n        ]\n\n    def _derive_workflow_group_status(self, nodes: list[dict[str, Any]]) -> str:\n        statuses = {self._stringify(node.get("status")).lower() for node in nodes}\n        if WorkflowExecutionStatus.FAILED.value in statuses:\n            return WorkflowExecutionStatus.FAILED.value\n        if WorkflowExecutionStatus.RUNNING.value in statuses:\n            return WorkflowExecutionStatus.RUNNING.value\n        if statuses and statuses.issubset({WorkflowExecutionStatus.DONE.value}):\n            return WorkflowExecutionStatus.DONE.value\n        return WorkflowExecutionStatus.PENDING.value\n\n    def _value_from_paths(self, sources: list[dict[str, Any]], *paths: JSON_PATH) -> Any:\n',
)

print('ok')

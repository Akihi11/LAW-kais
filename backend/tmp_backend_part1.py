from pathlib import Path
from textwrap import dedent

root = Path(r'd:\PythonCode\LAW')


def replace(rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'replace target not found in {rel}: {old[:80]!r}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def write(rel: str, content: str) -> None:
    (root / rel).write_text(content, encoding='utf-8', newline='\n')

write(
    'backend/app/utils/workflow_display.py',
    dedent('''\
    from __future__ import annotations

    import re
    from datetime import datetime
    from typing import Any

    from app.schemas.domain import TaskNodeState, TaskNodeStatus, WorkflowExecutionStatus


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
        return re.sub(r"[\\s\\-_:：·、（）()\\[\\]【】,.，。/]+", "", text).lower()


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
    ''')
)

replace(
    'backend/app/config.py',
    '    results_dir: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "results")\n',
    '    results_dir: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "results")\n    raw_results_dir: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "raw_results")\n',
)

replace(
    'backend/app/schemas/domain.py',
    'class WorkflowNodeState(BaseModel):\n    name: str\n    status: WorkflowExecutionStatus = WorkflowExecutionStatus.PENDING\n',
    'class WorkflowNodeState(BaseModel):\n    name: str\n    status: WorkflowExecutionStatus = WorkflowExecutionStatus.PENDING\n    display_order: int | None = Field(default=None, ge=1)\n',
)
replace(
    'backend/app/schemas/domain.py',
    'class TaskNodeState(BaseModel):\n    node_id: str\n    node_name: str\n    status: TaskNodeStatus = TaskNodeStatus.WAITING\n    started_at: datetime | None = None\n    finished_at: datetime | None = None\n    input: dict[str, Any] | list[Any] | str | None = None\n    output: dict[str, Any] | list[Any] | str | None = None\n    error: str | None = None\n    node_type: str | None = None\n    raw: dict[str, Any] | None = None\n',
    'class TaskNodeState(BaseModel):\n    node_id: str\n    node_name: str\n    status: TaskNodeStatus = TaskNodeStatus.WAITING\n    started_at: datetime | None = None\n    finished_at: datetime | None = None\n    input: dict[str, Any] | list[Any] | str | None = None\n    output: dict[str, Any] | list[Any] | str | None = None\n    error: str | None = None\n    node_type: str | None = None\n    display_order: int | None = Field(default=None, ge=1)\n    raw: dict[str, Any] | None = None\n',
)

replace(
    'backend/app/schemas/response.py',
    'class TaskNodeResponse(BaseModel):\n    nodeId: str\n    nodeName: str\n    status: TaskNodeStatus\n    startedAt: datetime | None = None\n    finishedAt: datetime | None = None\n    input: dict[str, Any] | list[Any] | str | None = None\n    output: dict[str, Any] | list[Any] | str | None = None\n    error: str | None = None\n    nodeType: str | None = None\n',
    'class TaskNodeResponse(BaseModel):\n    nodeId: str\n    nodeName: str\n    status: TaskNodeStatus\n    startedAt: datetime | None = None\n    finishedAt: datetime | None = None\n    input: dict[str, Any] | list[Any] | str | None = None\n    output: dict[str, Any] | list[Any] | str | None = None\n    error: str | None = None\n    nodeType: str | None = None\n    display_order: int | None = Field(default=None, ge=1)\n',
)
replace(
    'backend/app/schemas/response.py',
    'class ClauseOrderedFinding(BaseModel):\n    clause_order: int | None = None\n    clause_title: str | None = None\n    clause_type: str | None = None\n    core_issue: str | None = None\n    evidence_position: str | None = None\n    evidence_quote: str | None = None\n    need_manual_review: bool | None = None\n    revision_suggestion: str | None = None\n    risk_level: str | None = None\n    risk_reason: str | None = None\n',
    'class ClauseOrderedFinding(BaseModel):\n    clause_order: int | None = None\n    clause_title: str | None = None\n    clause_type: str | None = None\n    core_issue: str | None = None\n    evidence_position: str | None = None\n    evidence_quote: str | None = None\n    need_manual_review: bool | None = None\n    revision_suggestion: str | None = None\n    proposed_amendment: str | None = None\n    risk_level: str | None = None\n    risk_reason: str | None = None\n',
)
replace(
    'backend/app/schemas/response.py',
    'class WorkflowNode(BaseModel):\n    name: str\n    status: WorkflowExecutionStatus | None = None\n',
    'class WorkflowNode(BaseModel):\n    name: str\n    status: WorkflowExecutionStatus | None = None\n    display_order: int | None = Field(default=None, ge=1)\n',
)

write(
    'backend/app/utils/file_storage.py',
    dedent('''\
    from __future__ import annotations

    import json
    import re
    from pathlib import Path
    from typing import Any
    from urllib.parse import quote

    from fastapi import UploadFile

    from app.config import Settings
    from app.exceptions import FileTooLargeError, UnsupportedFileTypeError
    from app.schemas.domain import FileInfo
    from app.schemas.response import ReviewResultResponse


    class FileStorage:
        allowed_extensions = {".docx", ".pdf"}

        def __init__(self, settings: Settings) -> None:
            self.settings = settings
            self.max_size_bytes = int(settings.max_upload_size_mb * 1024 * 1024)
            self.uploads_dir = settings.uploads_dir
            self.results_dir = settings.results_dir
            self.raw_results_dir = settings.raw_results_dir
            self.temp_dir = settings.temp_dir

        def ensure_directories(self) -> None:
            for directory in (self.uploads_dir, self.results_dir, self.raw_results_dir, self.temp_dir):
                directory.mkdir(parents=True, exist_ok=True)

        async def save_upload(self, task_id: str, upload_file: UploadFile) -> FileInfo:
            original_filename = upload_file.filename or "uploaded-file"
            extension = Path(original_filename).suffix.lower()
            if extension not in self.allowed_extensions:
                raise UnsupportedFileTypeError(original_filename, sorted(self.allowed_extensions))

            safe_filename = f"{task_id}_{self._sanitize_filename(original_filename)}"
            destination = self.uploads_dir / safe_filename

            total_bytes = 0
            try:
                with destination.open("wb") as output_stream:
                    while True:
                        chunk = await upload_file.read(1024 * 1024)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > self.max_size_bytes:
                            raise FileTooLargeError(self.settings.max_upload_size_mb)
                        output_stream.write(chunk)
            except Exception:
                if destination.exists():
                    destination.unlink(missing_ok=True)
                raise
            finally:
                await upload_file.close()

            return FileInfo(
                original_filename=original_filename,
                stored_filename=safe_filename,
                content_type=upload_file.content_type,
                size_bytes=total_bytes,
                extension=extension,
                path=str(destination),
            )

        def build_upload_public_url(self, file_info: FileInfo) -> str:
            if self.settings.use_fixed_test_file_url and self.settings.fixed_test_file_url:
                return self.settings.fixed_test_file_url.strip()

            base_url = self.settings.public_file_base_url.rstrip("/")
            relative_path = f"/storage/uploads/{quote(file_info.stored_filename)}"
            return f"{base_url}{relative_path}"

        def save_result(self, task_id: str, result: ReviewResultResponse) -> str:
            destination = self.results_dir / f"{task_id}.json"
            destination.write_text(
                json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(destination)

        def save_raw_result_artifacts(self, task_id: str, raw_payload: dict[str, Any] | None) -> dict[str, str]:
            workflow_payload = {
                "taskId": task_id,
                "describe_workflow_run": self._extract_workflow_raw_payload(raw_payload),
            }
            nodes_payload = {
                "taskId": task_id,
                "describe_node_runs": self._extract_node_raw_payloads(raw_payload),
            }

            workflow_destination = self.raw_results_dir / f"{task_id}.workflow.json"
            nodes_destination = self.raw_results_dir / f"{task_id}.nodes.json"
            workflow_destination.write_text(json.dumps(workflow_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            nodes_destination.write_text(json.dumps(nodes_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return {
                "workflow": str(workflow_destination),
                "nodes": str(nodes_destination),
            }

        def load_result(self, result_path: str) -> dict:
            return json.loads(Path(result_path).read_text(encoding="utf-8"))

        def delete_file(self, file_path: str) -> None:
            path = Path(file_path)
            if path.exists():
                path.unlink(missing_ok=True)

        def _extract_workflow_raw_payload(self, raw_payload: dict[str, Any] | None) -> Any:
            if not isinstance(raw_payload, dict):
                return None
            if "describeWorkflowRun" in raw_payload:
                return raw_payload.get("describeWorkflowRun")
            return raw_payload

        def _extract_node_raw_payloads(self, raw_payload: dict[str, Any] | None) -> list[Any]:
            if not isinstance(raw_payload, dict):
                return []
            describe_node_runs = raw_payload.get("describeNodeRuns")
            if isinstance(describe_node_runs, list):
                return describe_node_runs
            return []

        @staticmethod
        def _sanitize_filename(filename: str) -> str:
            sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
            return sanitized or "upload"
    ''')
)

print('ok')

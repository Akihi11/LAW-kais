from __future__ import annotations

import json
import os
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
        if os.getenv("VERCEL"):
            storage_dir = Path("/tmp/storage")
            self.uploads_dir = storage_dir / "uploads"
            self.results_dir = storage_dir / "results"
            self.raw_results_dir = storage_dir / "raw_results"
            self.temp_dir = storage_dir / "temp"
        else:
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
        terminal_output_payload = self._extract_terminal_output_payload(task_id, raw_payload)

        workflow_destination = self.raw_results_dir / f"{task_id}.workflow.json"
        nodes_destination = self.raw_results_dir / f"{task_id}.nodes.json"
        workflow_destination.write_text(json.dumps(workflow_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        nodes_destination.write_text(json.dumps(nodes_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        saved_paths = {
            "workflow": str(workflow_destination),
            "nodes": str(nodes_destination),
        }
        if terminal_output_payload is not None:
            output_destination = self.raw_results_dir / f"{task_id}.output.json"
            output_destination.write_text(json.dumps(terminal_output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            saved_paths["output"] = str(output_destination)
        return saved_paths

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

    def _extract_terminal_output_payload(self, task_id: str, raw_payload: dict[str, Any] | None) -> dict[str, Any] | None:
        terminal_node_payload = self._select_terminal_node_payload(self._extract_node_raw_payloads(raw_payload))
        node_run = self._extract_node_run_payload(terminal_node_payload)
        if node_run is None:
            return None

        return {
            "taskId": task_id,
            "nodeRunId": self._stringify(node_run.get("NodeRunId"), terminal_node_payload.get("NodeRunId")),
            "nodeName": self._stringify(node_run.get("NodeName"), terminal_node_payload.get("NodeName")),
            "nodeType": node_run.get("NodeType"),
            "output": node_run.get("Output"),
            "taskOutput": node_run.get("TaskOutput"),
            "outputRef": node_run.get("OutputRef"),
            "taskOutputRef": node_run.get("TaskOutputRef"),
            "describe_node_run": terminal_node_payload,
        }

    def _select_terminal_node_payload(self, node_payloads: list[Any]) -> dict[str, Any] | None:
        candidates: list[tuple[int, int, dict[str, Any]]] = []
        terminal_candidates: list[tuple[int, int, dict[str, Any]]] = []

        for index, node_payload in enumerate(node_payloads):
            if not isinstance(node_payload, dict):
                continue
            node_run = self._extract_node_run_payload(node_payload)
            if node_run is None:
                continue

            score = self._score_node_output_signal(node_run)
            candidate = (score, index, node_payload)
            candidates.append(candidate)
            if self._looks_like_terminal_node(node_run, node_payload):
                terminal_candidates.append(candidate)

        if terminal_candidates:
            return max(terminal_candidates, key=lambda item: (item[0], item[1]))[2]
        if candidates:
            return max(candidates, key=lambda item: (item[0], item[1]))[2]
        return None

    def _extract_node_run_payload(self, node_payload: Any) -> dict[str, Any] | None:
        if not isinstance(node_payload, dict):
            return None
        response = node_payload.get("Response")
        if isinstance(response, dict):
            node_run = response.get("NodeRun")
            if isinstance(node_run, dict):
                return node_run
        return None

    def _looks_like_terminal_node(self, node_run: dict[str, Any], node_payload: dict[str, Any]) -> bool:
        node_name = self._stringify(node_run.get("NodeName"), node_payload.get("NodeName")).lower()
        node_type = self._stringify(node_run.get("NodeType")).lower()
        terminal_keywords = ("结束", "汇总", "总结", "报告", "输出", "reply", "end", "summary", "report")
        if any(keyword in node_name for keyword in terminal_keywords):
            return True
        return node_type in {"10", "16", "reply", "end"}

    def _score_node_output_signal(self, node_run: dict[str, Any]) -> int:
        score = 0
        if not self._is_empty_value(node_run.get("Output")):
            score += 2
        if not self._is_empty_value(node_run.get("TaskOutput")):
            score += 1
        if self._stringify(node_run.get("OutputRef")):
            score += 1
        if self._stringify(node_run.get("TaskOutputRef")):
            score += 1
        return score

    @staticmethod
    def _is_empty_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0
        return False

    @staticmethod
    def _stringify(*values: Any) -> str:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
        return sanitized or "upload"

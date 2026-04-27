from pathlib import Path
from textwrap import dedent

root = Path(r'd:\PythonCode\LAW')


def replace(rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'replace target not found in {rel}: {old[:80]!r}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def replace_block(rel: str, start_marker: str, end_marker: str, new_block: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    path.write_text(text[:start] + new_block + text[end:], encoding='utf-8', newline='\n')

replace(
    'backend/app/services/review_service.py',
    '        return TaskNodeResponse(\n            nodeId=node.node_id,\n            nodeName=node.node_name,\n            status=node.status,\n            startedAt=node.started_at,\n            finishedAt=node.finished_at,\n            input=node.input,\n            output=node.output,\n            error=node.error,\n            nodeType=node.node_type,\n        )\n',
    '        return TaskNodeResponse(\n            nodeId=node.node_id,\n            nodeName=node.node_name,\n            status=node.status,\n            startedAt=node.started_at,\n            finishedAt=node.finished_at,\n            input=node.input,\n            output=node.output,\n            error=node.error,\n            nodeType=node.node_type,\n            display_order=node.display_order,\n        )\n',
)

replace_block(
    'backend/app/services/review_service.py',
    '    async def _materialize_result(',
    '    async def _update_result_extraction_state(',
    dedent('''\
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

''')
)

print('ok')

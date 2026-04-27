from pathlib import Path
from textwrap import dedent

root = Path(r'd:\PythonCode\LAW')


def replace(rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'replace target not found in {rel}: {old[:120]!r}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def replace_block(rel: str, start_marker: str, end_marker: str, new_block: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    path.write_text(text[:start] + new_block + text[end:], encoding='utf-8', newline='\n')

replace(
    'backend/app/providers/tencent_yuanqi_async_provider.py',
    'from app.utils.logger import get_logger\n',
    'from app.utils.logger import get_logger\nfrom app.utils.workflow_display import sort_task_nodes_for_display\n',
)

replace_block(
    'backend/app/providers/tencent_yuanqi_async_provider.py',
    '    async def _fetch_workflow_snapshot(self, task: TaskRecord) -> dict[str, Any]:\n',
    '    async def _describe_node_runs(self, task: TaskRecord, node_runs: list[Any]) -> list[TaskNodeState]:\n',
    dedent('''\
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

''')
)

replace_block(
    'backend/app/providers/tencent_yuanqi_async_provider.py',
    '    async def _describe_node_runs(self, task: TaskRecord, node_runs: list[Any]) -> list[TaskNodeState]:\n',
    '    async def _describe_single_node(\n',
    dedent('''\
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

''')
)

replace_block(
    'backend/app/providers/tencent_yuanqi_async_provider.py',
    '    async def _describe_single_node(\n',
    '    async def _hydrate_node_output_from_refs(self, node_detail: dict[str, Any], *, node_run_id: str) -> None:\n',
    dedent('''\
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

''')
)

replace_block(
    'backend/app/providers/tencent_yuanqi_async_provider.py',
    '    def _build_workflow_groups(\n',
    '    def _derive_group_status(\n',
    dedent('''\
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

''')
)

print('ok')

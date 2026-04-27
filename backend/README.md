# Contract Review Workbench Backend

## Mainline

The production Tencent integration now uses the official workflow async APIs on `https://lke.tencentcloudapi.com`.

Main request flow:

- `CreateWorkflowRun`
- `DescribeWorkflowRun`
- `DescribeNodeRun`
- optional: `StopWorkflowRun`, `ListWorkflowRuns`

The task APIs used by the frontend mainline are:

- `POST /api/contract-review/tasks`
- `GET /api/contract-review/tasks/{taskId}`
- `GET /api/contract-review/tasks/{taskId}/result`

## Provider Selection

Default provider:

```env
REVIEW_PROVIDER=tencent_yuanqi_async
```

Legacy compatibility providers are still present, but they are not the main workflow path:

- `tencent_yuanqi`
- `tencent_yuanqi_sse`

## Required Config

```env
REVIEW_PROVIDER=tencent_yuanqi_async
YUANQI_ASYNC_ENDPOINT=https://lke.tencentcloudapi.com
YUANQI_APP_BIZ_ID=
YUANQI_ASYNC_VERSION=2023-11-30
YUANQI_ASYNC_REGION=ap-guangzhou
YUANQI_ASYNC_RUN_ENV=1
YUANQI_TC_SECRET_ID=
YUANQI_TC_SECRET_KEY=
YUANQI_DEFAULT_VISITOR_BIZ_ID=law_self_user
```

Optional but recommended:

```env
YUANQI_ASYNC_INCLUDE_WORKFLOW_GRAPH=true
YUANQI_ASYNC_POLL_NODE_DETAILS=true
```

Backward compatibility:

- `YUANQI_APP_ID` is still accepted and will be used as the fallback for `YUANQI_APP_BIZ_ID`.
- `tencent_yuanqi` still reads `YUANQI_APP_ID` and `YUANQI_APP_KEY` for the legacy `chat/completions` path.

## Logging

The workflow provider logs these fields on create/describe/node-detail calls:

- `X-TC-Action`
- `AppBizId`
- `WorkflowRunId`
- `RequestId`
- upstream `State`
- `NodeRuns` count
- full error response after sanitization

## Local Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
GET http://127.0.0.1:8000/api/health
```

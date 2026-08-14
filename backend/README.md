# 合同审查工作台后端

基于 FastAPI 的合同审查后端服务。后端负责文件校验与解析、审查任务管理、第三方工作流调用、状态轮询、结果转换和本地持久化。

## 主要功能

- 接收 `.docx` 和 `.pdf` 合同文件
- 支持甲方、乙方两种审查视角
- 创建并查询异步审查任务
- 调用腾讯元器工作流异步 API
- 提供 Mock 模式用于本地开发和联调
- 保存上传文件、任务记录、标准化结果和原始响应
- 返回统一的任务状态、工作流节点和风险审查结果

## 技术栈

- Python 3.11 或更高版本
- FastAPI
- Uvicorn
- Pydantic 2
- HTTPX
- SQLite
- python-docx
- pypdf

## 目录结构

```text
backend/
  app/
    api/            API 路由
    providers/      Mock 与腾讯元器提供方
    repositories/   任务数据访问
    schemas/        请求、响应和领域模型
    services/       审查任务业务逻辑
    utils/          文件、解析和日志工具
    main.py         FastAPI 应用入口
    config.py       环境变量配置
  examples/         Mock 结果示例
  storage/          本地运行数据
  .env.example      环境变量示例
  requirements.txt  Python 依赖
```

## 接口说明

当前主接口如下：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/contract-review/tasks` | 上传合同并创建审查任务 |
| `GET` | `/api/contract-review/tasks/{taskId}` | 查询任务状态和工作流进度 |
| `GET` | `/api/contract-review/tasks/{taskId}/result` | 获取最终审查结果 |

旧版 `/api/reviews` 系列接口仍保留用于兼容，但已标记为废弃，新代码应使用 `/api/contract-review/tasks`。

创建任务使用 `multipart/form-data`：

- `file`：合同文件，支持 `.docx` 和 `.pdf`
- `review_role`：`甲方` 或 `乙方`
- `X-Visitor-Biz-ID`：可选请求头，用于指定腾讯元器访问者标识

## 审查提供方

通过 `REVIEW_PROVIDER` 选择审查提供方。

### 腾讯元器异步工作流

默认主流程：

```env
REVIEW_PROVIDER=tencent_yuanqi_async
```

该模式使用腾讯云官方工作流异步 API：

- `CreateWorkflowRun`
- `DescribeWorkflowRun`
- `DescribeNodeRun`
- 可选的 `StopWorkflowRun`、`ListWorkflowRuns`

### Mock 模式

本地开发、不调用腾讯接口时使用：

```env
REVIEW_PROVIDER=mock
MOCK_FAST_COMPLETE=true
```

Mock 结果来自 `examples/mock_result.json`。

### 兼容提供方

以下旧提供方仍保留，但不作为主流程：

- `tencent_yuanqi`
- `tencent_yuanqi_sse`

## 本地启动

### 1. 创建虚拟环境

```powershell
cd backend
python -m venv .venv
```

### 2. 激活虚拟环境

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止执行激活脚本，也可以不激活，后续直接使用 `.\.venv\Scripts\python.exe`。

### 3. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 4. 创建配置文件

```powershell
Copy-Item .env.example .env
```

仅进行本地联调时，建议先在 `.env` 中使用 Mock：

```env
REVIEW_PROVIDER=mock
MOCK_FAST_COMPLETE=true
```

### 5. 启动服务

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后可访问：

- 健康检查：`http://127.0.0.1:8000/api/health`
- Swagger 文档：`http://127.0.0.1:8000/docs`
- OpenAPI 定义：`http://127.0.0.1:8000/openapi.json`

## 腾讯元器配置

使用 `tencent_yuanqi_async` 时，至少需要配置：

```env
REVIEW_PROVIDER=tencent_yuanqi_async
YUANQI_ASYNC_ENDPOINT=https://lke.tencentcloudapi.com
YUANQI_ASYNC_SERVICE=lke
YUANQI_ASYNC_VERSION=2023-11-30
YUANQI_ASYNC_REGION=ap-guangzhou
YUANQI_ASYNC_RUN_ENV=1
YUANQI_APP_BIZ_ID=
YUANQI_TC_SECRET_ID=
YUANQI_TC_SECRET_KEY=
YUANQI_DEFAULT_VISITOR_BIZ_ID=law_self_user
```

推荐保留以下配置，以便返回工作流和节点详情：

```env
YUANQI_ASYNC_INCLUDE_WORKFLOW_GRAPH=true
YUANQI_ASYNC_POLL_NODE_DETAILS=true
```

兼容规则：

- 未配置 `YUANQI_APP_BIZ_ID` 时，会尝试使用 `YUANQI_APP_ID`。
- 未配置 `YUANQI_TC_SECRET_ID` 和 `YUANQI_TC_SECRET_KEY` 时，会尝试读取 `TC_SECRET_ID` 和 `TC_SECRET_KEY`。
- 旧版 `tencent_yuanqi` 仍使用 `YUANQI_APP_ID`、`YUANQI_APP_KEY` 或 `YUANQI_API_KEY`。

请勿将包含密钥的 `.env` 文件提交到 Git。

## 常用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | 运行环境名称 |
| `BACKEND_PORT` | `8000` | 后端服务端口 |
| `REVIEW_PROVIDER` | `tencent_yuanqi_async` | 审查提供方 |
| `MAX_UPLOAD_SIZE_MB` | `3.5` | 后端文件大小限制；`.env.example` 中配置为 `20` |
| `MOCK_FAST_COMPLETE` | `false` | Mock 任务是否快速完成 |
| `PUBLIC_FILE_BASE_URL` | `http://127.0.0.1:8000` | 上传文件的公开基础地址，主要供旧提供方使用 |
| `YUANQI_REQUEST_TIMEOUT_SECONDS` | `1000` | 腾讯接口请求超时时间 |

## 请求示例

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

创建审查任务：

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/contract-review/tasks `
  -F "file=@D:\contracts\example.docx" `
  -F "review_role=乙方"
```

查询任务状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/contract-review/tasks/{taskId}
```

获取审查结果：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/contract-review/tasks/{taskId}/result
```

## 本地数据

非 Vercel 环境下，运行数据默认保存在 `backend/storage/`：

- `uploads/`：上传的合同文件
- `results/`：标准化审查结果
- `raw_results/`：腾讯工作流和节点原始响应
- `temp/`：临时文件
- `tasks.sqlite3`：任务数据库

这些文件属于本地运行数据，不应作为源码提交。

## 日志

每个请求都会生成或透传 `X-Request-ID`。腾讯元器异步提供方会记录关键调用信息，包括：

- `X-TC-Action`
- `AppBizId`
- `WorkflowRunId`
- `RequestId`
- 上游任务状态
- 工作流节点数量
- 脱敏后的错误响应

排查问题时可使用 `RequestId` 和 `WorkflowRunId` 关联本地日志与腾讯云请求。

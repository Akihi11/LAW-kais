# 合同审查工作台 Frontend

基于 Next.js 14、TypeScript、Tailwind CSS 和 Zustand 的前端项目，用于联调现有 FastAPI Mock 后端，完成合同上传、阶段级进度查看、结果总览展示和逐条重点问题定位。

## 项目说明

本项目只负责前端展示与联调，不修改后端业务逻辑、不新增后端接口、不接入真实腾讯元器。

当前实现的能力包括：

- 上传合同文件并选择审查视角（甲方 / 乙方）
- 调用现有 `POST /api/reviews` 创建审查任务
- 在结果总览页轮询任务状态与最终结果
- 以阶段级进度展示审查流程
- 展示统一结果 JSON 中的基本信息、结论、风险统计与完整报告
- 在逐条重点问题页中实现“问题列表 -> 合同原文”联动定位

## 技术栈

- Next.js 14
- TypeScript
- Tailwind CSS
- Zustand
- Fetch API

## 目录结构

```text
frontend/
  app/
    review/
      new/page.tsx
      [taskId]/
        overview/page.tsx
        issues/page.tsx
    globals.css
    layout.tsx
    page.tsx
  components/
    common/
    issues/
    overview/
    upload/
    workflow/
  lib/
    api.ts
    constants.ts
    error-messages.ts
    review-helpers.ts
    types.ts
    useReviewTask.ts
  stores/
    reviewStore.ts
  .env.local.example
  .gitignore
  next.config.mjs
  package.json
  package-lock.json
  postcss.config.js
  tailwind.config.ts
  tsconfig.json
```

## 交付物要求

源码包只保留源码与说明文件，不应包含以下目录：

- `.next/`
- `node_modules/`

这两个目录已加入 `.gitignore`，本地构建和安装依赖后会生成，但不应进入最终交付包。

## 页面说明

### `/review/new`

上传合同文件页，包含：

- 文件上传区域
- 已选文件名展示
- 审查视角切换
- 开始审查按钮
- 右侧工作流调用 / 执行状态区域

### `/review/[taskId]/overview`

结果总览页，包含：

- 阶段级进度展示
- 合同基本信息卡片
- 总体结论框
- 风险统计卡片
- 完整报告正文

### `/review/[taskId]/issues`

逐条重点问题页，包含：

- 左侧合同原文
- 右侧风险筛选器与问题列表
- 问题详情
- 点击问题后自动定位并高亮左侧相关条款

## 后端联调方式

前端只调用现有统一契约接口：

- `POST /api/reviews`
- `GET /api/reviews/{taskId}`
- `GET /api/reviews/{taskId}/result`

为了避免改动后端 CORS 或接口路径，前端使用 Next.js `rewrites` 将本地 `/api/*` 代理到后端服务地址。

默认代理目标由 `BACKEND_ORIGIN` 控制：

```env
BACKEND_ORIGIN=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_PATH=/api
```

## 环境变量

在 `frontend/` 下创建 `.env.local`：

```env
BACKEND_ORIGIN=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_PATH=/api
```

变量说明：

- `BACKEND_ORIGIN`：FastAPI 后端地址，默认联调本地 Mock 后端
- `NEXT_PUBLIC_API_BASE_PATH`：前端内部请求使用的基础路径，默认保持 `/api`

## 状态管理策略

Zustand 仅持久化以下字段：

- `taskId`
- `currentFilter`
- `expandedIssueId`

以下状态不做持久化，页面刷新后会重新向后端拉取：

- `taskState`
- `reviewStatus`
- `progress`
- `result`
- `error`

这样可以避免把合同原文、完整报告和旧任务状态长期写入 localStorage，降低容量风险和缓存污染。

## 轮询策略

`useReviewTask` 的轮询行为如下：

- 任务状态为 `failed` 时立即停止轮询
- 成功拿到最终结果后立即停止轮询
- 结果已经成功获取后不会重复请求 `GET /result`
- 增加最大轮询次数保护，避免无限轮询

## 错误提示策略

页面会基于后端业务错误码展示明确提示，至少覆盖：

- `task_not_found`
- `result_not_ready`
- `invalid_file_type`
- `file_too_large`
- `invalid_review_role`
- `provider_not_implemented`
- `internal_error`

## 运行方式

### 1. 启动后端 Mock

先在 `backend/` 中启动现有 FastAPI 服务，确保以下接口可访问：

- `GET /api/health`
- `POST /api/reviews`
- `GET /api/reviews/{taskId}`
- `GET /api/reviews/{taskId}/result`

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 配置环境变量

```bash
cp .env.local.example .env.local
```

Windows PowerShell 可使用：

```powershell
Copy-Item .env.local.example .env.local
```

### 4. 启动前端

```bash
npm run dev
```

默认访问地址：

- `http://127.0.0.1:3000/review/new`

## 本地联调流程

1. 打开 `http://127.0.0.1:3000/review/new`
2. 选择 `.docx` 或 `.pdf` 合同文件
3. 选择甲方或乙方审查视角
4. 点击“开始审查”
5. 成功创建任务后自动跳转至结果总览页
6. 在任务完成前查看阶段级进度
7. 任务完成后查看统一结果总览
8. 点击进入逐条重点问题页
9. 在右侧选择问题并联动定位左侧合同原文

## 说明边界

本轮前端实现明确不包含：

- 后端改造
- 新增接口
- 登录注册
- 多用户与权限体系
- 历史任务列表
- 导出 PDF / Word
- 真实腾讯元器接入
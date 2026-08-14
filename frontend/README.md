# 合同审查工作台前端

基于 Next.js 14、TypeScript、Tailwind CSS 和 Zustand 构建的合同审查前端。前端负责用户登录、合同上传、任务进度展示、审查结果总览和风险问题定位，并通过 Next.js 代理调用 FastAPI 后端。

## 主要功能

- 使用本地管理员账号登录
- 在上传页一键查看内置预设报告，无需等待后端审查
- 上传 `.docx` 或 `.pdf` 合同文件
- 选择甲方或乙方审查视角
- 创建合同审查任务并轮询任务状态
- 展示工作流阶段、节点状态和执行进度
- 展示合同基本信息、总体结论、风险统计和完整报告
- 按风险等级筛选问题并定位合同原文

## 技术栈

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Zustand
- Fetch API

## 目录结构

```text
frontend/
  app/
    login/                       登录页
    review/new/                  新建审查任务
    review/[taskId]/overview/    审查结果总览
    review/[taskId]/issues/      风险问题详情
  components/                    页面组件
  images/                        页面图片
  lib/                           API、类型和通用逻辑
  stores/                        Zustand 状态管理
  middleware.ts                 登录状态校验
  next.config.mjs               Next.js 配置和后端代理
  package.json                  依赖与脚本
```

## 环境要求

- Node.js 18.17 或更高版本，推荐使用 Node.js 20 LTS
- npm
- 已启动的后端服务，默认地址为 `http://127.0.0.1:8000`

## 环境变量

复制环境变量示例文件：

```powershell
cd frontend
Copy-Item .env.local.example .env.local
```

默认配置如下：

```env
BACKEND_ORIGIN=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_PATH=/api
```

- `BACKEND_ORIGIN`：FastAPI 后端地址，由 Next.js 服务端代理使用。
- `NEXT_PUBLIC_API_BASE_PATH`：浏览器请求的 API 基础路径，通常保持为 `/api`。

修改 `.env.local` 后需要重新启动前端服务。

## 安装与启动

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

服务启动后访问：

- 前端首页：`http://127.0.0.1:3000`
- 登录页面：`http://127.0.0.1:3000/login`

本地默认账号：

```text
用户名：admin
密码：admin
```

登录成功后进入 `/review/new`。页面中的“查看预设报告”按钮会直接打开内置报告，不调用后端审查接口。

> Windows 环境中，如果执行 `npm` 没有任何输出，可以改用 `npm.cmd`。可通过 `Get-Command npm -All` 检查当前实际调用的 npm 程序。

## 页面路由

| 路径                             | 说明                         |
| -------------------------------- | ---------------------------- |
| `/login`                         | 管理员登录                   |
| `/review/new`                    | 上传合同并创建审查任务       |
| `/review/[taskId]/overview`      | 查看进度、风险统计和完整报告 |
| `/review/[taskId]/issues`        | 筛选风险问题并定位合同条款   |

根路径 `/` 会根据登录状态跳转到登录页或新建审查页。

## 后端接口

前端当前使用以下接口：

```text
POST /api/contract-review/tasks
GET  /api/contract-review/tasks/{taskId}
GET  /api/contract-review/tasks/{taskId}/result
```

开发环境下，请求会由 `next.config.mjs` 转发到 `BACKEND_ORIGIN`，因此浏览器不需要直接跨域访问后端。

## 文件限制

- 支持格式：`.docx`、`.pdf`
- 前端单文件限制：3.5 MB
- 审查视角：甲方、乙方

后端的 `MAX_UPLOAD_SIZE_MB` 应设置为不小于前端限制的值。

## 常用命令

```powershell
# 开发模式
npm.cmd run dev

# 生产构建
npm.cmd run build

# 启动生产构建
npm.cmd run start
```

## 本地联调流程

1. 启动后端并确认 `http://127.0.0.1:8000/api/health` 返回正常。
2. 启动前端并打开 `http://127.0.0.1:3000`。
3. 使用 `admin / admin` 登录并进入上传页。
4. 点击“查看预设报告”，可立即查看预存的结果总览和逐条重点问题。
5. 需要真实审查时，上传 `.docx` 或 `.pdf` 合同。
6. 选择审查视角并点击“开始审查”。
7. 等待任务完成后查看真实结果总览和风险问题详情。

## 常见问题

### 前端页面打不开

检查 `3000` 端口是否已经监听：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 3000
```

如果没有监听，请在 `frontend/` 目录执行：

```powershell
npm.cmd run dev
```

### 页面能打开，但接口请求失败

1. 检查后端是否在 `8000` 端口运行。
2. 检查 `.env.local` 中的 `BACKEND_ORIGIN`。
3. 修改环境变量后重启前端。
4. 访问 `http://127.0.0.1:3000/api/health`，确认前端代理能够连接后端。

### 构建失败

删除本地构建缓存并重新安装依赖后再构建：

```powershell
Remove-Item -Recurse -Force .next
npm.cmd install
npm.cmd run build
```

`node_modules/`、`.next/` 和 `.env.local` 均不应提交到 Git。

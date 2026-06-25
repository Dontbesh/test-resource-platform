# 一期工程骨架与首个端到端 Tracer

Status: complete

Date: 2026-06-23

## Goal

基于已接受的技术选型 `FastAPI + PostgreSQL + Vue 3`，创建新测试资源平台的最小工程骨架，并跑通第一条可验证的端到端链路。

## Scope

本计划只覆盖工程骨架和第一个 tracer，不实现完整一期业务。

包括：

- 在 `agent-assisted-test-platform/` 同级创建新平台源码目录 `test-resource-platform/`。
- 后端 FastAPI 项目骨架。
- PostgreSQL 与 SQLAlchemy/Alembic 基线。
- Vue 3 + TypeScript + Vite 前端骨架。
- Docker Compose 本地启动。
- 统一 `/api/v1` 路由前缀。
- 健康检查或最小认证链路。
- OpenAPI 输出。
- 后端第一条 API 测试。
- 前端第一条页面或 API 调用验证。

## Non-goals

- 不实现完整用户管理。
- 不实现完整 RBAC。
- 不实现资源池、机器台账、租约、凭据、CSV 导入和审计。
- 不接入旧 `radiatest` 数据库或服务。
- 不引入消息队列、微服务或 Kubernetes。

## Confirmed Decisions

- 当前 `agent-assisted-test-platform/` 继续保存项目管理文档，平台源码放在同级独立目录 `test-resource-platform/`。
- 第一条 tracer 使用 `/api/v1/health` 健康检查，而不是最小登录。
- 后端采用 Python 3.12 + FastAPI + Pydantic + SQLAlchemy 2.x + Alembic。
- 数据库采用 PostgreSQL。
- 前端采用 Vue 3 + TypeScript + Vite + Vue Router + Pinia + Naive UI。
- 测试采用 pytest + httpx/TestClient，后续 E2E 使用 Playwright。
- 部署采用 Docker Compose。
- 核心业务必须通过 `/api/v1` API 暴露，Web 不绕过业务 API。

## Architecture Sketch

```text
web-vue
  -> /api/v1
api-fastapi
  -> app modules
  -> SQLAlchemy session
postgres
```

第一条 tracer 选择 `/api/v1/health`：

- 前端首页请求健康检查。
- 后端返回 API 状态、版本和数据库连通状态。
- 测试验证接口返回稳定结构。
- OpenAPI 能展示该接口。

最小登录接口后移到用户与 RBAC 阶段，避免工程骨架阶段提前引入密码散列、用户表和 token 策略。

## Tasks

- [x] 创建新代码仓或源码目录结构。
- [x] 初始化后端 FastAPI 应用和 `/api/v1/health`。
- [x] 接入 SQLAlchemy 和 PostgreSQL 连接配置。
- [x] 初始化 Alembic，并创建迁移元数据基线。
- [x] 编写后端健康检查 API 测试。
- [x] 初始化 Vue 3 + TypeScript + Vite 项目。
- [x] 接入 Vue Router、Pinia 和 Naive UI。
- [x] 创建首页，请求并展示 `/api/v1/health` 状态。
- [x] 创建 Docker Compose，定义 api、web、postgres。
- [x] 补充 README 启动和测试命令。
- [x] 配置 FastAPI OpenAPI 输出到 `/api/v1/openapi.json`。

## Acceptance Scenarios

- 新成员能按 README 在本地启动前后端和 PostgreSQL。
- `GET /api/v1/health` 返回稳定 JSON，且包含数据库连通状态。
- 后端测试能在干净环境运行并通过。
- 前端页面能通过 API 显示后端健康状态。
- OpenAPI 文档能访问并包含 `/api/v1/health`。

## Verification Commands

已执行：

```text
backend/.venv/Scripts/python -m pytest
backend/.venv/Scripts/python -m ruff check .
frontend: vue-tsc --noEmit
frontend: vite build
```

未执行：

```text
docker compose config
docker compose up --build
```

原因：当前机器未安装或未暴露 `docker` 命令。

## Current Progress

- 技术选型 ADR 已接受：`docs/adr/0006-phase-1-technology-stack-and-architecture.md`。
- 工程骨架已创建：`../test-resource-platform/`。
- 后端健康检查测试通过。
- 后端 ruff 检查通过。
- 前端类型检查通过。
- 前端生产构建通过；Vite 提示首包 chunk 大于 500 kB，骨架阶段暂不拆包。
- Docker Compose 文件已创建。
- 2026-06-25 已在实验室 Linux 服务器 clone 项目并成功启动，前端页面可正常显示健康检查信息。
- 独立 Audit 已完成：无 P0/P1；P2 为 README 缺少 Linux / `docker-compose` 兼容命令，已补充。

## Open Questions

- 暂无。

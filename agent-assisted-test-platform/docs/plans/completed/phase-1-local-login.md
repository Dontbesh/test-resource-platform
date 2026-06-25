# 本地账号登录最小闭环

Status: complete

Date: 2026-06-25

## Goal

在现有 `FastAPI + PostgreSQL + Vue 3` 工程骨架上，实现 Web 登录最小闭环：初始化第一个 `ADMIN` 用户，用户可以登录、查询当前用户、登出，前端未登录时跳转登录页，登录后进入后台首页。

## Scope

包括：

- `users` 表和 Alembic 迁移。
- 安全密码散列。
- 数据库为空时初始化第一个 `ADMIN`。
- HttpOnly Cookie 会话。
- 登录、当前用户、登出 API。
- 前端登录页。
- 前端当前用户状态。
- 前端路由守卫。
- 后端登录 API 测试。

## Non-goals

- 不实现 PAT。
- 不实现完整用户管理页面。
- 不实现 ADMIN 创建、禁用、重置其他账号。
- 不实现完整接口级 RBAC 权限矩阵。
- 不实现资源池、机器台账、租约、凭据或审计。
- 不接入 Gitee OAuth、SSO 或外部身份系统。

## Confirmed Decisions

- Web 登录使用 HttpOnly Cookie 会话，不把访问令牌保存到前端 `localStorage`。
- PAT 后续单独实现，用于脚本或外部客户端调用 API。
- 如果数据库里还没有任何用户，使用环境变量初始化第一个 `ADMIN`。
- 初始化 ADMIN 只在用户表为空时执行；一旦已有用户，不再自动覆盖或重置密码。

## Proposed API

```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout
```

### `POST /api/v1/auth/login`

请求：

```json
{
  "username": "admin",
  "password": "Admin@123456"
}
```

成功：

- 设置 HttpOnly Cookie。
- 返回当前用户公开信息。

失败：

- 用户不存在、密码错误、用户禁用都返回稳定错误码。

### `GET /api/v1/auth/me`

成功：

- 返回当前登录用户公开信息。

失败：

- 未登录返回 `401`。
- 用户已禁用返回 `401` 或 `403`，实现时固定一种稳定结果。

### `POST /api/v1/auth/logout`

成功：

- 清除 Cookie。
- 返回空成功响应。

## Backend Architecture

新增模块：

| Module | Responsibility |
|---|---|
| `app.identity` | 用户模型、角色枚举、密码散列、用户查询 |
| `app.auth` | 登录、会话签发、会话读取、当前用户依赖 |
| `app.bootstrap` | 初始化第一个 ADMIN |

路由层只负责请求和响应。登录校验、密码验证、Cookie 签发、当前用户读取隐藏在应用层函数中。

## Frontend Architecture

新增内容：

- `LoginView.vue`
- `DashboardView.vue`
- `src/api/auth.ts`
- `src/stores/auth.ts`
- 路由守卫：未登录访问后台页时跳转登录页。

前端只做体验层保护。后端仍是最终认证来源。

## Environment Variables

```text
SESSION_SECRET_KEY=change-me
SESSION_COOKIE_NAME=trp_session
SESSION_MAX_AGE_SECONDS=28800
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=Admin@123456
```

`INITIAL_ADMIN_PASSWORD` 只用于首次初始化。生产环境必须修改默认值。

## Tasks

- [x] 添加后端密码散列和会话签名。
- [x] 创建 `users` 表模型和迁移。
- [x] 实现数据库 session 依赖。
- [x] 实现密码散列和校验。
- [x] 实现初始化第一个 `ADMIN`。
- [x] 实现登录、当前用户、登出 API。
- [x] 编写登录 API 测试。
- [x] 更新 Docker Compose 和 `.env.example`。
- [x] 实现前端 auth API 和 Pinia store。
- [x] 实现登录页、后台首页和路由守卫。
- [x] 更新 README。

## Acceptance Scenarios

- 空数据库启动后能初始化第一个 `ADMIN`。
- 使用正确用户名和密码可以登录。
- 登录成功后浏览器持有 HttpOnly Cookie。
- 登录后访问 `/api/v1/auth/me` 能得到当前用户。
- 密码错误不能登录。
- 登出后 `/api/v1/auth/me` 返回未登录。
- 前端未登录访问后台页跳转登录页。
- 前端登录成功后进入后台首页。

## Verification Commands

```text
backend/.venv/Scripts/python -m pytest
backend/.venv/Scripts/python -m ruff check .
frontend: npm run typecheck
frontend: npm run build
docker compose up --build
```

## Current Progress

- Clarify 已确认：PAT 不在本轮做。
- Clarify 已确认：Web 登录使用 HttpOnly Cookie 会话。
- Clarify 已确认：数据库为空时用环境变量初始化第一个 `ADMIN`。
- 后端登录 API、用户模型、初始化 ADMIN、会话 Cookie 已实现。
- 前端登录页、后台首页和路由守卫已实现。
- README 已补充登录测试方式。
- 验证已通过：后端 pytest、后端 ruff、前端 typecheck、前端 build、Alembic SQLite 临时迁移。
- Vite 仍提示首包 chunk 大于 500 kB，属于 Naive UI 骨架阶段已知警告。
- 独立 Audit 已完成：无 P0/P1；三个 P2 已修复。
  - 运行时不再默认 `create_all` 绕过 Alembic；测试通过 `AUTO_CREATE_SCHEMA=true` 单独启用。
  - Cookie `secure` 改为 `SESSION_COOKIE_SECURE` 环境变量控制。
  - 前端 Docker 改为复制 `package-lock.json` 并使用 `npm ci`。

## Open Questions

- 暂无。

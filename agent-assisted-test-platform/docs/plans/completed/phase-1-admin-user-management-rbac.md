# 一期 ADMIN 用户管理与基础 RBAC

Status: complete

Date: 2026-06-25

## Goal

在已完成本地登录闭环的基础上，实现 `ADMIN` 用户管理与基础接口级 RBAC，让管理员可以创建、禁用和重置 `TSE` / `TE` 用户，并为后续资源池、机器台账、租约和凭据功能建立统一的角色校验入口。

## Scope

包括：
- 后端新增基础授权模块，用于声明“当前用户必须具备某些角色”。
- 后端新增用户管理 API。
- `ADMIN` 可以创建 `TSE` / `TE` / `ADMIN` 用户。
- `ADMIN` 可以查看用户列表。
- `ADMIN` 可以禁用用户。
- `ADMIN` 可以重置用户密码。
- 非 `ADMIN` 调用用户管理 API 时返回稳定的 `403` 错误。
- 被禁用用户不能继续登录；已有会话访问 `/api/v1/auth/me` 时也会失效。
- 前端新增用户管理页面和入口，仅 `ADMIN` 可见。
- 后端补充用户管理与 RBAC API 测试。

## Non-goals

不包括：
- PAT 创建、列表、过期和撤销。
- 复杂权限矩阵文档全量落地。
- 资源池、机器台账、租约、凭据、CSV 导入或审计。
- 自助注册、用户自助改密、找回密码。
- 多组织、多租户或外部身份系统。
- 用户删除。禁用用于保留历史归属和后续审计关系。

## Confirmed Decisions

- 本轮继续不做 PAT。
- 用户管理接口只允许 `ADMIN` 调用。
- 禁用用户而不是删除用户，避免后续租约、审计等历史记录失去操作者。
- 真实授权必须在后端完成；前端只做菜单隐藏和体验层保护。
- 新授权入口应该能被后续资源池、机器、租约接口复用，避免每个路由手写角色判断。

## Proposed API

```text
GET  /api/v1/users
POST /api/v1/users
POST /api/v1/users/{user_id}/disable
POST /api/v1/users/{user_id}/reset-password
```

### `GET /api/v1/users`

返回用户列表，按 `id` 升序。

成功响应：
```json
[
  {
    "id": 1,
    "username": "admin",
    "role": "ADMIN",
    "is_active": true
  }
]
```

### `POST /api/v1/users`

请求：
```json
{
  "username": "alice",
  "password": "Alice@123456",
  "role": "TE"
}
```

成功：
- 创建启用状态的用户。
- 返回用户公开信息。

失败：
- 用户名重复返回 `409 USERNAME_ALREADY_EXISTS`。
- 非 `ADMIN` 返回 `403 FORBIDDEN`。

### `POST /api/v1/users/{user_id}/disable`

成功：
- 将用户标记为 `is_active=false`。
- 返回用户公开信息。

失败：
- 用户不存在返回 `404 USER_NOT_FOUND`。
- 非 `ADMIN` 返回 `403 FORBIDDEN`。

### `POST /api/v1/users/{user_id}/reset-password`

请求：
```json
{
  "password": "NewPassword@123456"
}
```

成功：
- 重置目标用户密码。
- 返回 `204`。

失败：
- 用户不存在返回 `404 USER_NOT_FOUND`。
- 非 `ADMIN` 返回 `403 FORBIDDEN`。

## Backend Design

新增或扩展模块：

| Module | Responsibility |
|---|---|
| `app.auth.authorization` | 提供角色依赖函数，例如要求当前用户角色属于给定集合 |
| `app.api.v1.users` | 用户管理路由，只负责请求解析、调用身份模块和返回响应 |
| `app.identity.service` | 用户查询、列表、创建、禁用、重置密码等身份业务操作 |
| `app.identity.schemas` | 用户管理请求和响应模型 |

路由层保持薄：
- 通过依赖获取当前 `ADMIN`。
- 调用 `identity.service`。
- 将领域结果映射为 HTTP 响应。

## Frontend Design

新增：
- `src/api/users.ts`
- `src/views/UserManagementView.vue`
- `/users` 路由，要求登录且角色为 `ADMIN`

调整：
- 后台首页增加 `ADMIN` 可见的“用户管理”入口。
- 非 `ADMIN` 直接访问 `/users` 时跳回 dashboard 或展示无权限状态；最终权限仍以后端 `403` 为准。

## Tasks

- [x] RED/GREEN: 后端测试覆盖 `ADMIN` 可以创建用户。
- [x] RED/GREEN: 后端测试覆盖非 `ADMIN` 不能访问用户管理接口。
- [x] RED/GREEN: 后端测试覆盖 `ADMIN` 可以禁用用户，且禁用后不能登录/继续读取当前用户。
- [x] RED/GREEN: 后端测试覆盖 `ADMIN` 可以重置用户密码。
- [x] 实现用户管理 API 路由、schema 和服务函数。
- [x] 实现前端用户管理 API client。
- [x] 实现前端用户管理页面和 dashboard 入口。
- [x] 运行后端 pytest、ruff，前端 typecheck、build。
- [x] 更新 README 或计划进度，记录测试结果。

## Acceptance Scenarios

- `ADMIN` 登录后可以创建一个 `TE` 用户。
- 新建 `TE` 用户可以登录。
- `TE` 调用 `/api/v1/users` 返回 `403`。
- `ADMIN` 可以禁用该 `TE` 用户。
- 被禁用的 `TE` 不能再次登录。
- 如果该 `TE` 已经持有会话，访问 `/api/v1/auth/me` 返回 `401`。
- `ADMIN` 可以重置一个用户的密码。
- 被重置密码的用户只能用新密码登录。
- 前端 `ADMIN` 可以进入用户管理页并看到用户列表。

## Verification Commands

```text
backend/.venv/Scripts/python -m pytest
backend/.venv/Scripts/python -m ruff check .
frontend: npm run typecheck
frontend: npm run build
docker compose up --build
```

## Current Progress

- Goal 已确认：继续不做 PAT，先做 `ADMIN` 用户管理与基础 RBAC。
- 已确认现有代码具备 `UserRole`、`get_current_user`、`create_user`、登录会话和前端路由守卫，可在此基础上扩展。
- 后端已新增 `app.auth.authorization.require_roles` / `require_admin`，作为后续业务接口复用的角色校验入口。
- 后端已新增 `/api/v1/users` 用户管理接口，覆盖列表、创建、禁用和重置密码。
- 前端已新增 `/users` 用户管理页面，dashboard 中仅 `ADMIN` 可见入口，路由守卫也限制 `ADMIN` 访问。
- 验证已通过：后端 `pytest` 8 passed、后端 `ruff check .`、前端 `npm run typecheck`、前端 `npm run build`。
- 独立 Audit 发现 3 个 P2，均已修复：
  - 补充非 `ADMIN` 访问所有用户管理接口的 `403` 回归测试。
  - 补充禁用/重置不存在用户的 `404 USER_NOT_FOUND` 测试。
  - 捕获重复用户名并发创建时可能出现的数据库 `IntegrityError`，统一映射为 `409 USERNAME_ALREADY_EXISTS`。
- 已知构建提示：Vite 仍提示首包 chunk 大于 500 kB，原因与 Naive UI 骨架阶段引入量有关，本轮不处理拆包。

## Open Questions

- 暂无。

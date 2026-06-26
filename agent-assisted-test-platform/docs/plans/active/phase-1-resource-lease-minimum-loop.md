# Phase 1 Resource Lease Minimum Loop

Status: active

## Goal

实现资源租约最小闭环：登录用户可以从一台可用机器创建资源租约，在“我的租约”中查看自己的租约，并按不可变 `lease_id` 主动释放自己的有效租约。

这个目标补齐一期平台最核心的业务路径：

1. 管理员或 TSE 维护资源池和机器台账。
2. TE/TSE/ADMIN 选择一台可用机器并立即占用。
3. 平台生成独立资源租约，而不是把占用人和时间写回机器表。
4. 用户按 `lease_id` 释放自己的租约。

## Scope

- 新增后端资源租约数据表与领域模型。
- 新增占用、查看我的租约、释放接口。
- 占用时校验机器存在、资源池启用、机器启用、同一时刻无有效租约。
- 使用服务端时间计算开始时间和结束时间。
- 使用不可变 `lease_id` 作为释放入口。
- 过期租约采用惰性到期：访问租约接口或尝试占用时，把已超过结束时间的有效租约标记为 `EXPIRED`。
- 前端资源台账页增加“占用”入口，并增加“我的租约”视图与“释放”操作。
- 覆盖后端关键行为测试，并运行现有后端和前端检查。

## Non-Goals

- 不做未来时段预约。
- 不做租约延期。
- 不做管理员强制释放。
- 不做 PAT、飞书、LLM 或外部身份绑定。
- 不做机器凭据查看或凭据审计。
- 不做租约事件查询 API。
- 不做批量占用或自动选择 N 台机器。
- 不引入后台任务队列；本轮只做惰性到期。

## Confirmed Decisions

- “占用”指立即创建资源租约，不是预约。
- 一台机器同一时刻最多存在一条有效资源租约。
- 释放租约必须使用 `lease_id`，不使用 `resource_code` 猜测当前租约。
- 占用成功不返回 SSH/BMC 密码。
- 所有已登录用户都可以占用可用机器和释放自己的租约；资源台账维护权限仍由 `ADMIN`/`TSE` 控制。
- 资源池停用或机器停用后，该机器不能被新建租约占用。

## Architecture

### Backend module

新增 `app.leases` 模块，保持和现有 `app.resources`、`app.identity` 平级：

- `models.py`: `ResourceLease` 与 `LeaseStatus`。
- `schemas.py`: 占用请求、租约响应。
- `service.py`: 创建租约、列出我的租约、释放租约、惰性到期。
- `api/v1/resource_leases.py`: HTTP 路由与错误码转换。

这个模块的外部接口保持小而深：路由只调用租约服务；“机器是否可占用”“有效租约唯一性”“过期处理”集中在租约服务中，避免前端或机器模块复制判断。

### Data model

新增 `resource_leases` 表：

- `id`: 数据库主键。
- `lease_id`: 不可变租约编号，唯一。
- `machine_id`: 指向 `machine_resources.id`。
- `user_id`: 指向 `users.id`。
- `purpose`: 占用用途。
- `status`: `ACTIVE` / `RELEASED` / `EXPIRED`。
- `started_at`: 服务端创建时间。
- `expires_at`: 服务端计算的结束时间。
- `released_at`: 主动释放时间，可空。
- `created_at` / `updated_at`: 审计基础时间戳。

数据库层增加“同一机器最多一条 ACTIVE 租约”的唯一索引，配合服务层校验处理并发占用冲突。

### API

- `POST /api/v1/leases`
  - 请求：`resource_code`, `duration_minutes`, `purpose`
  - 响应：资源租约、机器简要信息、租期
  - 失败：机器不存在、资源池停用、机器停用、租期非法、已有有效租约
- `GET /api/v1/leases/my`
  - 返回当前登录用户的租约，按创建时间倒序。
- `POST /api/v1/leases/{lease_id}/release`
  - 只允许租约所有者释放。
  - 已释放或已到期租约不能重复释放。

### Frontend

复用现有 `/resources` 页面：

- 机器列表增加“占用”按钮。
- 点击后弹窗填写占用时长和用途。
- 增加“我的租约”标签页，展示 `lease_id`、机器、用途、状态、开始时间、结束时间。
- ACTIVE 且属于当前用户的租约显示“释放”按钮。

## Task Checklist

- [x] 后端 RED/GREEN 1：用户可以占用一台可用机器并获得 `lease_id`。
- [x] 后端 RED/GREEN 2：同一机器已有 ACTIVE 租约时，第二次占用返回稳定冲突错误。
- [x] 后端 RED/GREEN 3：资源池停用或机器停用时不能新建租约。
- [x] 后端 RED/GREEN 4：用户可以查看自己的租约。
- [x] 后端 RED/GREEN 5：用户只能释放自己的 ACTIVE 租约。
- [x] 后端 RED/GREEN 6：过期 ACTIVE 租约会惰性转为 `EXPIRED`，不再阻塞新租约。
- [x] 前端：增加租约 API 客户端、占用弹窗、我的租约列表和释放按钮。
- [x] 文档：更新 README 当前能力边界与接口说明。
- [x] 验证：运行后端测试、ruff、前端 typecheck、前端 build。
- [ ] 提交：通过验证后创建本地 checkpoint commit。

## Acceptance Scenarios

1. 登录用户选择一台资源池启用且机器状态为 `ACTIVE` 的机器，输入用途和租期后，占用成功并获得 `lease_id`。
2. 另一位用户尝试占用同一台仍处于 ACTIVE 租约中的机器时，收到 `RESOURCE_ALREADY_LEASED`。
3. 资源池被停用后，该资源池内机器不能被占用。
4. 机器被停用后，该机器不能被占用。
5. 用户可以在“我的租约”看到自己的租约。
6. 用户可以释放自己的 ACTIVE 租约，释放后该机器可以再次被占用。
7. 用户不能释放别人的租约。
8. 已到期租约不再阻塞同一机器的新占用。

## Verification Commands

Backend:

```powershell
cd D:\Desktop\radiaTest-2\intern-projects-main-agent-assisted-test-platform\test-resource-platform\backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Frontend:

```powershell
cd D:\Desktop\radiaTest-2\intern-projects-main-agent-assisted-test-platform\test-resource-platform\frontend
npm run typecheck
npm run build
```

Migration smoke test:

```powershell
cd D:\Desktop\radiaTest-2\intern-projects-main-agent-assisted-test-platform\test-resource-platform\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Current Progress

- Clarify complete: 本轮只做立即占用、查看我的租约、释放自己的租约。
- Architect complete: 租约作为独立模块和独立表实现，不回写机器表保存占用关系。
- Solve complete: 后端租约 API、前端资源台账租约入口和 README 已实现。
- Verification complete: `pytest` 19 passed；`ruff check .` passed；`npm.cmd run typecheck` passed；`npm.cmd run build` passed；SQLite Alembic `upgrade head` passed。

## Open Questions

- 暂定单次租期范围为 `1..1440` 分钟。若后续需要更长租期，再通过配置项扩展。

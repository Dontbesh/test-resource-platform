# Phase 1 Lease Events And Controls

Status: ready-for-audit

## Goal

补齐一期资源租约的控制与追踪能力：登录用户可以延期自己的有效资源租约，`ADMIN` / `TSE` 可以强制释放他人的有效资源租约，平台会为占用、延期、释放、到期和强制释放持久化租约事件，并提供可查询的事件 API。

这轮目标是把“能占用和释放机器”推进到“租约状态变化可追踪、冲突可处理、延期不会误作用到下一位使用人”。

## Scope

- 新增租约事件数据模型，记录资源租约关键变化。
- 占用成功时写入 `CREATED` 租约事件。
- 本人释放成功时写入 `RELEASED` 租约事件。
- 惰性到期处理时写入 `EXPIRED` 租约事件。
- 新增本人延期接口，只有租约所有者可以延期自己的 `ACTIVE` 租约。
- 延期接口使用不可变 `lease_id`，请求只接收 `duration_minutes`，由服务端计算新的结束时间。
- 新增 `ADMIN` / `TSE` 强制释放接口，允许处理他人的 `ACTIVE` 租约。
- 强制释放成功时写入 `FORCE_RELEASED` 租约事件。
- 新增租约事件查询接口，首版仅 `ADMIN` / `TSE` 可查。
- 前端“我的租约”增加延期入口；`ADMIN` / `TSE` 增加强制释放入口。
- 补充后端行为测试，重点覆盖权限、稳定错误码、旧租约保护和事件产生。

## Non-Goals

- 不做未来时段预约。
- 不做管理员代别人延期。
- 不做租约审批流。
- 不做通知系统。
- 不做 PAT、CSV 导入、飞书、LLM 或外部身份绑定。
- 不做写 API 幂等键，本轮只通过 `lease_id` 防止旧请求作用到新租约。
- 不做通用审计查询页面；本轮只做租约事件查询。
- 不引入后台任务队列；到期事件仍通过现有惰性到期流程产生。

## Confirmed Decisions

- 本人可以延期自己的 `ACTIVE` 资源租约。
- `ADMIN` / `TSE` 可以强制释放他人的 `ACTIVE` 资源租约。
- `TE` 不能强制释放任何租约。
- 本轮不做“管理员代别人延期”。
- 释放、延期和强制释放都必须使用 `lease_id`，不能用 `resource_code` 猜测当前租约。
- 过期、已释放、已强制释放的租约不能再次延期、释放或强制释放。
- 租约事件是租约状态变化历史，不替代 `resource_leases.status` 当前状态。

## Architecture

### Backend module

继续深化现有 `app.leases` 模块：

- `models.py`: 新增 `ResourceLeaseEvent` 与 `LeaseEventType`。
- `schemas.py`: 新增延期请求、强制释放响应复用、事件公开响应。
- `service.py`: 增加 `extend_resource_lease`、`force_release_resource_lease`、`list_lease_events`，并让创建、释放、到期流程写事件。
- `api/v1/resource_leases.py`: 增加延期、强制释放和事件查询路由。

路由层继续保持薄，只负责鉴权、请求解析、错误码映射和提交事务。租约状态判断、事件写入和过期处理集中在 `app.leases.service`，避免前端或多个路由复制规则。

### Data model

新增 `resource_lease_events` 表：

- `id`: 数据库主键。
- `lease_id`: 指向不可变租约编号，方便外部追踪。
- `resource_lease_id`: 指向 `resource_leases.id`。
- `machine_id`: 指向 `machine_resources.id`。
- `actor_user_id`: 执行动作的平台用户。
- `target_user_id`: 租约所属用户。
- `event_type`: `CREATED` / `EXTENDED` / `RELEASED` / `EXPIRED` / `FORCE_RELEASED`。
- `occurred_at`: 服务端事件时间。
- `previous_expires_at`: 延期或状态变化前的结束时间，可空。
- `new_expires_at`: 延期后的结束时间或事件发生时的结束时间，可空。

首版不增加 JSON 元数据字段，避免过早设计通用审计系统。

### API

- `POST /api/v1/leases/{lease_id}/extend`
  - 当前租约所有者可调用。
  - 请求：`duration_minutes`
  - 成功：返回更新后的资源租约。
  - 失败：租约不存在、不是本人租约、租约不是 `ACTIVE`、租期非法。

- `POST /api/v1/leases/{lease_id}/force-release`
  - `ADMIN` / `TSE` 可调用。
  - 成功：返回更新后的资源租约。
  - 失败：租约不存在、租约不是 `ACTIVE`、非 `ADMIN/TSE` 越权。

- `GET /api/v1/lease-events`
  - `ADMIN` / `TSE` 可查询。
  - 首版按 `id` 升序返回事件，支持 `after_id` 和 `limit` 连续读取。
  - `TE` 调用返回 `403`。

## Task Checklist

- [x] RED/GREEN 1：占用成功会产生 `CREATED` 租约事件。
- [x] RED/GREEN 2：租约所有者可以延期自己的 `ACTIVE` 租约，并产生 `EXTENDED` 事件。
- [x] RED/GREEN 3：用户不能延期别人的租约，已释放或已到期租约不能延期。
- [x] RED/GREEN 4：释放自己的租约会产生 `RELEASED` 事件，重复释放不产生新事件。
- [x] RED/GREEN 5：惰性到期会产生 `EXPIRED` 事件，重复触发惰性到期不产生重复事件。
- [x] RED/GREEN 6：`ADMIN` / `TSE` 可以强制释放他人租约，并产生 `FORCE_RELEASED` 事件。
- [x] RED/GREEN 7：`TE` 不能强制释放，强制释放非 `ACTIVE` 租约返回稳定错误。
- [x] RED/GREEN 8：租约事件查询仅 `ADMIN` / `TSE` 可访问，支持按 `after_id` 增量读取。
- [x] 前端：增加延期 API client、延期弹窗和“我的租约”延期按钮。
- [x] 前端：为 `ADMIN` / `TSE` 增加强制释放入口。
- [x] 文档：更新 README 当前能力边界与租约接口说明。
- [x] 验证：后端测试、ruff、前端 typecheck、前端 build、Alembic upgrade head。
- [x] 提交：通过验证后创建本地 checkpoint commit。

## Acceptance Scenarios

1. 用户占用一台机器后，`ADMIN/TSE` 能在租约事件列表看到 `CREATED` 事件。
2. 租约所有者延期自己的有效租约后，租约 `expires_at` 延后，并产生 `EXTENDED` 事件。
3. 用户尝试延期别人的租约时收到 `LEASE_NOT_OWNED`。
4. 用户尝试延期已释放或已到期租约时收到 `LEASE_NOT_ACTIVE`。
5. 用户释放自己的有效租约后产生 `RELEASED` 事件。
6. 同一个租约重复释放不会产生第二条释放事件。
7. 租约到期后通过惰性到期转为 `EXPIRED`，并产生一条 `EXPIRED` 事件。
8. `ADMIN` / `TSE` 可以强制释放他人的有效租约，并产生 `FORCE_RELEASED` 事件。
9. `TE` 强制释放任意租约都会收到 `403 FORBIDDEN`。
10. 使用旧 `lease_id` 发起延期或释放请求，不会影响同一机器上的新租约。
11. `ADMIN/TSE` 可以用 `after_id` 连续读取租约事件；`TE` 不能读取租约事件。

## Verification Commands

Backend:

```powershell
cd D:\Desktop\radiaTest-2\intern-projects-main-agent-assisted-test-platform\test-resource-platform\backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Frontend:

```powershell
cd D:\Desktop\radiaTest-2\intern-projects-main-agent-assisted-test-platform\test-resource-platform\frontend
npm.cmd run typecheck
npm.cmd run build
```

## Current Progress

- Clarify complete: 本轮补齐一期租约增强、强制释放、租约事件和测试补强。
- Architect complete: 继续深化 `app.leases` 模块，新增租约事件表；租约事件不替代当前租约状态。
- Solve complete: 后端延期、强制释放、租约事件和事件查询已实现；前端延期与强制释放入口已实现；README 已更新。
- Verification complete:
  - `.\.venv\Scripts\python.exe -m pytest`: 32 passed。
  - `.\.venv\Scripts\python.exe -m ruff check .`: passed。
  - SQLite Alembic `upgrade head`: passed。
  - `npm.cmd run typecheck`: passed。
  - `npm.cmd run build`: passed；仍有 Vite chunk size warning，原因与现有 Naive UI 打包体积有关，本轮不处理拆包。
- Checkpoint commit: `289e0c4 Add lease controls and event tracking`。

## Open Questions

- 暂定延期请求 `duration_minutes` 表示“从当前结束时间继续延长 N 分钟”，而不是从当前时间重新计算。
- 暂定租约事件首版仅 `ADMIN` / `TSE` 查询，不向普通用户开放“我的租约事件”。

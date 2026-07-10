# Phase 1 Feishu Cc-Connect Style Integration

Status: active

## Goal

参考 `cc-connect` 的飞书接入方式，为测试资源平台设计一套飞书接入基础：

- Web 管理页扫码完成飞书应用创建/授权。
- 平台保存飞书应用凭据与连接状态。
- 后端通过飞书 WebSocket 长连接接收用户消息，不要求平台暴露公网 IP。
- 飞书消息最终调用现有资源平台能力：查询机器、申请机器、释放租约、延期租约。

## Reference: cc-connect Flow

本地参考代码目录：

```text
D:\Desktop\radiaTest-2\intern-projects-main-agent-assisted-test-platform\cc-connect
```

关键文件：

- `cmd/cc-connect/feishu.go`
- `core/setup.go`
- `platform/feishu/feishu.go`
- `platform/feishu/card.go`
- `web/src/pages/Projects/PlatformSetupQR.tsx`
- `web/src/api/setup.ts`

cc-connect 的扫码接入分为三段：

1. `begin`
   - 请求 `https://accounts.feishu.cn/oauth/v1/app/registration`
   - 参数：
     - `action=begin`
     - `archetype=PersonalAgent`
     - `auth_method=client_secret`
     - `request_user_info=open_id`
   - 返回：
     - `device_code`
     - `verification_uri_complete`
     - `interval`
     - `expire_in`
   - 前端用 `verification_uri_complete` 生成二维码。

2. `poll`
   - 继续请求同一个 registration endpoint。
   - 参数：
     - `action=poll`
     - `device_code=<device_code>`
   - 用户扫码并确认后返回：
     - `client_id`，即飞书 `app_id`
     - `client_secret`，即飞书 `app_secret`
     - `user_info.open_id`
     - `user_info.tenant_brand`
   - 如果 `tenant_brand=lark`，cc-connect 会切换到 `https://accounts.larksuite.com`。

3. `save`
   - 把 `app_id/app_secret/platform_type/owner_open_id` 写入配置。
   - cc-connect 写 TOML；测试资源平台应写 PostgreSQL。

运行时：

- 用 `app_id/app_secret` 创建飞书 SDK client。
- 默认走 WebSocket 长连接模式。
- 订阅并处理：
  - `im.message.receive_v1`
  - `card.action.trigger`
  - 可选 bot menu 事件。
- 收到消息后执行：
  - 去重。
  - 忽略旧消息。
  - 群聊未 @ 机器人时忽略。
  - `allow_from/allow_chat` 权限过滤。
  - 解析消息文本并分发到业务 handler。
- 回复时通过飞书消息 API 回复原消息、发送新消息，或发送交互卡片。

## Current Platform Fit

当前测试资源平台已有可复用能力：

- 用户登录与 RBAC。
- 机器资源池与机器列表。
- 机器占用状态与使用人展示。
- 租约创建、查看、释放、延期、强制释放。
- 租约事件记录。
- 机器凭据配置和查看。
- SSH/BMC 连通性检测。

当前缺口：

- 没有飞书应用配置表。
- 没有飞书扫码创建/绑定应用接口。
- 没有飞书 WebSocket worker。
- 没有飞书用户 `open_id` 到平台用户的映射。
- 没有飞书命令解析。
- 没有飞书卡片渲染与按钮回调。
- 没有飞书操作审计来源字段。

## Proposed Architecture

### Backend Modules

新增 `app.integrations.feishu`：

- `models.py`
  - `FeishuApp`
  - `FeishuSetupSession`
  - `FeishuUserBinding`
  - `FeishuMessageEvent`
- `schemas.py`
  - setup begin/poll/save response。
  - app status response。
  - command/action response。
- `registration.py`
  - 封装 cc-connect 的 app registration flow。
- `client.py`
  - 封装 tenant token、bot info、send message、send card。
- `worker.py`
  - 运行 WebSocket 长连接。
  - 把飞书消息转换成平台内部 command。
- `commands.py`
  - 确定性命令解析，不先引入 LLM。
- `cards.py`
  - 飞书交互卡片 JSON 生成。

### Data Model

`feishu_apps`

- `id`
- `name`
- `platform_type`: `FEISHU` / `LARK`
- `app_id`
- `app_secret_encrypted`
- `owner_open_id`
- `tenant_brand`
- `bot_open_id`
- `status`: `CONFIGURED` / `CONNECTED` / `DISCONNECTED` / `ERROR`
- `last_connected_at`
- `last_error`
- `created_by_user_id`
- `created_at`
- `updated_at`

`feishu_setup_sessions`

- `id`
- `device_code`
- `qr_url`
- `base_url`
- `status`: `PENDING` / `COMPLETED` / `DENIED` / `EXPIRED` / `ERROR`
- `expires_at`
- `created_by_user_id`
- `created_at`
- `updated_at`

`feishu_user_bindings`

- `id`
- `feishu_app_id`
- `platform_user_id`
- `open_id`
- `display_name`
- `created_at`
- unique: `feishu_app_id + open_id`

`feishu_message_events`

- `id`
- `feishu_app_id`
- `message_id`
- `chat_id`
- `sender_open_id`
- `message_type`
- `raw_event_json`
- `handled_status`
- `created_at`
- unique: `feishu_app_id + message_id`

### Setup APIs

- `POST /api/v1/integrations/feishu/setup/begin`
  - `ADMIN` / `TSE` only。
  - 调用飞书 registration begin。
  - 返回 `device_code/qr_url/interval/expires_in`。

- `POST /api/v1/integrations/feishu/setup/poll`
  - `ADMIN` / `TSE` only。
  - 用 `device_code` 轮询飞书 registration。
  - 返回 `pending/completed/denied/expired/error`。

- `POST /api/v1/integrations/feishu/setup/save`
  - `ADMIN` / `TSE` only。
  - 保存 `app_id/app_secret/platform_type/owner_open_id`。
  - 加密保存 `app_secret`。

- `GET /api/v1/integrations/feishu/apps`
  - 查看已配置飞书应用和连接状态。

- `POST /api/v1/integrations/feishu/apps/{app_id}/start`
  - 启动该应用的 WebSocket worker。

- `POST /api/v1/integrations/feishu/apps/{app_id}/stop`
  - 停止 worker。

### Phase 1 Commands

第一版只做确定性命令：

- `/help`
- `/whoami`
- `/bind <平台用户名>` 或通过 Web 侧生成绑定入口。
- `/machines`
- `/machines free`
- `/lease <resource_code> <minutes> <purpose>`
- `/my-leases`
- `/release <lease_id>`
- `/extend <lease_id> <minutes>`

第一版不通过飞书返回机器 SSH/BMC 密码。

### Permissions

参考 cc-connect 文档，飞书应用至少需要：

- `contact:user.base:readonly`
- `im:message.group_at_msg:readonly`
- `im:message.p2p_msg:readonly`
- `im:message.group_msg`
- `im:message:send_as_bot`
- `im.message.receive_v1`

如果做交互卡片，还需要：

- `card.action.trigger`

### Frontend

新增管理页：

- 路由：`/integrations/feishu`
- 入口：后台首页新增“飞书接入”按钮。
- 页面能力：
  - 开始扫码配置。
  - 展示二维码。
  - 轮询扫码状态。
  - 保存应用凭据。
  - 展示应用连接状态。
  - 启停 worker。

### Implementation Order

1. 只做 app registration begin/poll/save，先不启动 WebSocket。
2. 保存飞书应用配置，确保 app_secret 加密入库。
3. 前端做扫码配置页。
4. 后端实现飞书 SDK client，能获取 tenant token 和 bot info。
5. 实现 WebSocket worker 与状态展示。
6. 实现 `/whoami` 和 `/help` 两个最小命令。
7. 实现资源查询和租约命令。
8. 实现基础飞书卡片。

## Test Plan

Backend:

- registration begin 请求参数测试。
- poll pending/completed/denied/expired 测试。
- save app credentials 加密落库测试。
- worker 消息去重测试。
- 未绑定飞书用户不可申请资源测试。
- 已绑定用户申请/释放/延期资源测试。

Frontend:

- setup begin/poll/save API client typecheck。
- 扫码页不同状态渲染。
- 连接状态展示。

Manual:

- 用飞书 App 扫码创建应用。
- 确认平台保存 app_id/app_secret。
- 启动 worker 后查看连接状态。
- 在飞书单聊发送 `/whoami`。
- 绑定平台用户后发送 `/machines`、`/lease`、`/release`。

## Open Decisions

- 飞书用户绑定平台用户时，是用平台 Web 登录确认，还是先用 `/bind username` 临时方案。
- 第一版是否必须做交互卡片，还是先用纯文本命令。
- Worker 是随 API 进程启动，还是独立进程/container。

## Current Progress

- Decision: `ADMIN` / `TSE` can configure Feishu app setup.
- Done: backend `begin/poll/save` APIs for cc-connect style Feishu app registration.
- Done: `feishu_setup_sessions` and `feishu_apps` tables with Alembic migration.
- Done: `app_secret` is encrypted with existing `CREDENTIAL_ENCRYPTION_KEY` before persistence.
- Done: frontend `/integrations/feishu` page with QR setup, polling, auto-save, and configured app list.
- Done: dashboard entry for `ADMIN` / `TSE`.
- Not done yet: Feishu WebSocket worker, tenant token/bot info runtime client, user binding, message commands, and cards.

Verification:

- `.\.venv\Scripts\python.exe -m pytest`: 37 passed.
- `.\.venv\Scripts\python.exe -m ruff check .`: passed.
- SQLite Alembic `upgrade head`: passed.
- `npm.cmd run typecheck`: passed.
- `npm.cmd run build`: passed with existing Vite chunk size warning.
- Local PostgreSQL Alembic run was not completed because the local `postgres` password did not match the configured default database URL.

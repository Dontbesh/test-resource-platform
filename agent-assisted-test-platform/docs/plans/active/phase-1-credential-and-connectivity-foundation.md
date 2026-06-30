# Phase 1 Credential And Connectivity Foundation

Status: active

## Goal

在不接入真实物理机的前提下，完成机器凭据管理和连通性检查的基础能力，让平台从“能占用机器”推进到“能安全保存连接信息、按权限查看连接信息、记录凭据查看行为，并为后续真实 SSH/BMC 联调预留清晰接口”。

本轮目标不是直接操作真实机器，而是先把真实机器接入前最容易出安全问题的部分打好底座。

## Scope

- 新增机器凭据数据模型，用于保存 SSH 和 BMC 连接信息。
- 凭据敏感字段加密入库，不保存明文密码。
- 新增凭据配置接口，允许 `ADMIN` / `TSE` 为机器维护 SSH/BMC 凭据。
- 新增凭据查看接口，按机器是否关键、当前租约归属和用户角色做授权。
- 每次成功查看凭据写入审计记录。
- 前端资源台账页增加凭据配置入口和凭据查看入口。
- 新增连通性检查模块接口和 API：当前先做 TCP 端口检查能力，后续真实机器联调时复用同一接口。
- 连通性检查可在测试中通过本地假连接器验证，不依赖实验室真实机器。
- 更新 README 当前能力边界和测试说明。

## Non-Goals

- 本轮不使用用户提供的两台真实机器做自动化验证。
- 不执行真实远程命令。
- 不做 SSH 登录后命令执行。
- 不做 IPMI/Redfish 开关机、重启、电源状态查询。
- 不做凭据批量导入。
- 不做密钥轮换后台流程。
- 不做飞书、PAT、LLM 或外部身份绑定。

## Confirmed Decisions

- 真实测试机暂时保留，等平台凭据、权限、审计和连通性能力更完整后再联调。
- 凭据不能写入 Git、README、周报、日志或前端持久化存储。
- 占用成功仍不返回凭据；凭据只能通过独立接口查看。
- 普通机器凭据：`ADMIN` 可查看；当前有效租约的占用人可查看。
- 关键机器凭据：仅 `ADMIN` 可查看，即使当前用户占用了该机器也不能绕过。
- 查看凭据必须审计。
- 连通性检查先以 TCP 端口探测为主，避免依赖 ICMP 权限和真实设备。

## Architecture

### Backend modules

新增 `app.credentials` 模块：

- `models.py`: `MachineCredential` 与 `CredentialAccessEvent`。
- `crypto.py`: 加密和解密凭据字段。
- `schemas.py`: 凭据配置请求、凭据公开响应、审计响应。
- `service.py`: 凭据配置、凭据查看授权、审计写入。
- `api/v1/machine_credentials.py`: HTTP 路由和稳定错误码。

新增 `app.connectivity` 模块：

- `schemas.py`: 连通性检查请求与响应。
- `service.py`: 连通性检查业务逻辑。
- `tcp.py`: 生产环境 TCP socket 检查实现。
- `api/v1/connectivity_checks.py`: HTTP 路由。

`credentials` 和 `connectivity` 都以机器资源为入口，但不把凭据明文或检查过程塞进机器台账模块。机器台账继续描述“机器是什么”，凭据模块描述“如何连接”，连通性模块描述“当前能否连上”。

### Data model

新增 `machine_credentials` 表：

- `id`
- `machine_id`
- `ssh_username`
- `encrypted_ssh_password`
- `bmc_username`
- `encrypted_bmc_password`
- `created_at`
- `updated_at`

新增 `credential_access_events` 表：

- `id`
- `machine_id`
- `user_id`
- `access_type`
- `created_at`

### Configuration

新增环境变量：

- `CREDENTIAL_ENCRYPTION_KEY`

本轮计划使用 `cryptography.fernet.Fernet` 加密敏感字段。测试环境可用固定测试 key；生产和共享测试环境必须通过 `.env` 或部署密钥注入，不能提交到代码仓库。

### API

- `PUT /api/v1/machines/{resource_code}/credentials`
  - `ADMIN` / `TSE` 配置机器凭据。
  - 请求包含 SSH/BMC 用户名和密码。
  - 响应不返回密码明文。

- `GET /api/v1/machines/{resource_code}/credentials`
  - 授权后返回该机器 SSH/BMC 连接信息。
  - 普通机器：`ADMIN` 或当前有效租约占用人可查看。
  - 关键机器：仅 `ADMIN` 可查看。
  - 成功查看时写入 `credential_access_events`。

- `POST /api/v1/machines/{resource_code}/connectivity-checks`
  - 执行按需连通性检查。
  - 首版检查 SSH 端口和 BMC HTTPS 端口。
  - 返回每个目标的状态、耗时和错误原因。

## Task Checklist

- [x] 后端 RED/GREEN 1：`ADMIN` / `TSE` 可以为机器配置凭据，响应不包含密码明文。
- [x] 后端 RED/GREEN 2：数据库中不保存明文密码。
- [x] 后端 RED/GREEN 3：普通机器当前占用人可以查看凭据，并产生审计记录。
- [x] 后端 RED/GREEN 4：非占用人不能查看普通机器凭据。
- [x] 后端 RED/GREEN 5：关键机器凭据仅 `ADMIN` 可查看。
- [x] 后端 RED/GREEN 6：连通性检查 API 可以通过可替换连接器返回可达/不可达结果。
- [x] 前端：资源台账页增加配置凭据和查看凭据入口。
- [x] 前端：资源台账页增加连通性检查入口和结果展示。
- [x] 文档：更新 README 和 `.env.example`。
- [x] 验证：后端测试、ruff、前端 typecheck、前端 build、Alembic upgrade head。
- [x] 提交：通过验证后创建本地 checkpoint commit。

## Acceptance Scenarios

1. `ADMIN` 创建机器后，可以为该机器配置 SSH/BMC 凭据；响应不会回显密码。
2. 直接读取数据库时看不到 SSH/BMC 明文密码。
3. TE 占用普通机器后，可以查看该机器凭据。
4. 另一个没有占用该机器的 TE 查看同一机器凭据时收到稳定的 403 错误。
5. TE 即使占用了关键机器，也不能查看关键机器凭据。
6. `ADMIN` 可以查看关键机器凭据。
7. 每次成功查看凭据都会产生审计记录。
8. 连通性检查 API 在测试连接器返回可达时显示可达，在返回失败时显示不可达。

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

- Clarify complete: 真实机器暂不接入；本轮先做凭据、授权、审计和可测试连通性接口。
- Architect complete: 新增 `credentials` 和 `connectivity` 两个模块，避免污染机器台账和租约模块。
- Solve complete: 后端凭据、审计、连通性接口和前端资源台账入口已实现。
- Verification complete: `pytest` 26 passed；`ruff check .` passed；`npm.cmd run build` passed；SQLite Alembic `upgrade head` passed。

## Open Questions

- 已确认新增 Python 依赖 `cryptography` 用于 Fernet 加密。
- 已确认凭据查看审计首版只做后端表记录，不做审计查询页面。

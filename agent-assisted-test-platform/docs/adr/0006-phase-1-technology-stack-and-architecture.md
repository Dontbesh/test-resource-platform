# 一期技术选型与总体架构

Status: Accepted

Date: 2026-06-23

## Context

一期目标是新建一个独立的测试资源平台，完成本地账号、三角色权限、资源池、物理机和已有虚机台账、资源租约、凭据加密、CSV 导入、连通性检查、审计、OpenAPI 和 Docker Compose 部署。

旧 `radiatest` 只作为领域知识和迁移字段参考。新平台不复用旧系统数据库、运行服务或 Python 包。

本期需要优先控制范围和交付风险：

- 三个月必须交付可试用的一期。
- 一期不做微服务、消息队列、Kubernetes、IM、LLM、远程 Shell、虚机创建、PXE 或电源控制。
- 核心业务规则必须位于后端业务模块中，Web 和未来 IM 适配器调用同一组 `/api/v1` API。
- 资源租约、凭据查看、权限、审计、幂等和并发冲突需要自动化测试保护。

## Decision

一期正式采用以下技术栈：

- 后端：Python 3.12 + FastAPI + Pydantic + SQLAlchemy 2.x + Alembic。
- 数据库：PostgreSQL。
- 前端：Vue 3 + TypeScript + Vite + Vue Router + Pinia + Naive UI。
- 测试：pytest + httpx/TestClient + Playwright。
- API 文档：FastAPI 自动生成 OpenAPI，并将 OpenAPI JSON 纳入兼容性检查。
- 部署：Docker Compose 单机部署，包含 web、api、postgres，可选 nginx。
- 后续异步能力：一期不引入队列；二期需要执行代理后，再引入独立 agent 进程和任务表，必要时增加 Redis/RQ 或 Celery。

总体架构采用模块化单体：

```text
frontend-vue
  -> /api/v1
backend-fastapi
  -> identity
  -> authorization
  -> resource_pool
  -> machine_resource
  -> resource_lease
  -> credential
  -> csv_import
  -> connectivity_check
  -> audit
  -> idempotency
postgres
```

后端内部按照领域模块组织。每个模块暴露少量应用服务接口，数据库访问、事务、状态转换和审计写入隐藏在模块实现内部。

## Considered Options

### Option A: FastAPI + PostgreSQL + SPA Frontend

优点：

- FastAPI 对 OpenAPI 支持最好，天然适合 API-first。
- Pydantic 适合做请求、响应和错误结构校验。
- Python 学习成本低，适合三个月实习周期。
- pytest、httpx、SQLAlchemy、Alembic 生态成熟。
- 后续二期接 libvirt、SSH、IPMI、CSV、脚本迁移时，Python 生态更顺手。
- 前端采用 Vue 3 SPA；React 保留为已评估但本期不采用的备选。

问题：

- 需要一开始建立清晰模块边界，否则 FastAPI 项目也容易变成路由函数堆积。
- 并发占用不能只依赖 Python 判断，必须用数据库事务、唯一约束或行锁兜底。
- 团队如果完全没有 FastAPI 经验，需要第一周写好项目骨架示例。

结论：推荐。

### Option B: Flask + PostgreSQL + SPA Frontend

优点：

- 与旧 `radiatest` 后端框架接近，理解旧代码后迁移心智成本低。
- Flask 轻量，概念简单。
- SQLAlchemy、Alembic、pytest 生态成熟。

问题：

- OpenAPI、请求校验、响应模型需要额外约定和库维护。
- 项目规模稍大后，路由、权限、错误码、文档容易依赖人工纪律。
- 旧平台本身就是 Flask 项目，继续选 Flask 容易不自觉复刻旧平台的松散结构。

结论：可行但不推荐作为首选。

### Option C: Spring Boot + PostgreSQL + SPA Frontend

优点：

- 企业级权限、事务、分层、迁移、测试方案成熟。
- 类型系统和工程约束强，长期维护稳定。
- 对复杂后台系统和团队协作友好。

问题：

- 对实习周期来说学习和启动成本更高。
- 二期需要和现有 Linux/KVM/SSH 脚本生态结合时，Java 不如 Python 直接。
- 如果团队没有成熟 Spring Boot 模板，容易把时间花在框架工程化而不是领域闭环。

结论：长期可行，但不适合作为本次三个月一期首选。

## Frontend Choice

一期前端不应因为旧平台使用 Vue 就继续选择 Vue。评估重点应放在认证、权限菜单、表格、表单、API 状态管理和长期维护成本。

本项目的前端认证不是复杂的企业 SSO，而是本地账号登录后的后台管理权限控制。真正的认证、授权、审计和越权拒绝都必须由后端完成；前端只负责提升体验，例如未登录跳转、菜单隐藏、按钮禁用和 403 页面。因此，前端选型主要比较“实现这些体验层能力的复杂度”和“长期维护成本”。

### Option A: Vue 3 + TypeScript + Vite + Vue Router + Pinia + Naive UI

优点：

- 路由守卫模型直接，适合实现“未登录跳登录页、无权限跳 403、按角色生成菜单”等需求。
- Pinia 的 store 写法轻量，保存当前用户、角色、权限、token/session 状态比较直观。
- Naive UI 覆盖后台管理常用的表格、筛选、表单、弹窗、标签和消息提示。
- 文件结构和心智模型相对集中，适合小团队快速交付一期。
- 对后台管理常见场景而言，需要组合的核心库较少，认证和权限代码更容易被初学者读懂。

问题：

- Vue 生态中的企业后台成套方案少于 React + Ant Design Pro，需要自己组织布局、权限菜单和 API client。
- 如果团队长期主力技术栈是 React，选择 Vue 会增加未来新成员接手和跨项目复用成本。

认证实现难度：

- 简单。前端只需实现登录页、当前用户 store、API 拦截器、全局路由守卫和权限菜单。
- 真实鉴权仍由后端完成；前端只做体验层面的页面保护。

### Option B: React + TypeScript + Vite + React Router + TanStack Query + Ant Design

优点：

- React 生态更大，招聘、资料、第三方库和后台模板更多。
- Ant Design 面向企业后台，表格、表单、弹窗、布局和 Pro Components 生态成熟。
- TanStack Query 很适合处理资源列表、详情、分页、刷新、缓存失效和请求状态。
- React 的组合能力强，后续复杂交互和自定义组件有更大生态空间。
- 如果团队已经熟悉 React，认证、权限组件和 API 状态管理可以沉淀为更通用的前端基础设施。

问题：

- React 本身只负责 UI，需要额外选择 router、server state、client state、form、权限封装等库。
- React Router 当前能力很强，但模式较多；对新手来说，需要先明确只采用 SPA/data-router 的一小部分能力。
- 如果不用管理框架，认证、菜单、权限按钮、表格查询约定仍需要自己搭。
- 初期工程决策点多于 Vue，例如表单库、请求封装、权限组件、错误边界和布局约定都需要统一。

认证实现难度：

- 中等。可以实现得很干净，但需要自己约定 `AuthProvider`、`ProtectedRoute`、`useCurrentUser`、API 拦截器和权限组件。
- 对熟悉 React 的团队不难；对第一次做后台的人，选择点比 Vue 多。

### Option C: React + Refine 或 Ant Design Pro

优点：

- 更像“后台管理平台框架”，内置或约定了认证、授权、资源路由、列表、表单、菜单等常见后台模式。
- Refine 明确提供 auth provider、access control provider、data provider、audit log 等概念，与本项目的一期后台管理形态相似。
- 如果目标是最快搭出管理后台，React 管理框架会比从零搭 Vue 或 React 更快。

问题：

- 框架抽象会进入业务代码，后续要理解它的 data provider、resource、auth provider 等约定。
- 本项目是 API-first 的资源平台，不是普通 CRUD 管理后台；租约并发、幂等、凭据审计等关键逻辑仍必须在后端，不能被前端框架“CRUD 化”。
- 如果团队对该框架不熟，调试和定制成本可能在中后期显现。

认证实现难度：

- 初始最简单。框架已经提供认证和授权扩展点。
- 长期复杂度取决于我们是否能接受框架的资源模型和路由模型。

### Recommendation

前端曾按团队条件比较以下路线，而不是按旧平台技术栈选择：

| 条件 | 推荐 |
|---|---|
| 实习生或团队 React 经验不明显强于 Vue，需要最快完成一期后台管理闭环 | Vue 3 + TypeScript + Vite + Vue Router + Pinia + Naive UI |
| 团队已有 React 经验，后续其他项目也偏 React，希望沉淀通用前端能力 | React + TypeScript + Vite + React Router + TanStack Query + Ant Design |
| 导师更关注快速生成标准后台 CRUD，且接受框架约束 | React + Refine + Ant Design，需要先做 spike |

本期正式选择 Vue 3。理由是一期前端认证和 RBAC 只是体验层保护，Vue Router + Pinia 能用较少概念完成登录状态、路由守卫、角色菜单和权限按钮；后端仍负责真正的认证、授权、审计和稳定错误返回。

React 方案同样可行，尤其适合希望长期复用 Ant Design、TanStack Query 和 React 权限组件的团队。本期不采用 React，主要是为了减少一期工程决策点，优先完成资源平台闭环。

不建议一期使用 Next.js。该平台是内网后台管理系统，不需要 SEO 或服务端渲染；Next.js 的全栈能力会增加部署和认证边界复杂度。

## Backend Architecture

后端采用 API-first 的模块化单体。建议第一批模块如下：

| Module | Responsibility |
|---|---|
| identity | 本地账号、密码登录、用户启停、PAT 生命周期 |
| authorization | `ADMIN`、`TSE`、`TE` 权限矩阵和接口授权 |
| resource_pool | 资源池创建、维护、查询 |
| machine_resource | 物理机和已有虚机统一台账、标签、状态、宿主关系 |
| resource_lease | 占用、释放、延期、强制释放、到期处理和租约事件 |
| credential | SSH/BMC 凭据加密保存、授权查看和审计 |
| csv_import | CSV 预检查、确认导入、错误报告 |
| connectivity_check | 按需 Ping 或 SSH 端口检查，保存最近结果 |
| audit | 登录、资源变更、租约变更、凭据查看等审计查询 |
| idempotency | 写 API 的 `Idempotency-Key` 保存、重复响应和冲突检测 |

路由层只做：

- 解析请求。
- 调用应用服务。
- 返回统一响应或错误。

业务服务层负责：

- 权限判断。
- 状态转换。
- 数据库事务。
- 并发冲突处理。
- 幂等处理。
- 审计写入。

数据库层负责：

- 表结构和唯一约束。
- 事务隔离。
- 有效租约唯一性约束。
- Alembic 迁移。

## Data Model Direction

一期核心表建议包括：

- `users`
- `personal_access_tokens`
- `resource_pools`
- `machine_resources`
- `machine_credentials`
- `resource_leases`
- `resource_lease_events`
- `audit_logs`
- `idempotency_records`
- `connectivity_checks`
- `csv_import_jobs`

资源占用不能像旧平台一样直接把占用人、开始时间、结束时间写在机器表上。新平台必须用独立 `resource_leases` 表，并用不可变 `lease_id` 执行释放和延期。

`machine_resources` 表表达“机器是什么”，`resource_leases` 表表达“某次谁在什么时间段使用了它”。

## API Direction

API 使用 `/api/v1` 主版本。

通用响应要求：

- 每个响应包含或可追踪 `request_id`。
- 错误返回稳定 `error_code`。
- 写 API 支持 `Idempotency-Key`。
- API 文档由 OpenAPI 生成并纳入检查。

关键 API 方向：

- 占用机器：使用 `resource_code` 和 `duration_minutes`。
- 占用成功：返回 `lease_id`，不返回密码。
- 释放机器：使用 `lease_id`。
- 延期租约：使用 `lease_id`。
- 查看凭据：使用独立凭据 API，单独鉴权和审计。

## Testing Strategy

一期测试重点不追求页面细节覆盖，而是保护业务不出错：

- 单元或领域测试：租约状态转换、最大租期、权限矩阵、凭据可见性。
- API 集成测试：登录、PAT、资源池、机器台账、占用、释放、延期、凭据查看、审计。
- 并发测试：两个用户同时占用同一台机器只能成功一个。
- 幂等测试：重复占用、重复释放、参数冲突返回稳定结果。
- 旧租约竞态测试：旧 `lease_id` 的延迟释放不能影响新租约。
- 端到端测试：至少覆盖登录、查询机器、占用、查看凭据、释放。

## Deployment Direction

一期使用 Docker Compose：

```text
compose
  - frontend
  - api
  - postgres
  - nginx optional
```

配置通过环境变量注入：

- 数据库连接。
- JWT/session 密钥。
- PAT 哈希参数。
- 凭据加密密钥。
- 最大租期。
- 日志级别。

凭据加密密钥必须与数据库分离配置，不能写入代码仓库。

## Consequences

收益：

- API-first 与 OpenAPI 成本低。
- Python 生态适合后续资源执行代理和迁移脚本。
- Vue 3 能用较少前端工程决策完成一期后台认证、权限菜单、表格、筛选、表单和弹窗。
- PostgreSQL 能用事务、约束和索引保护租约并发一致性。
- 模块化单体能在一期控制复杂度，也为二期执行代理留下扩展点。

代价：

- 需要主动约束模块边界，避免业务逻辑散落在路由函数中。
- 需要从项目第一天建立迁移、测试、错误码和 OpenAPI 检查。
- 需要团队熟悉 FastAPI、Pydantic、SQLAlchemy 2.x 的基本实践。

## Follow-up Work

- 创建新代码仓骨架。
- 补充领域模型图和接口级权限矩阵。
- 编写首个端到端 tracer：登录或健康检查接口 + Vue 页面 + OpenAPI + 测试 + Docker Compose。

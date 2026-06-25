# 测试资源平台

这是新测试资源平台的一期源码目录。项目管理材料、ADR 和周报保留在同级 `agent-assisted-test-platform/` 目录中。

## 技术栈

- 后端：FastAPI + Pydantic + SQLAlchemy 2.x + Alembic
- 数据库：PostgreSQL
- 前端：Vue 3 + TypeScript + Vite + Vue Router + Pinia + Naive UI
- 部署：Docker Compose

## 目录结构

```text
test-resource-platform/
├── backend/
│   ├── app/
│   ├── migrations/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## 第一条 Tracer

第一条端到端链路是：

```text
Vue 首页 -> GET /api/v1/health -> FastAPI -> PostgreSQL SELECT 1
```

接口会返回 API 状态、版本、`request_id` 和数据库连通状态。

当前登录链路是：

```text
Vue 登录页 -> POST /api/v1/auth/login -> HttpOnly Cookie -> GET /api/v1/auth/me
```

空数据库首次启动时会根据 `.env` 初始化第一个 `ADMIN`。

## 本地启动

Windows PowerShell 复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

启动：

```powershell
docker compose up --build
```

Linux 服务器复制环境变量模板：

```bash
cp .env.example .env
```

启动：

```bash
docker compose up --build
```

如果服务器只有旧版 Compose 命令，使用：

```bash
docker-compose up --build
```

访问：

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/api/docs
- OpenAPI JSON：http://localhost:8000/api/v1/openapi.json
- 健康检查：http://localhost:8000/api/v1/health

默认初始登录账号来自 `.env`：

```text
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=Admin@123456
```

首次测试可访问前端登录页：

```text
http://localhost:5173/login
```

生产或共享测试环境必须修改默认密码和 `SESSION_SECRET_KEY`。

## 后端测试

在 `backend/` 目录安装依赖后运行：

```powershell
pytest
```

## 前端检查

在 `frontend/` 目录安装依赖后运行：

```powershell
npm run typecheck
npm run build
```

## 当前边界

此骨架只验证工程链路，不包含完整用户、权限、资源池、机器台账、租约、凭据、CSV 导入和审计能力。

当前已包含 Web 登录最小闭环，但尚未包含完整用户管理、PAT 生命周期和接口级 RBAC。

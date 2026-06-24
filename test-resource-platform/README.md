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

当前第一条端到端链路是：

```text
Vue 首页 -> GET /api/v1/health -> FastAPI -> PostgreSQL SELECT 1
```

接口会返回 API 状态、版本、`request_id` 和数据库连通状态。

## 本地启动

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

启动：

```powershell
docker compose up --build
```

访问：

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/api/docs
- OpenAPI JSON：http://localhost:8000/api/v1/openapi.json
- 健康检查：http://localhost:8000/api/v1/health

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

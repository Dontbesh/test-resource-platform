from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.bootstrap.admin import ensure_database_schema, ensure_initial_admin
from app.core.config import get_settings
from app.core.request_id import RequestIdMiddleware
from app.db.session import iter_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    ensure_database_schema(settings)
    for session in iter_session(settings.database_url):
        ensure_initial_admin(session, settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

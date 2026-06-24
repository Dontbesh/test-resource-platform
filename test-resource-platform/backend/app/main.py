from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.request_id import RequestIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

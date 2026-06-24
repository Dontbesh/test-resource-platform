from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.health import check_database

router = APIRouter()


class DatabaseHealth(BaseModel):
    status: Literal["ok", "unavailable"]
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    version: str
    request_id: str
    database: DatabaseHealth


@router.get("/health", response_model=HealthResponse)
def health_check(request: Request) -> HealthResponse:
    settings = get_settings()
    database = check_database(settings.database_url)
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        request_id=request.state.request_id,
        database=DatabaseHealth(status=database.status, error=database.error),
    )

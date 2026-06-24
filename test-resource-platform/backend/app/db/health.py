from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class DatabaseCheckResult:
    status: str
    error: str | None = None


@lru_cache
def get_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def check_database(database_url: str) -> DatabaseCheckResult:
    try:
        engine = get_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return DatabaseCheckResult(status="ok")
    except Exception as exc:
        return DatabaseCheckResult(status="unavailable", error=exc.__class__.__name__)

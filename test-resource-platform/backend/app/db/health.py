from dataclasses import dataclass

from sqlalchemy import text

from app.db.session import get_engine


@dataclass(frozen=True)
class DatabaseCheckResult:
    status: str
    error: str | None = None


def check_database(database_url: str) -> DatabaseCheckResult:
    try:
        engine = get_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return DatabaseCheckResult(status="ok")
    except Exception as exc:
        return DatabaseCheckResult(status="unavailable", error=exc.__class__.__name__)

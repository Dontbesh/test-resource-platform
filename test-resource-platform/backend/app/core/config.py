from dataclasses import dataclass
from functools import lru_cache
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    database_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=getenv("APP_NAME", "Test Resource Platform"),
        app_version=getenv("APP_VERSION", "0.1.0"),
        database_url=getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/test_resource_platform",
        ),
    )

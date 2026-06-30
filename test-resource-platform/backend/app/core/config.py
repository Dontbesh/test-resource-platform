from dataclasses import dataclass
from functools import lru_cache
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    database_url: str
    session_secret_key: str
    session_cookie_name: str
    session_max_age_seconds: int
    session_cookie_secure: bool
    initial_admin_username: str
    initial_admin_password: str
    auto_create_schema: bool
    credential_encryption_key: str | None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=getenv("APP_NAME", "Test Resource Platform"),
        app_version=getenv("APP_VERSION", "0.1.0"),
        database_url=getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/test_resource_platform",
        ),
        session_secret_key=getenv("SESSION_SECRET_KEY", "change-me"),
        session_cookie_name=getenv("SESSION_COOKIE_NAME", "trp_session"),
        session_max_age_seconds=int(getenv("SESSION_MAX_AGE_SECONDS", "28800")),
        session_cookie_secure=getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        initial_admin_username=getenv("INITIAL_ADMIN_USERNAME", "admin"),
        initial_admin_password=getenv("INITIAL_ADMIN_PASSWORD", "Admin@123456"),
        auto_create_schema=getenv("AUTO_CREATE_SCHEMA", "false").lower() == "true",
        credential_encryption_key=getenv("CREDENTIAL_ENCRYPTION_KEY"),
    )

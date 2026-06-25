from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_engine
from app.identity.models import UserRole
from app.identity.service import count_users, create_user


def ensure_database_schema(settings: Settings) -> None:
    if not settings.auto_create_schema:
        return
    # Tests can create their own schema without invoking Alembic.
    # Runtime environments should run `alembic upgrade head` instead.
    Base.metadata.create_all(get_engine(settings.database_url))


def ensure_initial_admin(session: Session, settings: Settings) -> None:
    if count_users(session) > 0:
        return
    create_user(
        session=session,
        username=settings.initial_admin_username,
        password=settings.initial_admin_password,
        role=UserRole.ADMIN,
    )
    session.commit()
